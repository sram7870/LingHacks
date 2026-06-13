import torch
import numpy as np
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


# Override/wrap claim extractor to generate and attach embeddings to Claims
original_extract_claims = claim_extractor.extract_claims

def wrapped_extract_claims(document) -> list:
    claims = original_extract_claims(document)
    claim_extractor._initialize_model()
    for claim in claims:
        tokens = claim_extractor.tokenizer(claim.text, truncation=True, max_length=128, return_tensors="pt")
        with torch.no_grad():
            output = claim_extractor.model(**tokens)
        if hasattr(output, "pooler_output") and output.pooler_output is not None:
            emb = output.pooler_output
        else:
            emb = output.last_hidden_state[:, 0, :]
        # Convert to a list of floats
        claim.embedding = emb[0].cpu().numpy().tolist()
    return claims

claim_extractor.extract_claims = wrapped_extract_claims


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
    _post_process_graph(parsed, claims, review, graph_builder)
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
    _post_process_graph(parsed, claims, review, graph_builder)
    return _build_paper_response(parsed, review, claims)


@router.post("/analyze/enriched", tags=["Analysis"])
async def analyze_enriched(request: PaperParseRequest) -> dict:
    """Comprehensive multi-stage analysis with semantic evolution and GNN predictions."""
    parsed = encoder.parse_document(request)
    claims = claim_extractor.extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)
    base_response = _build_paper_response(parsed, review, claims)
    
    graph_builder.build_graph(parsed, claims, review)
    _post_process_graph(parsed, claims, review, graph_builder)
    
    enriched = enriched_analyzer.build_enriched_output(
        parsed, claims, review, base_response, graph_client=graph_builder.client
    )
    return enriched


@router.post("/analyze/relational", tags=["Analysis"])
async def analyze_relational(request: PaperParseRequest) -> dict:
    """Comprehensive multi-stage analysis with Relational Paper Analysis (RPA)."""
    parsed = encoder.parse_document(request)
    claims = claim_extractor.extract_claims(parsed)
    review = agent_coordinator.review_paper(parsed, claims)
    base_response = _build_paper_response(parsed, review, claims)
    
    # 1. Run graph builder to insert the paper and claims into Neo4j
    graph_builder.build_graph(parsed, claims, review)
    
    # 2. Run post-processing to update stance_label and claim embeddings
    _post_process_graph(parsed, claims, review, graph_builder)
    
    # 3. Call build_enriched_output, passing the graph_client
    enriched = enriched_analyzer.build_enriched_output(
        parsed, claims, review, base_response, graph_client=graph_builder.client
    )
    
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
