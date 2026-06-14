import logging
import json
from datetime import datetime
import torch

from fastapi import APIRouter, File, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse
from typing import List, Optional
import os
from app.services import file_store
from app.schemas import PaperAnalysisResponse, PaperParseRequest
from app.services.agent_review import AgentReviewCoordinator
from app.services.document_encoder import DocumentEncoder
from app.services.landscape_service import LandscapeService
from app.services.paper_service import PaperService

logger = logging.getLogger(__name__)
router = APIRouter()

# lightweight default instances; heavy components are lazily initialized
encoder = DocumentEncoder()
_claim_extractor = None
agent_coordinator = AgentReviewCoordinator()
_graph_builder = None

landscape_service = LandscapeService()
paper_service = PaperService()


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
    if not getattr(builder.client, "available", False):
        return

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


def _processed_claims_have_embeddings(processed_data: dict) -> bool:
    claims = processed_data.get("claims") or processed_data.get("paper", {}).get("claims") or []
    dict_claims = [claim for claim in claims if isinstance(claim, dict)]
    return bool(dict_claims) and all(claim.get("embedding") for claim in dict_claims)


def _processed_data_is_complete_for_rpa(processed_data: dict) -> bool:
    return (
        bool(processed_data.get("paper"))
        and bool(processed_data.get("analysis"))
        and _processed_claims_have_embeddings(processed_data)
    )


def _process_registered_paper(paper_id: str, paper_info: dict) -> dict:
    with open(paper_info["filepath"], "rb") as f:
        content = f.read()
    parsed = encoder.parse_file(content, paper_info["filename"])
    if not parsed.title:
        parsed.title = paper_info.get("title") or paper_info["filename"]
    claims = get_claim_extractor().extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)
    _safe_update_graph(parsed, claims, review)
    base_response = _build_paper_response(parsed, review, claims)
    enriched = get_enriched_analyzer().build_enriched_output(
        parsed, claims, review, base_response, graph_client=get_graph_builder().client
    )
    paper_service.save_processed_output(paper_id, enriched)
    return enriched


@router.post("/parse", response_model=PaperAnalysisResponse, tags=["Parsing"])
async def parse_paper(request: PaperParseRequest) -> PaperAnalysisResponse:
    parsed = encoder.parse_document(request)
    # Ensure title is present
    if not parsed.title:
        parsed.title = "Untitled Paper"

    claims = get_claim_extractor().extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)
    _safe_update_graph(parsed, claims, review)
    return _build_paper_response(parsed, review, claims)


@router.post("/upload", response_model=PaperAnalysisResponse, tags=["Parsing"])
async def upload_paper(file: UploadFile = File(...), landscape_id: Optional[str] = Query(None)) -> PaperAnalysisResponse:
    if not file.filename.lower().endswith((".pdf", ".xml", ".html", ".htm")):
        raise HTTPException(status_code=400, detail="Unsupported file format")
    if landscape_id and not landscape_service.get_landscape(landscape_id):
        raise HTTPException(status_code=404, detail="Landscape not found")

    file_bytes = await file.read()

    try:
        parsed = encoder.parse_file(file_bytes, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to parse document: {exc}") from exc

    if not parsed.title:
        parsed.title = file.filename

    paper_id = paper_service.register_paper(
        title=parsed.title,
        filename=file.filename,
        file_bytes=file_bytes,
        year=getattr(parsed.metadata, "year", None) if hasattr(parsed, "metadata") else None
    )

    if landscape_id and not landscape_service.add_paper_to_landscape(landscape_id, paper_id):
        raise HTTPException(status_code=404, detail="Landscape not found")

    claims = get_claim_extractor().extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)
    _safe_update_graph(parsed, claims, review)
    response = _build_paper_response(parsed, review, claims)
    
    enriched = get_enriched_analyzer().build_enriched_output(
        parsed, claims, review, response, graph_client=get_graph_builder().client
    )
    paper_service.save_processed_output(paper_id, enriched)
    
    return response


