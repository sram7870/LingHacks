import re
from operator import itemgetter
from typing import List, Tuple

from app.core.config import settings
from app.schemas import Claim
from app.services.document_encoder import ParsedDocument


class ClaimExtractor:
    CLAIM_KEYWORDS = [
        "improve",
        "reduce",
        "increase",
        "associated",
        "significant",
        "evidence",
        "support",
        "suggest",
        "linked",
        "risk",
        "benefit",
        "reduce",
        "correlat",
        "predict",
        "indicate",
        "demonstrat",
    ]

    NEGATIVE_PATTERNS = [
        "not significant",
        "no significant",
        "failed to",
        "did not",
        "no evidence",
        "lack of",
        "not associated",
        "not correlated",
        "contradict",
        "inconsistent",
    ]

    STRONG_CLAIM_PHRASES = [
        "we found",
        "our results",
        "this study demonstrates",
        "this work shows",
        "results indicate",
        "our findings",
        "we show",
    ]

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

        for sentence, section in candidates:
            score = self._score_sentence(sentence, section)
            polarity = self._detect_polarity(sentence)
            scored.append({"sentence": sentence, "score": score, "polarity": polarity, "section": section})

        top_claims = sorted(scored, key=itemgetter("score"), reverse=True)[:5]
        claims = [
            Claim(
                text=item["sentence"],
                polarity=item["polarity"],
                confidence=round(item["score"], 3),
                span_start=None,
                span_end=None,
            )
            for item in top_claims
            if item["score"] >= 0.25
        ]

        if not claims and scored:
            fallback = sorted(scored, key=itemgetter("score"), reverse=True)[:3]
            claims = [
                Claim(
                    text=item["sentence"],
                    polarity=item["polarity"],
                    confidence=round(item["score"], 3),
                    span_start=None,
                    span_end=None,
                )
                for item in fallback
            ]

        return claims

    def _collect_candidates(self, document: ParsedDocument) -> List[Tuple[str, str]]:
        ordered_sections = [
            (document.abstract or "", "abstract"),
            (document.sections.get("results") or "", "results"),
            (document.sections.get("discussion") or "", "discussion"),
            (document.sections.get("introduction") or "", "introduction"),
            (document.sections.get("methods") or "", "methods"),
        ]
        candidates = []
        for text, section in ordered_sections:
            if not text:
                continue
            for sentence in self._split_sentences(text):
                candidates.append((sentence, section))
        return candidates

    def _split_sentences(self, text: str) -> List[str]:
        sentences = re.split(r"(?<=[\.\?\!])\s+", text)
        return [sentence.strip() for sentence in sentences if len(sentence.strip()) > 20]

    def _score_sentence(self, sentence: str, section: str) -> float:
        tokens = self.tokenizer(sentence, truncation=True, max_length=128, return_tensors="pt")
        if self._torch is None or self._sigmoid is None:
            raise RuntimeError("Torch dependencies are not initialized")

        with self._torch.no_grad():
            output = self.model(**tokens)

        if hasattr(output, "pooler_output") and output.pooler_output is not None:
            embedding = output.pooler_output
        else:
            embedding = output.last_hidden_state[:, 0, :]

        model_score = float(self._sigmoid(embedding.mean()))
        keyword_bonus = self._keyword_strength(sentence)
        pattern_bonus = self._pattern_strength(sentence)
        section_bonus = 0.15 if section in {"results", "discussion", "abstract"} else 0.0
        raw = 0.2 * model_score + 0.55 * keyword_bonus + 0.2 * pattern_bonus + section_bonus
        return min(1.0, max(0.0, raw))

    def _keyword_strength(self, sentence: str) -> float:
        text = sentence.lower()
        count = sum(1 for keyword in self.CLAIM_KEYWORDS if keyword in text)
        return min(1.0, (count + 1) / 5.0)

    def _pattern_strength(self, sentence: str) -> float:
        text = sentence.lower()
        return 0.25 if any(phrase in text for phrase in self.STRONG_CLAIM_PHRASES) else 0.0

    def _detect_polarity(self, sentence: str) -> str:
        text = sentence.lower()
        if any(neg in text for neg in self.NEGATIVE_PATTERNS):
            return "oppose"
        if any(word in text for word in ["support", "confirms", "demonstrates", "shows", "linked to", "improve"]):
            return "support"
        return "neutral"
