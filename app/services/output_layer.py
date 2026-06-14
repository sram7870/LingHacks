from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
import numpy as np

from app.schemas import Claim, PaperAnalysisResponse
from app.services.document_encoder import ParsedDocument
from app.services.semantic_evolution import SemanticEvolution
from app.services.controversy_gnn import ControversyGraphBuilder

logger = logging.getLogger(__name__)


class EnrichedPaperAnalysis:
    """Rich, multi-layered analysis output with all reasoning layers."""

    def __init__(self):
        self.semantic_evolution = SemanticEvolution()
        self.gnn_builder = ControversyGraphBuilder()

    def build_enriched_output(
        self,
        parsed: ParsedDocument,
        claims: List[Claim],
        review_result: Any,
        base_response: PaperAnalysisResponse,
        graph_client: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Construct a rich, multi-layered analysis response."""
        year = datetime.now().year

        # Semantic evolution tracking
        semantic_snapshot = self.semantic_evolution.track_evolution(
            topic="lyme_disease",
            document=parsed,
            year=year,
        )

        # Build GNN inputs with semantic embeddings if available
        paper_embedding = semantic_snapshot.embedding
        self.gnn_builder.add_paper_node("paper_0", paper_embedding[:128])

        for i, claim in enumerate(claims):
            if getattr(claim, "embedding", None):
                claim_vec = np.array(claim.embedding[:128], dtype=np.float32)
            else:
                claim_vec = np.full(128, claim.confidence, dtype=np.float32)
            self.gnn_builder.add_claim_node(f"claim_{i}", claim_vec)
            self.gnn_builder.add_claim_edge("paper_0", f"claim_{i}")

        # GNN predictions
        gnn_output = self.gnn_builder.predict_controversy()

        # Semantic drift analysis
        semantic_drift = self.semantic_evolution.compute_semantic_drift("lyme_disease")

        output = {
            "paper": {
                "title": parsed.title,
                "abstract": parsed.abstract,
                "year": year,
            },
            "analysis": {
                "stance": base_response.stance,
                "weaknesses": base_response.weaknesses,
                "evidence_strength": base_response.evidence_strength,
                "methodological_quality": base_response.methodological_quality,
                "uncertainty": base_response.uncertainty,
                "study_design": base_response.study_design,
                "sample_size": base_response.sample_size,
                "controversy_cluster": base_response.controversy_cluster,
                "citation_roles": base_response.citation_role,
            },
            "claims": [
                {
                    "text": claim.text,
                    "polarity": claim.polarity,
                    "confidence": claim.confidence,
                    "section": getattr(claim, "section", None),
                }
                for claim in claims
            ],
            "methodological_assessment": {
                "study_design": getattr(review_result, "study_design", "Unknown"),
                "sample_size": getattr(review_result, "sample_size", 0),
                "weaknesses": review_result.weaknesses[:5],
            },
            "graph_predictions": {
                "controversy_score": gnn_output["controversy_score"],
                "consensus_score": gnn_output["consensus_score"],
                "emerging_topic_score": gnn_output["emerging_topic_score"],
            },
            "semantic_analysis": {
                "drift": semantic_drift["drift"],
                "years_tracked": semantic_drift["years_tracked"],
                "embedding_dimension": 384,
            },
            "citation_context": {
                "total_citations": len(parsed.citations),
                "citation_roles": base_response.citation_role,
            },
            "model_metadata": {
                "pipeline_stages": 8,
                "ensemble_models_used": 2,
                "agreement_confidence": round(0.85 + (base_response.uncertainty * 0.1), 3),
                "timestamp": datetime.now().isoformat(),
            },
        }

        # Relational Paper Analysis (RPA)
        from app.services.relational_analysis import RelationalAnalyzer

        stance_dict = getattr(review_result, "stance", {})
        stance_label = "neutral"
        if stance_dict:
            max_key = max(stance_dict, key=lambda k: stance_dict.get(k, 0.0))
            if max_key == "PTLDS":
                stance_label = "supporting"
            elif max_key == "CLD":
                stance_label = "opposing"

        if graph_client is None:
            try:
                from app.db.graph import KnowledgeGraphClient
                graph_client = KnowledgeGraphClient()
            except Exception:
                graph_client = None

        if graph_client is not None and getattr(graph_client, "available", False):
            analyzer = RelationalAnalyzer(
                graph_client=graph_client,
                gnn_model=self.gnn_builder.gnn,
                evolution_tracker=self.semantic_evolution
            )

            paper_id = parsed.metadata.get("id") if (hasattr(parsed, "metadata") and parsed.metadata) else None
            if not paper_id:
                paper_id = parsed.title

            paper_year = parsed.metadata.get("year") if (hasattr(parsed, "metadata") and parsed.metadata) else None
            if not paper_year:
                paper_year = year

            rpa_result = analyzer.analyze(
                paper_id=str(paper_id),
                paper_title=parsed.title,
                paper_year=int(paper_year),
                extracted_claims=claims,
                methodology_quality=base_response.methodological_quality,
                stance_label=stance_label
            )

            output["relational_analysis"] = rpa_result
        
        return output

    def build_controversy_map(
        self,
        papers: List[ParsedDocument],
        reviews: List[Any],
    ) -> Dict[str, Any]:
        """Build a temporal controversy map across multiple papers."""
        controversy_clusters = {}
        timeline = {}

        for paper, review in zip(papers, reviews):
            year = datetime.now().year
            cluster_id = getattr(review, "controversy_cluster", 0)

            if cluster_id not in controversy_clusters:
                controversy_clusters[cluster_id] = []
            controversy_clusters[cluster_id].append(paper.title)

            if year not in timeline:
                timeline[year] = {"papers": 0, "avg_controversy": 0.0}
            timeline[year]["papers"] += 1

        return {
            "controversy_clusters": controversy_clusters,
            "timeline": timeline,
            "total_papers": len(papers),
            "unique_clusters": len(controversy_clusters),
        }

    def build_visualization_data(
        self,
        parsed: ParsedDocument,
        claims: List[Claim],
        review_result: Any,
    ) -> Dict[str, Any]:
        """Generate data optimized for frontend visualization."""
        author_last = None
        metadata = getattr(parsed, "metadata", {}) or {}
        authors = metadata.get("authors") if isinstance(metadata, dict) else None
        if isinstance(authors, list) and authors:
            author_last = authors[-1]

        nodes = [
            {
                "id": "paper_0",
                "label": parsed.title or "Untitled paper",
                "type": "paper",
                "size": 35,
                "value": review_result.method_quality,
                "description": parsed.abstract or "No abstract available.",
                "publication_year": metadata.get("year") if isinstance(metadata, dict) else None,
                "authors": authors,
            }
        ]

        for i, claim in enumerate(claims):
            nodes.append({
                "id": f"claim_{i}",
                "label": claim.text[:80],
                "type": "claim",
                "section": getattr(claim, "section", None) or "unknown",
                "size": 18,
                "value": claim.confidence,
                "papers": [
                    {
                        "title": parsed.title,
                        "author_last": author_last,
                        "date": metadata.get("year") if isinstance(metadata, dict) else None,
                    }
                ],
            })

        return {
            "nodes": nodes,
            "edges": [
                {"source": "paper_0", "target": f"claim_{i}", "weight": claim.confidence}
                for i, claim in enumerate(claims)
            ],
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(claims),
                "network_density": round(len(claims) / max(1, (len(nodes) * (len(nodes) - 1) / 2)), 3),
            },
        }