@router.post("/upload-multiple", tags=["Parsing"])
async def upload_multiple(files: List[UploadFile] = File(...), landscape_id: Optional[str] = Query(None)) -> dict:
    """Accept multiple files, save to storage, and run parsing pipeline for each."""
    if landscape_id and not landscape_service.get_landscape(landscape_id):
        raise HTTPException(status_code=404, detail="Landscape not found")

    saved = []
    for f in files:
        if not f.filename.lower().endswith((".pdf", ".xml", ".html", ".htm")):
            continue
        content = await f.read()
        record = file_store.save_file(content, f.filename)

        try:
            parsed = encoder.parse_file(content, f.filename)
            
            # Ensure title consistency
            if not parsed.title:
                parsed.title = f.filename

            paper_id = paper_service.register_paper(
                title=parsed.title,
                filename=f.filename,
                file_bytes=content,
                year=getattr(parsed.metadata, "year", None) if hasattr(parsed, "metadata") else None
            )

            if landscape_id and not landscape_service.add_paper_to_landscape(landscape_id, paper_id):
                raise HTTPException(status_code=404, detail="Landscape not found")

            claims = get_claim_extractor().extract_claims(parsed)
            review = agent_coordinator.review_paper(parsed, claims)
            _safe_update_graph(parsed, claims, review)
            base = _build_paper_response(parsed, review, claims)
            
            enriched = get_enriched_analyzer().build_enriched_output(
                parsed, claims, review, base, graph_client=get_graph_builder().client
            )
            paper_service.save_processed_output(paper_id, enriched)

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
async def get_controversy_map(landscape_id: Optional[str] = Query(None)) -> dict:
    """Retrieve temporal controversy map, optionally filtered by landscape."""
    paper_titles = None
    if landscape_id:
        landscape = landscape_service.get_landscape(landscape_id)
        if landscape:
            paper_titles = []
            for pid in landscape["paper_ids"]:
                p = paper_service.get_paper(pid)
                if p:
                    paper_titles.append(p["title"])

    try:
        graph_client = get_graph_builder().client
        if paper_titles is not None:
             # Assume fetch_controversy_map supports filtering by titles
             controversy_map = graph_client.fetch_controversy_map(paper_titles=paper_titles) if getattr(graph_client, "available", False) else None
        else:
             controversy_map = graph_client.fetch_controversy_map() if getattr(graph_client, "available", False) else None
             
        if controversy_map and controversy_map.get("total_papers", 0) > 0:
            return controversy_map
    except Exception:
        controversy_map = None

    # Fallback using paper_service when Neo4j is unavailable or fails.
    papers = paper_service.list_papers()
    if paper_titles is not None:
        papers = [p for p in papers if p["title"] in paper_titles]
    else:
        # If no landscape, also fallback to file_store for legacy compatibility if paper_service is empty
        if not papers:
            files = file_store.list_files(limit=200)
            # Map file_store records to a similar shape for fallback logic
            papers = [{"title": f.get("title") or f.get("filename"), "processed_path": f.get("stored_path") + ".analysis.json"} for f in files]

    clusters = {}
    timeline = {}
    total = 0

    for record in papers:
        processed_path = record.get("processed_path")
        # Special case for legacy file_store fallback
        if not processed_path and "id" in record:
             # Try to find analysis in file_store
             f_rec = file_store.get_file_record(record["id"])
             if f_rec and f_rec.get("analysis_json"):
                  try:
                      payload = json.loads(f_rec["analysis_json"])
                      # continue with payload...
                  except Exception: continue
             else: continue
        elif processed_path and os.path.exists(processed_path):
            try:
                with open(processed_path, "r") as f:
                    payload = json.load(f)
            except Exception:
                continue
        else:
            continue
            
        cluster = payload.get("controversy_cluster") or payload.get("analysis", {}).get("controversy_cluster") or 0
        if cluster is None: cluster = 0
        
        year = record.get("year") or datetime.now().year

        clusters.setdefault(int(cluster), []).append(record.get("title") or record.get("filename"))
        timeline.setdefault(int(year), {"papers": 0, "avg_controversy": 0.0})
        timeline[int(year)]["papers"] += 1
        timeline[int(year)]["avg_controversy"] += float(cluster)
        total += 1

    for year, stats in timeline.items():
        stats["avg_controversy"] = round(stats["avg_controversy"] / max(1, stats["papers"]), 3)

    return {
        "controversy_clusters": clusters,
        "timeline": timeline,
        "total_papers": total,
        "unique_clusters": len(clusters),
    }


# --- Landscape Management Endpoints ---

@router.get("/landscapes", tags=["Landscapes"])
async def list_landscapes():
    return landscape_service.list_landscapes()


@router.post("/landscapes", tags=["Landscapes"])
async def create_landscape(name: str = Query(...), description: str = Query("")):
    return landscape_service.create_landscape(name, description)


