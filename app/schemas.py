from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class PaperParseRequest(BaseModel):
    title: str
    abstract: str
    introduction: Optional[str] = None
    methods: Optional[str] = None
    results: Optional[str] = None
    discussion: Optional[str] = None
    citations: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[dict] = Field(default_factory=dict)


class Claim(BaseModel):
    text: str
    polarity: str
    confidence: float
    span_start: Optional[int] = None
    span_end: Optional[int] = None


class AgentReview(BaseModel):
    stance: dict
    weaknesses: List[str]
    method_quality: float
    evidence_strength: float
    controversy_cluster: Optional[int] = None
    citation_roles: List[str] = Field(default_factory=list)
    semantic_shift_score: float
    uncertainty: float


class PaperAnalysisResponse(BaseModel):
    title: str
    abstract: str
    sections: Dict[str, str]
    claims: List[Claim]
    stance: dict
    evidence_strength: float
    methodological_quality: float
    controversy_cluster: Optional[int]
    citation_role: List[str]
    semantic_shift_score: float
    uncertainty: float
