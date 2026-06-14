import logging
import json
from datetime import datetime
import torch
import numpy as np

from fastapi import APIRouter, File, HTTPException, UploadFile, Response
from fastapi.responses import FileResponse
from typing import List
import os
from app.services import file_store
from app.schemas import PaperAnalysisResponse, PaperParseRequest
from app.services.agent_review import AgentReviewCoordinator
from app.services.document_encoder import DocumentEncoder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# lightweight default instances; heavy components are lazily initialized
encoder = DocumentEncoder()
_claim_extractor = None
agent_coordinator = AgentReviewCoordinator()
_graph_builder = None


def get_graph_builder():
    global _graph_builder
    if _graph_builder is None:
        from app.services.graph_builder import KnowledgeGraphBuilder

        _graph_builder = KnowledgeGraphBuilder()
    return _graph_builder
_enriched_analyzer = None


def get_claim_extractor():
    global _claim_extractor
    if _claim_extractor is None:
        from app.services.claim_extraction import ClaimExtractor

        _claim_extractor = ClaimExtractor()
        
        # Override/wrap claim extractor to generate and attach embeddings to Claims
        original_extract_claims = _claim_extractor.extract_claims

        def wrapped_extract_claims(document) -> list:
            claims = original_extract_claims(document)
            _claim_extractor._initialize_model()
            for claim in claims:
                tokens = _claim_extractor.tokenizer(claim.text, truncation=True, max_length=128, return_tensors="pt")
                with torch.no_grad():
                    output = _claim_extractor.model(**tokens)
                if hasattr(output, "pooler_output") and output.pooler_output is not None:
                    emb = output.pooler_output
                else:
                    emb = output.last_hidden_state[:, 0, :]
                # Convert to a list of floats
                claim.embedding = emb[0].cpu().numpy().tolist()
            return claims

        _claim_extractor.extract_claims = wrapped_extract_claims
        
    return _claim_extractor


def get_enriched_analyzer():
    global _enriched_analyzer
    if _enriched_analyzer is None:
        from app.services.output_layer import EnrichedPaperAnalysis

        _enriched_analyzer = EnrichedPaperAnalysis()
    return _enriched_analyzer


def _post_process_graph(parsed, claims, review, builder):
    # Determine stance label
    stance_dict = getattr(review, "stance", {})
    stance_label = "neutral"
    if stance_dict:
        max_key = max(stance_dict, key=lambda k: stance_dict.get(k, 0.0))
        if max_key == "PTLDS":
            stance_label = "supporting"
        elif max_key == "CLD":
            stance_label = "opposing"

    method_quality = getattr(review, "method_quality", 0.0)

    try:
        with builder.client.driver.session() as session:
            # Update Paper node with stance_label and methodology_quality
            session.run(
                """
                MATCH (p:Paper {title: $title})
                SET p.stance_label = $stance_label,
                    p.methodology_quality = $method_quality,
                    p.methodological_quality = $method_quality
                """,
                title=parsed.title,
                stance_label=stance_label,
                method_quality=method_quality
            )

            # Update Claim nodes with their embeddings
            for claim in claims:
                emb = getattr(claim, "embedding", None)
                if emb is not None:
                    session.run(
                        """
                        MATCH (c:Claim {text: $text})
                        SET c.embedding = $embedding
                        """,
                        text=claim.text,
                        embedding=emb
                    )
    except Exception as exc:
        logger.warning("Graph post-processing failed: %s", exc)


def _build_paper_response(parsed, review, claims) -> PaperAnalysisResponse:
    return PaperAnalysisResponse(
        title=parsed.title,
        abstract=parsed.abstract,
        sections=parsed.sections,
        claims=claims,
        stance=review.stance,
        weaknesses=review.weaknesses,
        evidence_strength=review.evidence_strength,
        methodological_quality=review.method_quality,
        controversy_cluster=review.controversy_cluster,
        citation_role=review.citation_roles,
        semantic_shift_score=review.semantic_shift_score,
        uncertainty=review.uncertainty,
        study_design=review.study_design,
        sample_size=review.sample_size,
    )


