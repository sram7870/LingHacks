import logging

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
    return _claim_extractor


def get_enriched_analyzer():
    global _enriched_analyzer
    if _enriched_analyzer is None:
        from app.services.output_layer import EnrichedPaperAnalysis

        _enriched_analyzer = EnrichedPaperAnalysis()
    return _enriched_analyzer


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
        get_graph_builder().build_graph(parsed, claims, review)
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

    enriched = get_enriched_analyzer().build_enriched_output(parsed, claims, review, base_response)
    _safe_update_graph(parsed, claims, review)
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
