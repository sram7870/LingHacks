from fastapi import APIRouter, File, HTTPException, UploadFile
from app.schemas import PaperAnalysisResponse, PaperParseRequest
from app.services.agent_review import AgentReviewCoordinator
from app.services.claim_extraction import ClaimExtractor
from app.services.document_encoder import DocumentEncoder
from app.services.graph_builder import KnowledgeGraphBuilder
from app.services.output_layer import EnrichedPaperAnalysis

router = APIRouter(prefix="/api")

encoder = DocumentEncoder()
claim_extractor = ClaimExtractor()
agent_coordinator = AgentReviewCoordinator()
graph_builder = KnowledgeGraphBuilder()
enriched_analyzer = EnrichedPaperAnalysis()


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


@router.post("/parse", response_model=PaperAnalysisResponse, tags=["Parsing"])
async def parse_paper(request: PaperParseRequest) -> PaperAnalysisResponse:
    parsed = encoder.parse_document(request)
    claims = claim_extractor.extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)
    graph_builder.build_graph(parsed, claims, review)
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

    claims = claim_extractor.extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)
    graph_builder.build_graph(parsed, claims, review)
    return _build_paper_response(parsed, review, claims)


@router.post("/analyze/enriched", tags=["Analysis"])
async def analyze_enriched(request: PaperParseRequest) -> dict:
    """Comprehensive multi-stage analysis with semantic evolution and GNN predictions."""
    parsed = encoder.parse_document(request)
    claims = claim_extractor.extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)
    base_response = _build_paper_response(parsed, review, claims)
    
    enriched = enriched_analyzer.build_enriched_output(parsed, claims, review, base_response)
    graph_builder.build_graph(parsed, claims, review)
    return enriched


@router.get("/graph/controversy-map", tags=["Analysis"])
async def get_controversy_map() -> dict:
    """Retrieve temporal controversy map across indexed papers."""
    return {"status": "controversy_map_query_requires_neo4j_backend"}


@router.post("/visualize", tags=["Visualization"])
async def get_visualization_data(request: PaperParseRequest) -> dict:
    """Generate graph visualization data for frontend rendering."""
    parsed = encoder.parse_document(request)
    claims = claim_extractor.extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)
    
    viz_data = enriched_analyzer.build_visualization_data(parsed, claims, review)
    return viz_data