def _safe_update_graph(parsed, claims, review):
    try:
        builder = get_graph_builder()
        builder.build_graph(parsed, claims, review)
        _post_process_graph(parsed, claims, review, builder)
    except Exception as exc:
        logger.warning("Graph update failed: %s", exc)


@router.post("/parse", response_model=PaperAnalysisResponse, tags=["Parsing"])
async def parse_paper(request: PaperParseRequest) -> PaperAnalysisResponse:
    parsed = encoder.parse_document(request)
    claims = get_claim_extractor().extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)
    _safe_update_graph(parsed, claims, review)
    return _build_paper_response(parsed, review, claims)


@router.post("/upload", response_model=PaperAnalysisResponse, tags=["Parsing"])
async def upload_paper(file: UploadFile = File(...)) -> PaperAnalysisResponse:
    if not file.filename.lower().endswith((".pdf", ".xml", ".html", ".htm")):
        raise HTTPException(status_code=400, detail="Unsupported file format")

    file_bytes = await file.read()
    record = file_store.save_file(file_bytes, file.filename)

    try:
        parsed = encoder.parse_file(file_bytes, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to parse document: {exc}") from exc

    title = parsed.title or None
    pub_date = getattr(parsed.metadata, "year", None) if hasattr(parsed, "metadata") else None
    if title or pub_date:
        file_store.update_file_metadata(record["id"], title=title, pub_date=str(pub_date) if pub_date else None)

    claims = get_claim_extractor().extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)
    _safe_update_graph(parsed, claims, review)
    response = _build_paper_response(parsed, review, claims)
    file_store.save_analysis(record["id"], json.dumps(response.model_dump()))
    return response


@router.post("/upload-multiple", tags=["Parsing"])
async def upload_multiple(files: List[UploadFile] = File(...)) -> dict:
    """Accept multiple files, save to storage, and run parsing pipeline for each."""
    saved = []
    for f in files:
        if not f.filename.lower().endswith((".pdf", ".xml", ".html", ".htm")):
            continue
        content = await f.read()
        record = file_store.save_file(content, f.filename)

        try:
            parsed = encoder.parse_file(content, f.filename)
            claims = get_claim_extractor().extract_claims(parsed)
            review = agent_coordinator.review_paper(parsed, claims)
            _safe_update_graph(parsed, claims, review)
            base = _build_paper_response(parsed, review, claims)
            record["analysis"] = base.model_dump() if hasattr(base, "model_dump") else (base.dict() if hasattr(base, "dict") else base)
            if parsed.title:
                file_store.update_file_metadata(record["id"], title=parsed.title)
            file_store.save_analysis(record["id"], json.dumps(record["analysis"]))
        except Exception as exc:
            record["analysis_error"] = str(exc)
        saved.append(record)
    return {"uploaded": saved}


@router.post("/analyze/upload/{uid}", tags=["Analysis"])
async def analyze_upload(uid: int) -> dict:
    rec = file_store.get_file_record(uid)
    if not rec:
        raise HTTPException(status_code=404, detail="Upload not found")
    try:
        with open(rec["stored_path"], "rb") as fh:
            content = fh.read()
        parsed = encoder.parse_file(content, rec["filename"])
        claims = get_claim_extractor().extract_claims(parsed)
        review = agent_coordinator.review_paper(parsed, claims)
        base_response = _build_paper_response(parsed, review, claims)
        _safe_update_graph(parsed, claims, review)
        enriched = get_enriched_analyzer().build_enriched_output(
            parsed, claims, review, base_response, graph_client=get_graph_builder().client
        )
        return enriched
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to analyze upload: {exc}") from exc


@router.get("/uploads", tags=["Storage"])
async def list_uploads() -> dict:
    files = file_store.list_files()
    # truncate fields for safety
    for f in files:
        f['filename'] = os.path.basename(f['filename'])
    return {"files": files}


@router.get("/uploads/{uid}/download", tags=["Storage"])
async def download_upload(uid: int):
    rec = file_store.get_file_record(uid)
    if not rec:
        raise HTTPException(status_code=404, detail="File not found")
    path = rec['stored_path']
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not available on disk")
    return FileResponse(path, filename=rec['filename'])


