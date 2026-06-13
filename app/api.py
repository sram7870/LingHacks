import logging
import torch
import numpy as np

from fastapi import APIRouter, File, HTTPException, UploadFile
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
        evidence_strength=review.evidence_strength,
        methodological_quality=review.method_quality,
        controversy_cluster=review.controversy_cluster,
        citation_role=review.citation_roles,
        semantic_shift_score=review.semantic_shift_score,
        uncertainty=review.uncertainty,
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
    try:
        parsed = encoder.parse_file(file_bytes, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to parse document: {exc}") from exc

    claims = get_claim_extractor().extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)
    _safe_update_graph(parsed, claims, review)
    return _build_paper_response(parsed, review, claims)


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
        controversy_map = get_graph_builder().client.fetch_controversy_map()
        return controversy_map
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to retrieve controversy map: {exc}") from exc


@router.post("/visualize", tags=["Visualization"])
async def get_visualization_data(request: PaperParseRequest) -> dict:
    """Generate graph visualization data for frontend rendering."""
    parsed = encoder.parse_document(request)
    claims = get_claim_extractor().extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)

    viz_data = get_enriched_analyzer().build_visualization_data(parsed, claims, review)
    return viz_data


@router.get("/health", tags=["Health"])
async def api_health_check() -> dict:
    return {"status": "ok"}
