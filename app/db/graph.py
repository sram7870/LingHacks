import logging
from datetime import datetime
from typing import List, Optional
from app.core.config import settings
from app.services.document_encoder import ParsedDocument
from app.schemas import Claim

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import Neo4jError
    NEO4J_AVAILABLE = True
except ImportError:
    GraphDatabase = None
    Neo4jError = Exception
    NEO4J_AVAILABLE = False


class KnowledgeGraphClient:
    def __init__(self):
        self.driver = None
        if NEO4J_AVAILABLE:
            self._connect()
        else:
            logger.warning("Neo4j python driver not installed; graph persistence disabled.")

    def _connect(self) -> None:
        try:
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                connection_timeout=5.0,
                max_connection_lifetime=60,
                max_transaction_retry_time=5.0,
            )
            with self.driver.session() as session:
                session.run("RETURN 1")
        except Exception as exc:
            logger.warning("Unable to connect to Neo4j at %s: %s", settings.neo4j_uri, exc)
            self.driver = None

    def close(self):
        if self.driver is not None:
            self.driver.close()

    @property
    def available(self) -> bool:
        return NEO4J_AVAILABLE and self.driver is not None

    def _run(self, query: str, **params):
        if not self.available:
            logger.debug("Neo4j unavailable, skipping query: %s", query)
            return None
        try:
            with self.driver.session() as session:
                return session.run(query, **params)
        except Neo4jError as exc:
            logger.warning("Neo4j query failed: %s", exc)
            return None

    def create_paper_node(self, document: ParsedDocument, review_result=None, year: int = 2026) -> None:
        if not self.available:
            return

        query = """
            MERGE (p:Paper {title: $title})
            SET p.abstract = $abstract, p.sections = $sections, p.year = $year
            """
        if review_result is not None:
            query += ", p.methodological_quality = $method_quality, p.evidence_strength = $evidence_strength, p.uncertainty = $uncertainty, p.controversy_cluster = $controversy_cluster"

        self._run(
            query,
            title=document.title,
            abstract=document.abstract,
            sections=document.sections,
            year=year,
            method_quality=getattr(review_result, "method_quality", None),
            evidence_strength=getattr(review_result, "evidence_strength", None),
            uncertainty=getattr(review_result, "uncertainty", None),
            controversy_cluster=getattr(review_result, "controversy_cluster", None),
        )

    def create_temporal_node(self, document: ParsedDocument, year: int, embedding_summary: dict) -> None:
        if not self.available:
            return
        self._run(
            "MERGE (t:TemporalSnapshot {paper_title: $title, year: $year})"
            " SET t.embedding_norm = $emb_norm, t.topic = $topic",
            title=document.title,
            year=year,
            emb_norm=embedding_summary.get("embedding_norm", 0.0),
            topic=embedding_summary.get("topic", "lyme_disease"),
        )
        self._run(
            "MATCH (p:Paper {title: $title}), (t:TemporalSnapshot {paper_title: $title, year: $year})"
            " MERGE (p)-[:TEMPORAL_SNAPSHOT]->(t)",
            title=document.title,
            year=year,
        )

    def detach_all_paper_relationships(self, document: ParsedDocument) -> None:
        if not self.available:
            return
        self._run(
            "MATCH (p:Paper {title: $title})-[r]-() DELETE r",
            title=document.title,
        )

    def create_claim_node(self, claim: Claim) -> None:
        if not self.available:
            return
        self._run(
            "MERGE (c:Claim {text: $text})"
            " SET c.polarity = $polarity, c.confidence = $confidence",
            text=claim.text,
            polarity=claim.polarity,
            confidence=claim.confidence,
        )

    def create_supports_relationship(self, document: ParsedDocument, claim: Claim) -> None:
        if not self.available:
            return
        self._run(
            "MATCH (p:Paper {title: $title}), (c:Claim {text: $text})"
            " MERGE (c)-[:SUPPORTED_BY]->(p)",
            title=document.title,
            text=claim.text,
        )

    def create_method_node(self, document: ParsedDocument, review_result) -> None:
        if not self.available:
            return
        self._run(
            "MERGE (m:Method {paperTitle: $title})"
            " SET m.quality = $quality, m.study_design = $study_design, m.sample_size = $sample_size",
            title=document.title,
            quality=getattr(review_result, "method_quality", 0.0),
            study_design=getattr(review_result, "study_design", "Unknown"),
            sample_size=getattr(review_result, "sample_size", 0),
        )

    def create_method_relationship(self, document: ParsedDocument, review_result) -> None:
        if not self.available:
            return
        self._run(
            "MATCH (p:Paper {title: $title}), (m:Method {paperTitle: $title})"
            " MERGE (p)-[:USES_METHOD]->(m)",
            title=document.title,
        )

    def create_citation_node(self, citation_text: str) -> str:
        citation_id = citation_text[:200]
        if not self.available:
            return citation_id
        self._run(
            "MERGE (c:Citation {id: $id})"
            " SET c.text = $text",
            id=citation_id,
            text=citation_text,
        )
        return citation_id

    def create_cites_relationship(self, document: ParsedDocument, citation_id: str) -> None:
        if not self.available:
            return
        self._run(
            "MATCH (p:Paper {title: $title}), (c:Citation {id: $id})"
            " MERGE (p)-[:CITES]->(c)",
            title=document.title,
            id=citation_id,
        )

    def fetch_controversy_map(self, paper_titles: Optional[List[str]] = None) -> dict:
        if not self.available:
            return {
                "controversy_clusters": {},
                "timeline": {},
                "total_papers": 0,
                "unique_clusters": 0,
            }

        if paper_titles:
            query = "MATCH (p:Paper) WHERE p.title IN $titles RETURN p.title AS title, p.year AS year, p.controversy_cluster AS cluster ORDER BY p.year, p.title"
            result = self._run(query, titles=paper_titles)
        else:
            query = "MATCH (p:Paper) RETURN p.title AS title, p.year AS year, p.controversy_cluster AS cluster ORDER BY p.year, p.title"
            result = self._run(query)

        if result is None:
            return {
                "controversy_clusters": {},
                "timeline": {},
                "total_papers": 0,
                "unique_clusters": 0,
            }

        rows = [record.data() for record in result]

        controversy_clusters = {}
        timeline = {}
        total_papers = len(rows)

        for row in rows:
            cluster_id = row.get("cluster") if row.get("cluster") is not None else 0
            title = row.get("title") or "Untitled"
            year = row.get("year") or datetime.now().year

            if cluster_id not in controversy_clusters:
                controversy_clusters[cluster_id] = []
            controversy_clusters[cluster_id].append(title)

            if year not in timeline:
                timeline[year] = {"papers": 0, "avg_controversy": 0.0}
            timeline[year]["papers"] += 1
            timeline[year]["avg_controversy"] += float(cluster_id)

        for year, stats in timeline.items():
            if stats["papers"]:
                stats["avg_controversy"] = round(stats["avg_controversy"] / stats["papers"], 3)

        return {
            "controversy_clusters": controversy_clusters,
            "timeline": timeline,
            "total_papers": total_papers,
            "unique_clusters": len(controversy_clusters),
        }
