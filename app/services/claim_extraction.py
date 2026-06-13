import re
from operator import itemgetter
from typing import List

from app.core.config import settings
from app.schemas import Claim
from app.services.document_encoder import ParsedDocument


class ClaimExtractor:
    def __init__(self):
        self.model_name = "allenai/scibert_scivocab_uncased"
        self.tokenizer = None
        self.model = None
        self._torch = None
        self._sigmoid = None

    def _initialize_model(self) -> None:
        if self.tokenizer is None or self.model is None:
            try:
                from transformers import AutoModel, AutoTokenizer
                import torch
                from torch.nn.functional import sigmoid as _sigmoid
            except Exception as exc:
                raise RuntimeError(f"Required ML dependencies are not installed: {exc}") from exc

            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, cache_dir=settings.model_cache_dir)
            self.model = AutoModel.from_pretrained(self.model_name, cache_dir=settings.model_cache_dir)
            self.model.eval()
            self._torch = torch
            self._sigmoid = _sigmoid

    def extract_claims(self, document: ParsedDocument) -> List[Claim]:
        self._initialize_model()
        candidates = self._collect_candidates(document)
        scored = []
        for sentence in candidates:
            score = self._score_sentence(sentence)
            polarity = "support" if score >= 0.5 else "neutral"
            scored.append({"sentence": sentence, "score": score, "polarity": polarity})

        top_claims = sorted(scored, key=itemgetter("score"), reverse=True)[:3]
        return [
            Claim(text=item["sentence"], polarity=item["polarity"], confidence=round(item["score"], 3))
            for item in top_claims
            if item["score"] > 0.2
        ]

    def _collect_candidates(self, document: ParsedDocument) -> List[str]:
        sections = [document.abstract] + list(document.sections.values())
        text = "\n".join([section for section in sections if section])
        return self._split_sentences(text)

    def _split_sentences(self, text: str) -> List[str]:
        sentences = re.split(r"(?<=[\.\?\!])\s+", text)
        return [sentence.strip() for sentence in sentences if len(sentence.strip()) > 30]

    def _score_sentence(self, sentence: str) -> float:
        tokens = self.tokenizer(sentence, truncation=True, max_length=128, return_tensors="pt")
        if self._torch is None or self._sigmoid is None:
            # Should not happen if _initialize_model has run
            raise RuntimeError("Torch dependencies are not initialized")

        with self._torch.no_grad():
            output = self.model(**tokens)

        embedding = None
        if hasattr(output, "pooler_output") and output.pooler_output is not None:
            embedding = output.pooler_output
        else:
            embedding = output.last_hidden_state[:, 0, :]

        model_score = float(self._sigmoid(embedding.mean()))
        keyword_bonus = self._keyword_strength(sentence)
        return min(1.0, max(0.0, 0.25 * model_score + 0.75 * keyword_bonus))

    def _keyword_strength(self, sentence: str) -> float:
        keywords = [
            "improve",
            "reduce",
            "increase",
            "associated",
            "significant",
            "evidence",
            "study",
            "patients",
            "treatment",
            "risk",
        ]
        score = sum(1 for keyword in keywords if keyword in sentence.lower())
        return min(1.0, score / 4.0)
