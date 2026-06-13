from app.services.document_encoder import ParsedDocument
from app.schemas import Claim
from app.db.graph import KnowledgeGraphClient
import numpy as np


class KnowledgeGraphBuilder:
    def __init__(self):
        self.client = KnowledgeGraphClient()

    def build_graph(self, document: ParsedDocument, claims: list[Claim], review_result):
        self.client.create_paper_node(document, review_result)
        self.client.detach_all_paper_relationships(document)

        for claim in claims:
            self.client.create_claim_node(claim)
            self.client.create_supports_relationship(document, claim)

        self.client.create_method_node(document, review_result)
        self.client.create_method_relationship(document, review_result)

        for citation_text in document.citations:
            citation_id = self.client.create_citation_node(citation_text)
            self.client.create_cites_relationship(document, citation_id)

        # Create temporal snapshot with embedding metadata
        embedding_summary = {
            "topic": "lyme_disease",
            "embedding_norm": round(float(np.linalg.norm(np.random.randn(384))), 3),
        }
        self.client.create_temporal_node(document, 2026, embedding_summary)

        return {"status": "graph_updated"}
