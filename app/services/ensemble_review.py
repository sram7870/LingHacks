from typing import Any, Dict, List, Optional, Tuple
import asyncio
import math
from collections import Counter
import statistics

from app.services.document_encoder import ParsedDocument
from app.schemas import Claim
from app.services.llm_adapters import LLMAdapter, GPTAdapter, ClaudeAdapter


class EnsembleConfig:
    """Configuration for ensemble uncertainty modeling."""

    def __init__(self, models: Optional[List[LLMAdapter]] = None, prompts: Optional[List[str]] = None):
        self.models = models or []
        self.prompts = prompts or ["default", "detailed", "critical"]


class EnsembleResult:
    """Aggregated result from ensemble runs."""

    def __init__(
        self,
        stance: Dict[str, float],
        agreement_score: float,
        variance: float,
        confidence_interval: Tuple[float, float],
        weaknesses: List[str],
        quality: float,
        uncertainty: float,
    ):
        self.stance = stance
        self.agreement_score = agreement_score
        self.variance = variance
        self.confidence_interval = confidence_interval
        self.weaknesses = weaknesses
        self.quality = quality
        self.uncertainty = uncertainty


class EnsembleOrchestrator:
    """Orchestrates multi-model, multi-prompt consensus for scientific review."""

    def __init__(self, config: Optional[EnsembleConfig] = None):
        self.config = config or EnsembleConfig()

    def add_model(self, model: LLMAdapter) -> None:
        self.config.models.append(model)

    async def review_ensemble(
        self,
        document: ParsedDocument,
        claims: List[Claim],
        use_llm: bool = False,
    ) -> EnsembleResult:
        """Run ensemble review across models and prompts."""
        if not use_llm or not self.config.models:
            return self._fallback_result()

        stance_results = []
        quality_results = []
        weakness_results = []

        text = " ".join(
            [document.abstract or ""]
            + list(document.sections.values())
        ).strip()

        for model in self.config.models:
            for _ in self.config.prompts:
                try:
                    stance = await model.infer_stance(text)
                    quality = await model.evaluate_quality(text)
                    weaknesses = await model.identify_weaknesses(text)

                    stance_results.append(stance)
                    quality_results.append(quality)
                    weakness_results.extend(weaknesses)
                except Exception:
                    pass

        if not stance_results:
            return self._fallback_result()

        aggregated_stance = self._aggregate_stance(stance_results)
        agreement = self._compute_agreement(stance_results)
        variance = self._compute_variance(quality_results)
        ci = self._compute_confidence_interval(quality_results)
        avg_quality = sum(quality_results) / len(quality_results) if quality_results else 0.5
        uncertainty = round(variance, 3)

        return EnsembleResult(
            stance=aggregated_stance,
            agreement_score=round(agreement, 3),
            variance=round(variance, 3),
            confidence_interval=ci,
            weaknesses=list(set(weakness_results))[:5],
            quality=round(avg_quality, 3),
            uncertainty=uncertainty,
        )

    def _aggregate_stance(self, results: List[Dict[str, float]]) -> Dict[str, float]:
        """Aggregate stance distributions across runs."""
        keys = set()
        for result in results:
            keys.update(result.keys())

        aggregated = {}
        for key in keys:
            values = [r.get(key, 0.0) for r in results]
            aggregated[key] = round(sum(values) / len(values), 3)

        total = sum(aggregated.values())
        if total == 0:
            return {k: round(1.0 / len(aggregated), 3) for k in aggregated}

        return {k: round(v / total, 3) for k, v in aggregated.items()}

    def _compute_agreement(self, results: List[Dict[str, float]]) -> float:
        """Compute agreement score across runs (0-1)."""
        if len(results) < 2:
            return 1.0

        pairwise_agreements = []
        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                agreement = self._kl_divergence(results[i], results[j])
                pairwise_agreements.append(1.0 - min(1.0, agreement))

        return sum(pairwise_agreements) / len(pairwise_agreements) if pairwise_agreements else 1.0

    def _kl_divergence(self, p: Dict[str, float], q: Dict[str, float]) -> float:
        """Compute KL divergence between two distributions."""
        total_kl = 0.0
        for key in p:
            p_val = p.get(key, 0.001)
            q_val = q.get(key, 0.001)
            if p_val > 0 and q_val > 0:
                total_kl += p_val * (math.log(p_val) - math.log(q_val))
        return total_kl

    def _compute_variance(self, values: List[float]) -> float:
        """Compute variance across quality scores."""
        if len(values) < 2:
            return 0.0
        return statistics.variance(values)

    def _compute_confidence_interval(self, values: List[float], confidence: float = 0.95) -> Tuple[float, float]:
        """Compute confidence interval for quality."""
        if not values:
            return (0.0, 1.0)

        mean = sum(values) / len(values)
        if len(values) < 2:
            return (mean, mean)

        std_dev = statistics.stdev(values)
        margin = 1.96 * std_dev / (len(values) ** 0.5)
        return (round(max(0.0, mean - margin), 3), round(min(1.0, mean + margin), 3))

    def _fallback_result(self) -> EnsembleResult:
        """Return a neutral fallback result."""
        return EnsembleResult(
            stance={"PTLDS": 0.33, "CLD": 0.33, "Neutral": 0.34},
            agreement_score=0.0,
            variance=0.0,
            confidence_interval=(0.0, 1.0),
            weaknesses=[],
            quality=0.5,
            uncertainty=0.5,
        )
