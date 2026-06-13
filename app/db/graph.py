from neo4j import GraphDatabase
from app.core.config import settings
from app.services.document_encoder import ParsedDocument
from app.schemas import Claim


class KnowledgeGraphClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self):
        self.driver.close()

    def create_paper_node(self, document: ParsedDocument, review_result=None, year: int = 2026) -> None:
        with self.driver.session() as session:
            query = """
            MERGE (p:Paper {title: $title})
            SET p.abstract = $abstract, p.sections = $sections, p.year = $year
            """
            if review_result is not None:
                query += ", p.methodological_quality = $method_quality, p.evidence_strength = $evidence_strength, p.uncertainty = $uncertainty"

            session.run(
                query,
                title=document.title,
                abstract=document.abstract,
                sections=document.sections,
                year=year,
                method_quality=getattr(review_result, "method_quality", None),
                evidence_strength=getattr(review_result, "evidence_strength", None),
                uncertainty=getattr(review_result, "uncertainty", None),
            )

    def create_temporal_node(self, document: ParsedDocument, year: int, embedding_summary: dict) -> None:
        """Create a temporal snapshot node for semantic evolution tracking."""
        with self.driver.session() as session:
            session.run(
                "MERGE (t:TemporalSnapshot {paper_title: $title, year: $year})"
                " SET t.embedding_norm = $emb_norm, t.topic = $topic",
                title=document.title,
                year=year,
                emb_norm=embedding_summary.get("embedding_norm", 0.0),
                topic=embedding_summary.get("topic", "lyme_disease"),
            )
            session.run(
                "MATCH (p:Paper {title: $title}), (t:TemporalSnapshot {paper_title: $title, year: $year})"
                " MERGE (p)-[:TEMPORAL_SNAPSHOT]->(t)",
                title=document.title,
                year=year,
            )

    def detach_all_paper_relationships(self, document: ParsedDocument) -> None:
        with self.driver.session() as session:
            session.run(
                "MATCH (p:Paper {title: $title})-[r]-() DELETE r",
                title=document.title,
            )

    def create_claim_node(self, claim: Claim) -> None:
        with self.driver.session() as session:
            session.run(
                "MERGE (c:Claim {text: $text})"
                " SET c.polarity = $polarity, c.confidence = $confidence",
                text=claim.text,
                polarity=claim.polarity,
                confidence=claim.confidence,
            )

    def create_supports_relationship(self, document: ParsedDocument, claim: Claim) -> None:
        with self.driver.session() as session:
            session.run(
                "MATCH (p:Paper {title: $title}), (c:Claim {text: $text})"
                " MERGE (c)-[:SUPPORTED_BY]->(p)",
                title=document.title,
                text=claim.text,
            )

    def create_method_node(self, document: ParsedDocument, review_result) -> None:
        with self.driver.session() as session:
            session.run(
                "MERGE (m:Method {paperTitle: $title})"
                " SET m.quality = $quality, m.study_design = $study_design, m.sample_size = $sample_size",
                title=document.title,
                quality=getattr(review_result, "method_quality", 0.0),
                study_design=getattr(review_result, "study_design", "Unknown"),
                sample_size=getattr(review_result, "sample_size", 0),
            )

    def create_method_relationship(self, document: ParsedDocument, review_result) -> None:
        with self.driver.session() as session:
            session.run(
                "MATCH (p:Paper {title: $title}), (m:Method {paperTitle: $title})"
                " MERGE (p)-[:USES_METHOD]->(m)",
                title=document.title,
            )

    def create_citation_node(self, citation_text: str) -> str:
        citation_id = citation_text[:200]
        with self.driver.session() as session:
            session.run(
                "MERGE (c:Citation {id: $id})"
                " SET c.text = $text",
                id=citation_id,
                text=citation_text,
            )
        return citation_id

    def create_cites_relationship(self, document: ParsedDocument, citation_id: str) -> None:
        with self.driver.session() as session:
            session.run(
                "MATCH (p:Paper {title: $title}), (c:Citation {id: $id})"
                " MERGE (p)-[:CITES]->(c)",
                title=document.title,
                id=citation_id,
            )
