import re
from typing import Any, Dict, List, Optional
import asyncio

from app.services.document_encoder import ParsedDocument
from app.schemas import Claim
from app.core.config import settings


class AgentReviewResult:
    def __init__(
        self,
        stance: Dict[str, float],
        weaknesses: List[str],
        method_quality: float,
        evidence_strength: float,
        controversy_cluster: Optional[int],
        citation_roles: List[str],
        semantic_shift_score: float,
        uncertainty: float,
        study_design: str,
        sample_size: int,
    ):
        self.stance = stance
        self.weaknesses = weaknesses
        self.method_quality = method_quality
        self.evidence_strength = evidence_strength
        self.controversy_cluster = controversy_cluster
        self.citation_roles = citation_roles
        self.semantic_shift_score = semantic_shift_score
        self.uncertainty = uncertainty
        self.study_design = study_design
        self.sample_size = sample_size


class StanceAgent:
    TOPIC_LABELS = ["ptlds", "cld", "chronic lyme", "lyme disease"]

    def infer_stance(self, document: ParsedDocument, claims: List[Claim]) -> Dict[str, float]:
        weights = {"PTLDS": 0.0, "CLD": 0.0, "Neutral": 0.0}
        token_source = " ".join([document.abstract or ""] + list(document.sections.values())).lower()

        for label in self.TOPIC_LABELS:
            if label in token_source:
                if "ptlds" in label:
                    weights["PTLDS"] += 0.9
                elif "cld" in label:
                    weights["CLD"] += 0.9
                else:
                    weights["Neutral"] += 0.3

        for claim in claims:
            if claim.polarity == "support":
                weights["PTLDS"] += claim.confidence * 0.6
            elif claim.polarity == "neutral":
                weights["Neutral"] += claim.confidence * 0.8
            else:
                weights["CLD"] += claim.confidence * 0.4

        total = sum(weights.values())
        if total == 0:
            return {"PTLDS": 0.33, "CLD": 0.33, "Neutral": 0.34}

        return {k: round(v / total, 3) for k, v in weights.items()}


class SkepticAgent:
    WEAK_PHRASES = ["may", "might", "could", "suggest", "some patients", "larger studies", "further research", "possible", "potential"]
    NEGATIVE_INDICATORS = ["insufficient", "underpowered", "no evidence", "not significant", "failed to", "did not", "lack of"]

    def analyze(self, document: ParsedDocument, claims: List[Claim]) -> List[str]:
        weaknesses = []
        context = " ".join([document.abstract or ""] + list(document.sections.values())).lower()

        if not document.sections.get("methods"):
            weaknesses.append("The methods section is missing or not clearly identified.")
        if not document.sections.get("results"):
            weaknesses.append("The results section is missing or not clearly identified.")

        for phrase in self.WEAK_PHRASES:
            if phrase in context:
                weaknesses.append(f"Hedging language such as '{phrase}' is present, reducing confidence in the claim.")

        for phrase in self.NEGATIVE_INDICATORS:
            if phrase in context:
                weaknesses.append(f"Found cautious or negative wording: '{phrase}'. This suggests weaker evidence.")

        if len(claims) == 0:
            weaknesses.append("No claims were confidently extracted from this document.")
        elif len(claims) == 1:
            weaknesses.append("Only one claim was extracted. Additional evidence or claims would improve robustness.")

        if not weaknesses:
            weaknesses.append("Surface review did not identify obvious weaknesses; deeper review may still be needed.")

        return weaknesses


class MethodsAgent:
    DESIGN_KEYWORDS = {
        "RCT": ["randomized", "double blind", "placebo", "randomised", "trial"],
        "Cohort": ["cohort", "prospective", "retrospective"],
        "Case-control": ["case-control", "case control"],
        "Observational": ["observational", "survey", "cross-sectional"],
    }

    def evaluate(self, document: ParsedDocument) -> Dict[str, Any]:
        methods_text = (document.sections.get("methods") or "").lower()
        results_text = (document.sections.get("results") or "").lower()
        design = self._identify_design(methods_text)
        sample_size = self._extract_sample_size(methods_text + " " + results_text)
        quality = self._estimate_quality(methods_text, results_text, sample_size)
        return {
            "study_design": design,
            "quality": round(quality, 3),
            "sample_size": sample_size,
        }

    def _identify_design(self, text: str) -> str:
        for label, keywords in self.DESIGN_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                return label
        return "Observational" if text else "Unknown"

    def _extract_sample_size(self, text: str) -> int:
        matches = re.findall(r"(?:sample size|n\s*=|n=|participants|patients)\s*(?:of\s*)?(\d{2,5})", text)
        if matches:
            return int(matches[0])
        return 0

    def _estimate_quality(self, methods_text: str, results_text: str, sample_size: int) -> float:
        score = 0.0
        if methods_text:
            score += 0.35
        if results_text:
            score += 0.35
        if sample_size >= 200:
            score += 0.2
        elif sample_size >= 50:
            score += 0.1
        if "p=" in results_text or "p <" in results_text or "p-value" in results_text or "confidence interval" in results_text:
            score += 0.1
        if "randomized" in methods_text or "double blind" in methods_text or "placebo" in methods_text:
            score += 0.05
        return min(1.0, score)