@router.get("/landscapes/{landscape_id}", tags=["Landscapes"])
async def get_landscape(landscape_id: str):
    landscape = landscape_service.get_landscape(landscape_id)
    if not landscape:
        raise HTTPException(status_code=404, detail="Landscape not found")
    return landscape


@router.delete("/landscapes/{landscape_id}", tags=["Landscapes"])
async def delete_landscape(landscape_id: str):
    landscape_service.delete_landscape(landscape_id)
    return {"status": "deleted"}


@router.post("/landscapes/{landscape_id}/papers", tags=["Landscapes"])
async def add_paper_to_landscape(landscape_id: str, paper_id: str = Query(...)):
    if not paper_service.get_paper(paper_id):
        raise HTTPException(status_code=404, detail="Paper not found")
    if not landscape_service.add_paper_to_landscape(landscape_id, paper_id):
        raise HTTPException(status_code=404, detail="Landscape not found")
    return landscape_service.get_landscape(landscape_id)


@router.delete("/landscapes/{landscape_id}/papers/{paper_id}", tags=["Landscapes"])
async def remove_paper_from_landscape(landscape_id: str, paper_id: str):
    if not landscape_service.remove_paper_from_landscape(landscape_id, paper_id):
        raise HTTPException(status_code=404, detail="Landscape not found")
    return landscape_service.get_landscape(landscape_id)


@router.post("/landscapes/{landscape_id}/analyze", tags=["Landscapes"])
async def analyze_landscape(landscape_id: str):
    """Trigger existing analysis pipeline for all papers in a landscape."""
    landscape = landscape_service.get_landscape(landscape_id)
    if not landscape:
        raise HTTPException(status_code=404, detail="Landscape not found")
    
    # 1. Retrieve all papers in landscape
    papers = []
    for pid in landscape["paper_ids"]:
        p = paper_service.get_paper(pid)
        if p:
            papers.append(p)
    
    # 2. Ensure all papers are processed and in the graph
    for p in papers:
        needs_processing = not p.get("processed_path") or not os.path.exists(p["processed_path"])
        if not needs_processing:
            try:
                with open(p["processed_path"], "r") as f:
                    needs_processing = not _processed_data_is_complete_for_rpa(json.load(f))
            except Exception:
                needs_processing = True

        if needs_processing:
            try:
                _process_registered_paper(p["paper_id"], p)
            except Exception as exc:
                logger.warning("Failed to re-process paper %s during landscape analysis: %s", p["paper_id"], exc)

    # 3. Update landscape metadata
    landscape_service.update_landscape(
        landscape_id,
        last_analysis=datetime.now().isoformat(),
        graph_built=True
    )
    
    # 4. Return the controversy map specifically for this landscape
    return await get_controversy_map(landscape_id=landscape_id)


@router.post("/rpa/upload", tags=["RPA"])
async def rpa_upload_paper(file: UploadFile = File(...), landscape_id: Optional[str] = Query(None)) -> dict:
    """Lightweight upload: registers the paper and stores the file without adding it to the comparison corpus."""
    if not file.filename.lower().endswith((".pdf", ".xml", ".html", ".htm")):
        raise HTTPException(status_code=400, detail="Unsupported file format")
    if landscape_id and not landscape_service.get_landscape(landscape_id):
        raise HTTPException(status_code=404, detail="Landscape not found")

    file_bytes = await file.read()
    
    # Quick metadata extraction if possible, otherwise use filename
    try:
        # We do a 'light' parse just for the title to show in UI
        # If it fails or is slow, we fallback to filename
        parsed = encoder.parse_file(file_bytes, file.filename)
        title = parsed.title or file.filename
    except Exception:
        title = file.filename

    # Store paper persistently in the registry
    paper_id = paper_service.register_paper(
        title=title,
        filename=file.filename,
        file_bytes=file_bytes,
        deduplicate=False
    )

    return {"paper_id": paper_id, "title": title}


