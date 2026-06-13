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
    embedding: Optional[List[float]] = None


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


class ClaimCAS(BaseModel):
    claim_text: str
    cas_score: float
    supporting_count: int
    contradicting_count: int
    neutral_count: int
    low_corpus_coverage: bool


class ClaimCNS(BaseModel):
    claim_text: str
    cns_score: float
    most_similar_existing_claim: str
    similarity_score: float
    replication_candidate: bool


class RelationalAnalysisResult(BaseModel):
    paper_id: str
    paper_title: str

    # Metric 1
    aggregate_cas: Optional[float] = None
    cas_interpretation: Optional[str] = None
    per_claim_cas: Optional[List[ClaimCAS]] = None

    # Metric 2
    fci_score: Optional[float] = None
    fci_label: Optional[str] = None
    subgraph_paper_count: Optional[int] = None
    edge_controversy_ratio: Optional[float] = None
    stance_distribution: Optional[Dict[str, int]] = None

    # Metric 3
    mss_percentile: Optional[float] = None
    mss_label: Optional[str] = None
    contradicting_papers_median_quality: Optional[float] = None
    methodological_underdog: Optional[bool] = None
    comparison_pool_size: Optional[int] = None

    # Metric 4
    aggregate_cns: Optional[float] = None
    cns_interpretation: Optional[str] = None
    per_claim_cns: Optional[List[ClaimCNS]] = None

    # Metric 5
    publication_year: Optional[int] = None
    field_trajectory_at_publication: Optional[str] = None
    alignment_with_trajectory: Optional[str] = None
    debate_maturity: Optional[str] = None
    papers_published_same_period: Optional[int] = None
    drift_velocity_at_publication: Optional[float] = None

    # Flags
    corpus_too_small: Optional[bool] = False
    message: Optional[str] = None