@router.post("/analyze/enriched", tags=["Analysis"])
async def analyze_enriched(request: PaperParseRequest) -> dict:
    """Comprehensive multi-stage analysis with semantic evolution and GNN predictions."""
    parsed = encoder.parse_document(request)
    claims = get_claim_extractor().extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)
    base_response = _build_paper_response(parsed, review, claims)

    _safe_update_graph(parsed, claims, review)
    
    enriched = get_enriched_analyzer().build_enriched_output(
        parsed, claims, review, base_response, graph_client=get_graph_builder().client
    )
    return enriched


@router.post("/analyze/relational", tags=["Analysis"])
async def analyze_relational(request: PaperParseRequest) -> dict:
    """Comprehensive multi-stage analysis with Relational Paper Analysis (RPA)."""
    parsed = encoder.parse_document(request)
    claims = get_claim_extractor().extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)
    base_response = _build_paper_response(parsed, review, claims)

    _safe_update_graph(parsed, claims, review)

    enriched = get_enriched_analyzer().build_enriched_output(
        parsed, claims, review, base_response, graph_client=get_graph_builder().client
    )

    return enriched


@router.get("/graph/controversy-map", tags=["Analysis"])
async def get_controversy_map() -> dict:
    """Retrieve temporal controversy map across indexed papers."""
    try:
        graph_client = get_graph_builder().client
        controversy_map = graph_client.fetch_controversy_map() if getattr(graph_client, "available", False) else None
        if controversy_map and controversy_map.get("total_papers", 0) > 0:
            return controversy_map
    except Exception:
        controversy_map = None

    # Fallback using uploaded file metadata when Neo4j is unavailable.
    files = file_store.list_files(limit=200)
    clusters = {}
    timeline = {}
    total = 0

    for record in files:
        analysis_json = record.get("analysis_json")
        if not analysis_json:
            continue
        try:
            payload = json.loads(analysis_json)
        except Exception:
            continue
        cluster = payload.get("controversy_cluster") or payload.get("analysis", {}).get("controversy_cluster") or 0
        year = record.get("pub_date")
        if year:
            try:
                year = int(str(year)[:4])
            except Exception:
                year = None
        if year is None:
            year = int(record["uploaded_at"][:4]) if record["uploaded_at"] else datetime.utcnow().year

        clusters.setdefault(cluster, []).append(record.get("title") or record.get("filename"))
        timeline.setdefault(year, {"papers": 0, "avg_controversy": 0.0})
        timeline[year]["papers"] += 1
        timeline[year]["avg_controversy"] += float(cluster)
        total += 1

    for year, stats in timeline.items():
        stats["avg_controversy"] = round(stats["avg_controversy"] / max(1, stats["papers"]), 3)

    return {
        "controversy_clusters": clusters,
        "timeline": timeline,
        "total_papers": total,
        "unique_clusters": len(clusters),
    }


@router.post("/visualize", tags=["Visualization"])
async def get_visualization_data(request: PaperParseRequest) -> dict:
    """Generate graph visualization data for frontend rendering."""
    parsed = encoder.parse_document(request)
    claims = get_claim_extractor().extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)

    viz_data = get_enriched_analyzer().build_visualization_data(parsed, claims, review)
    return viz_data


@router.get("/visualize/upload/{uid}", tags=["Visualization"])
async def visualize_upload(uid: int) -> dict:
    """Generate visualization data for a stored upload by id."""
    rec = file_store.get_file_record(uid)
    if not rec:
        raise HTTPException(status_code=404, detail="Upload not found")
    try:
        with open(rec['stored_path'], 'rb') as fh:
            content = fh.read()
        parsed = encoder.parse_file(content, rec['filename'])
        claims = get_claim_extractor().extract_claims(parsed)
        review = agent_coordinator.review_paper(parsed, claims)
        viz = get_enriched_analyzer().build_visualization_data(parsed, claims, review)
        return viz
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to build visualization: {exc}") from exc


@router.get("/health", tags=["Health"])
async def api_health_check() -> dict:
    return {"status": "ok"}