@router.get("/rpa/analyze", tags=["RPA"])
async def rpa_analyze_paper(paper_id: str = Query(...), landscape_id: Optional[str] = Query(None)):
    """
    Run the full analytical pipeline and RPA on a stored paper.
    Heavy processing happens here.
    """
    # 1. Fast-fail: Check landscape size before any heavy work
    landscape_paper_titles = None
    if landscape_id:
        landscape = landscape_service.get_landscape(landscape_id)
        if not landscape:
            raise HTTPException(status_code=404, detail="Landscape not found")
        
        if len(landscape.get("paper_ids", [])) < 2:
            return {
                "rpa": {
                    "corpus_too_small": True,
                    "message": f"Landscape '{landscape['name']}' has only {len(landscape['paper_ids'])} paper(s). Relational analysis requires at least 2 papers for comparison."
                },
                "paper": {"title": "Insufficient Data"}
            }
        
        landscape_paper_titles = []
        for pid in landscape["paper_ids"]:
            p = paper_service.get_paper(pid)
            if p:
                landscape_paper_titles.append(p["title"])
    else:
        # Check global corpus size in Neo4j (fast query)
        total_global = 0
        try:
            with get_graph_builder().client.driver.session() as session:
                res = session.run("MATCH (p:Paper) RETURN count(p) AS count")
                total_global = res.single()["count"]
        except Exception:
            pass
            
        if total_global < 2:
            return {
                "rpa": {
                    "corpus_too_small": True,
                    "message": "The global library contains fewer than 2 papers. Relational analysis requires a comparison pool. Please upload more papers to the homepage first."
                },
                "paper": {"title": "Insufficient Data"}
            }

    # 2. Retrieve paper info
    paper_info = paper_service.get_paper(paper_id)
    if not paper_info:
        raise HTTPException(status_code=404, detail="Paper not found in registry")
    
    # 3. Check if paper needs full processing
    processed_path = paper_info.get("processed_path")
    should_process = not processed_path or not os.path.exists(processed_path)
    processed_data = None
    if not should_process:
        with open(processed_path, "r") as f:
            processed_data = json.load(f)
        should_process = not _processed_data_is_complete_for_rpa(processed_data)

    if should_process:
        try:
            processed_data = _process_registered_paper(paper_id, paper_info)
        except Exception as exc:
            logger.error("Full processing failed for paper %s: %s", paper_id, exc)
            raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    # 4. Run Relational Analysis (Scoped)
    from app.services.relational_analysis import RelationalAnalyzer
    analyzer = RelationalAnalyzer(
        graph_client=get_graph_builder().client,
        gnn_model=get_enriched_analyzer().gnn_builder.gnn,
        evolution_tracker=get_enriched_analyzer().semantic_evolution
    )
    
    # Re-construct claim objects
    from app.schemas import Claim
    claims_objs = [Claim(**c) for c in processed_data.get("claims", [])]
    
    # Determine stance
    stance_dict = processed_data["analysis"].get("stance", {})
    stance_label = "neutral"
    if stance_dict:
        max_key = max(stance_dict, key=lambda k: stance_dict.get(k, 0.0))
        if max_key == "PTLDS": stance_label = "supporting"
        elif max_key == "CLD": stance_label = "opposing"

    # Run actual relational cross-referencing
    rpa_result = analyzer.analyze(
        paper_id=paper_id,
        paper_title=processed_data["paper"]["title"],
        paper_year=processed_data["paper"]["year"],
        extracted_claims=claims_objs,
        methodology_quality=processed_data["analysis"]["methodological_quality"],
        stance_label=stance_label,
        landscape_paper_titles=landscape_paper_titles
    )
    
    return {
        "paper": processed_data["paper"],
        "rpa": rpa_result
    }


@router.post("/visualize", tags=["Visualization"])
async def get_visualization_data(request: PaperParseRequest) -> dict:
    """Generate graph visualization data for frontend rendering."""
    parsed = encoder.parse_document(request)
    claims = get_claim_extractor().extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)

    viz_data = get_enriched_analyzer().build_visualization_data(parsed, claims, review)
    return viz_data


@router.get("/visualize/paper/{paper_id}", tags=["Visualization"])
async def visualize_paper(paper_id: str) -> dict:
    """Generate visualization data for a registered paper."""
    paper = paper_service.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    try:
        with open(paper['filepath'], 'rb') as fh:
            content = fh.read()
        parsed = encoder.parse_file(content, paper['filename'])
        claims = get_claim_extractor().extract_claims(parsed)
        review = agent_coordinator.review_paper(parsed, claims)
        viz = get_enriched_analyzer().build_visualization_data(parsed, claims, review)
        return viz
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to build visualization: {exc}") from exc


@router.get("/health", tags=["Health"])
async def api_health_check() -> dict:
    return {"status": "ok"}
