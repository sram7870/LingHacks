from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.services.document_encoder import ParsedDocument


class SemanticSnapshot:
    """A temporal snapshot of semantic embeddings for a document."""

    def __init__(self, year: int, topic: str, embedding: np.ndarray, text: str):
        self.year = year
        self.topic = topic
        self.embedding = embedding
        self.text = text

    def to_dict(self) -> Dict:
        return {
            "year": self.year,
            "topic": self.topic,
            "embedding": self.embedding.tolist() if isinstance(self.embedding, np.ndarray) else self.embedding,
            "text": self.text[:200],
        }


class SemanticEvolution:
    """Tracks semantic and terminological evolution of scientific claims over time."""

    def __init__(self, model_name: str = "intfloat/e5-large-v2"):
        self.model_name = model_name
        self.model = None
        self.snapshots: Dict[str, List[SemanticSnapshot]] = {}

    def _initialize_model(self) -> None:
        if self.model is None:
            try:
                self.model = SentenceTransformer(self.model_name, cache_folder=settings.model_cache_dir)
            except Exception as exc:
                logger.warning("SemanticEvolution model load failed: %s", exc)
                self.model = None

    def embed_document(self, document: ParsedDocument, year: Optional[int] = None) -> np.ndarray:
        """Generate embedding for a document."""
        self._initialize_model()
        text = " ".join([document.abstract or ""] + list(document.sections.values())).strip()
        text = text[:2000]  # Truncate for efficiency
        if self.model is None:
            logger.warning("SemanticEvolution fallback to zero embedding for document: %s", document.title)
            return np.zeros(384, dtype=np.float32)

        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as exc:
            logger.warning("SemanticEvolution encoding failed: %s", exc)
            return np.zeros(384, dtype=np.float32)

    def track_evolution(
        self,
        topic: str,
        document: ParsedDocument,
        year: Optional[int] = None,
    ) -> SemanticSnapshot:
        """Track a document's semantic representation at a given year."""
        if year is None:
            year = datetime.now().year

        embedding = self.embed_document(document, year)
        text = document.abstract or " ".join(document.sections.values())

        snapshot = SemanticSnapshot(year=year, topic=topic, embedding=embedding, text=text)

        if topic not in self.snapshots:
            self.snapshots[topic] = []

        self.snapshots[topic].append(snapshot)
        return snapshot

    def compute_semantic_drift(self, topic: str) -> Dict[str, float]:
        """Compute semantic drift for a topic across years."""
        if topic not in self.snapshots or len(self.snapshots[topic]) < 2:
            return {"drift": 0.0, "years_tracked": len(self.snapshots.get(topic, []))}

        snapshots = sorted(self.snapshots[topic], key=lambda s: s.year)
        drift_scores = []

        for i in range(len(snapshots) - 1):
            curr = snapshots[i].embedding
            next_ = snapshots[i + 1].embedding
            distance = np.linalg.norm(curr - next_)
            drift_scores.append(float(distance))

        avg_drift = np.mean(drift_scores) if drift_scores else 0.0
        return {
            "drift": round(float(avg_drift), 3),
            "years_tracked": len(snapshots),
            "year_range": f"{snapshots[0].year}-{snapshots[-1].year}",
        }

    def find_terminology_evolution(self, topic: str) -> List[Dict]:
        """Track how terminology for a topic evolves over time."""
        if topic not in self.snapshots:
            return []

        snapshots = sorted(self.snapshots[topic], key=lambda s: s.year)
        evolution = []

        for snapshot in snapshots:
            evolution.append(
                {
                    "year": snapshot.year,
                    "topic": snapshot.topic,
                    "snippet": snapshot.text[:150],
                    "embedding_norm": round(float(np.linalg.norm(snapshot.embedding)), 3),
                }
            )

        return evolution

    def get_semantic_neighbors(
        self,
        topic: str,
        year: int,
        k: int = 3,
    ) -> List[Dict]:
        """Find semantically similar documents within a topic and year."""
        if topic not in self.snapshots:
            return []

        target_snapshots = [s for s in self.snapshots[topic] if s.year == year]
        if not target_snapshots:
            return []

        target = target_snapshots[0]
        other_snapshots = [s for s in self.snapshots[topic] if s.year != year]

        if not other_snapshots:
            return []

        similarities = []
        for snapshot in other_snapshots:
            sim = float(np.dot(target.embedding, snapshot.embedding) / (np.linalg.norm(target.embedding) * np.linalg.norm(snapshot.embedding) + 1e-8))
            similarities.append({"year": snapshot.year, "similarity": round(sim, 3), "text": snapshot.text[:150]})

        return sorted(similarities, key=lambda x: x["similarity"], reverse=True)[:k]
