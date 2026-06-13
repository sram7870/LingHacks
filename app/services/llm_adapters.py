from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings


class LLMAdapter(ABC):
    """Base interface for LLM model adapters."""

    @abstractmethod
    async def infer_stance(self, text: str) -> Dict[str, float]:
        """Infer stance distribution from text."""
        pass

    @abstractmethod
    async def identify_weaknesses(self, text: str) -> List[str]:
        """Identify methodological weaknesses from text."""
        pass

    @abstractmethod
    async def evaluate_quality(self, text: str) -> float:
        """Evaluate overall methodological quality (0-1)."""
        pass


class GPTAdapter(LLMAdapter):
    """OpenAI GPT adapter for stance inference and analysis."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1"

    async def infer_stance(self, text: str) -> Dict[str, float]:
        prompt = f"""Given the following scientific text, infer the stance distribution toward PTLDS (Post-Treatment Lyme Disease Syndrome), CLD (Chronic Lyme Disease), and Neutral.
        
Text:
{text[:2000]}

Respond in JSON format:
{{"PTLDS": <float 0-1>, "CLD": <float 0-1>, "Neutral": <float 0-1>}}
"""
        response = await self._call_api(prompt)
        try:
            import json
            return json.loads(response)
        except Exception:
            return {"PTLDS": 0.33, "CLD": 0.33, "Neutral": 0.34}

    async def identify_weaknesses(self, text: str) -> List[str]:
        prompt = f"""Analyze the following text for methodological weaknesses and limitations.

Text:
{text[:2000]}

List up to 5 weaknesses as a JSON array of strings."""
        response = await self._call_api(prompt)
        try:
            import json
            return json.loads(response)
        except Exception:
            return []

    async def evaluate_quality(self, text: str) -> float:
        prompt = f"""Rate the methodological quality of the following text on a scale of 0-1.

Text:
{text[:2000]}

Respond with a single float value."""
        response = await self._call_api(prompt)
        try:
            return float(response.strip())
        except Exception:
            return 0.5

    async def _call_api(self, prompt: str) -> str:
        if not self.api_key:
            return ""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "messages": [{"role": "user", "content": prompt}]},
                    timeout=60.0,
                )
                data = response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception:
            return ""


class ClaudeAdapter(LLMAdapter):
    """Anthropic Claude adapter for stance inference and analysis."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-sonnet-20240229"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1"

    async def infer_stance(self, text: str) -> Dict[str, float]:
        prompt = f"""Given the following scientific text, infer the stance distribution toward PTLDS (Post-Treatment Lyme Disease Syndrome), CLD (Chronic Lyme Disease), and Neutral.
        
Text:
{text[:2000]}

Respond in JSON format:
{{"PTLDS": <float 0-1>, "CLD": <float 0-1>, "Neutral": <float 0-1>}}
"""
        response = await self._call_api(prompt)
        try:
            import json
            return json.loads(response)
        except Exception:
            return {"PTLDS": 0.33, "CLD": 0.33, "Neutral": 0.34}

    async def identify_weaknesses(self, text: str) -> List[str]:
        prompt = f"""Analyze the following text for methodological weaknesses and limitations.

Text:
{text[:2000]}

List up to 5 weaknesses as a JSON array of strings."""
        response = await self._call_api(prompt)
        try:
            import json
            return json.loads(response)
        except Exception:
            return []

    async def evaluate_quality(self, text: str) -> float:
        prompt = f"""Rate the methodological quality of the following text on a scale of 0-1.

Text:
{text[:2000]}

Respond with a single float value."""
        response = await self._call_api(prompt)
        try:
            return float(response.strip())
        except Exception:
            return 0.5

    async def _call_api(self, prompt: str) -> str:
        if not self.api_key:
            return ""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
                    json={
                        "model": self.model,
                        "max_tokens": 1024,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    timeout=60.0,
                )
                data = response.json()
                return data.get("content", [{}])[0].get("text", "")
        except Exception:
            return ""