class ConsensusAgent:
    def combine(
        self,
        stance: Dict[str, float],
        method_quality: float,
        skepticism: List[str],
        claims: List[Claim],
    ) -> Dict[str, Any]:
        disagreement = 1.0 - max(stance.values()) if stance else 0.5
        has_weak_claims = sum(1 for claim in claims if claim.confidence < 0.4)
        close_weakness = len(skepticism)

        controversy_score = round(min(1.0, disagreement * 0.7 + (1.0 - method_quality) * 0.3 + close_weakness * 0.05), 3)
        controversy_cluster = 2 if controversy_score > 0.7 else (1 if controversy_score > 0.4 else 0)

        uncertainty = round(min(0.95, max(0.1, (1.0 - method_quality) * 0.35 + controversy_score * 0.35 + (has_weak_claims * 0.05))), 3)
        citation_roles = ["support" if stance.get("PTLDS", 0) >= 0.5 else "critique"]
        if stance.get("Neutral", 0.0) > 0.7:
            citation_roles = ["neutral"]

        semantic_shift_score = round(min(1.0, 0.25 + controversy_score * 0.35 + (1.0 - method_quality) * 0.2), 3)
        return {
            "controversy_cluster": controversy_cluster,
            "citation_roles": citation_roles,
            "semantic_shift_score": semantic_shift_score,
            "uncertainty": uncertainty,
        }


class AgentReviewCoordinator:
    def __init__(self, use_ensemble: bool | None = None):
        self.stance_agent = StanceAgent()
        self.skeptic_agent = SkepticAgent()
        self.methods_agent = MethodsAgent()
        self.consensus_agent = ConsensusAgent()
        self.use_ensemble = settings.use_ensemble_llm if use_ensemble is None else use_ensemble
        self.ensemble_orchestrator = None

        if self.use_ensemble:
            try:
                from app.services.ensemble_review import EnsembleOrchestrator, EnsembleConfig
                from app.services.llm_adapters import GPTAdapter, ClaudeAdapter

                config = EnsembleConfig()
                if settings.openai_api_key:
                    config.models.append(GPTAdapter(api_key=settings.openai_api_key))
                if settings.anthropic_api_key:
                    config.models.append(ClaudeAdapter(api_key=settings.anthropic_api_key))

                self.ensemble_orchestrator = EnsembleOrchestrator(config)
            except Exception:
                self.ensemble_orchestrator = None

    def review_paper(self, document: ParsedDocument, claims: List[Claim]) -> AgentReviewResult:
        stance = self.stance_agent.infer_stance(document, claims)
        weaknesses = self.skeptic_agent.analyze(document, claims)
        method_report = self.methods_agent.evaluate(document)
        consensus = self.consensus_agent.combine(stance, method_report["quality"], weaknesses, claims)
        evidence_strength = round((method_report["quality"] + (1.0 - consensus["uncertainty"])) / 2.0, 3)

        # Optionally run ensemble for enhanced uncertainty modeling
        if self.use_ensemble and self.ensemble_orchestrator:
            try:
                ensemble_result = asyncio.run(
                    self.ensemble_orchestrator.review_ensemble(document, claims, use_llm=True)
                )
                return AgentReviewResult(
                    stance=ensemble_result.stance,
                    weaknesses=ensemble_result.weaknesses or weaknesses,
                    method_quality=ensemble_result.quality,
                    evidence_strength=ensemble_result.quality,
                    controversy_cluster=consensus["controversy_cluster"],
                    citation_roles=consensus["citation_roles"],
                    semantic_shift_score=ensemble_result.uncertainty,
                    uncertainty=ensemble_result.uncertainty,
                    study_design=method_report["study_design"],
                    sample_size=method_report["sample_size"],
                )
            except Exception:
                pass

        return AgentReviewResult(
            stance=stance,
            weaknesses=weaknesses,
            method_quality=method_report["quality"],
            evidence_strength=evidence_strength,
            controversy_cluster=consensus["controversy_cluster"],
            citation_roles=consensus["citation_roles"],
            semantic_shift_score=consensus["semantic_shift_score"],
            uncertainty=consensus["uncertainty"],
            study_design=method_report["study_design"],
            sample_size=method_report["sample_size"],
        )
