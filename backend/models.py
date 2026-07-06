"""
Pydantic v2 schemas for the SME Productivity Assessment Platform.

Design principles (MSc spec):
- Strict schemas: validation failures raise ValidationError — no silent fallback.
- Per-metric extraction results carry the source passage for traceability.
- Pillar results carry confidence and excluded-metric lists (exclusion, not imputation).
- Digital Maturity is separate from the composite index (research design requirement).
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ─────────────────────────────────────────────────────────────
# Extraction layer schemas
# ─────────────────────────────────────────────────────────────


class ExtractionResult(BaseModel):
    """Result of extracting a single named metric from a document chunk."""

    model_config = ConfigDict(strict=True)

    metric_name: str
    value: Optional[float]  # None means the metric was not found
    unit: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source_passage: str = ""  # verbatim chunk text that produced this value


class ConflictWarning(BaseModel):
    """Raised when two source passages return values differing by >10% for the same metric."""

    model_config = ConfigDict(strict=True)

    metric_name: str
    value_a: float
    value_b: float
    passage_a: str
    passage_b: str
    discrepancy_pct: float  # absolute percentage difference


class ExtractionError(BaseModel):
    """Structured error returned when Pydantic validation fails on an LLM response."""

    model_config = ConfigDict(strict=True)

    metric_name: str
    raw_response: str
    error_detail: str


# ─────────────────────────────────────────────────────────────
# Raw metrics (legacy — kept for scoring engine input)
# ─────────────────────────────────────────────────────────────


class ExtractedMetrics(BaseModel):
    """
    Flat collection of all extracted numeric values, after conflict resolution.
    Used as the input to the scoring engine.
    """

    revenue: Optional[float] = None
    headcount: Optional[int] = None
    cogs: Optional[float] = None
    payroll: Optional[float] = None
    gross_margin: Optional[float] = None  # percentage, 0–100
    operating_margin: Optional[float] = None  # percentage, 0–100
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    inventory: Optional[float] = None

    # Digital maturity indicators (extracted by LLM, reported separately)
    digital_tools_mentioned: List[str] = Field(default_factory=list)
    automation_mentioned: bool = False
    digital_process_indicators: List[str] = Field(default_factory=list)

    # Aggregate extraction confidence (0–1 range)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


# ─────────────────────────────────────────────────────────────
# Scoring output schemas
# ─────────────────────────────────────────────────────────────


class MetricScore(BaseModel):
    """Normalised score for a single metric within a pillar."""

    metric_name: str
    raw_value: Optional[float]
    normalised_score: Optional[float]  # 0–100, None if excluded
    p25: float
    p50: float
    p75: float
    source_passage: str = ""
    excluded: bool = False
    exclusion_reason: str = ""


class PillarResult(BaseModel):
    """
    Scored result for a single productivity pillar (Labour Efficiency or Financial Health).
    Pillar score is the mean of included metric scores (0–100).
    Confidence decreases proportionally with excluded metrics.
    """

    pillar_name: str
    score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=100.0)  # % of metrics that were included
    metrics: List[MetricScore] = Field(default_factory=list)
    excluded_metrics: List[str] = Field(default_factory=list)
    exclusion_reasons: Dict[str, str] = Field(default_factory=dict)


class Recommendation(BaseModel):
    """A ranked recommendation with traceability to source passage(s)."""

    rank: int
    priority: str  # "High" | "Medium" | "Low"
    text: str
    pillar: str  # which pillar triggered this
    source_passages: List[str] = Field(default_factory=list)


class DigitalMaturityResult(BaseModel):
    """
    Digital Maturity diagnostic axis.
    NOT included in the Composite Productivity Index — reported separately.
    """

    score: float = Field(ge=0.0, le=100.0)
    level: str  # "Low" | "Medium" | "High"
    tools_identified: List[str] = Field(default_factory=list)
    automation_detected: bool = False
    process_indicators: List[str] = Field(default_factory=list)
    rubric_breakdown: Dict[str, float] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# API request / response schemas
# ─────────────────────────────────────────────────────────────


class AssessmentRequest(BaseModel):
    """Form fields accompanying file upload (validated by FastAPI)."""

    company_name: str = "Unknown"
    sector: str  # "Retail" | "Services" | "Manufacturing"
    document_type: str = "PDF"  # "PDF" | "CSV"


class AssessmentOutput(BaseModel):
    """
    Full assessment output returned by POST /assess.
    Composite Productivity Index = (labour_score + financial_score) / 2.
    Digital Maturity is reported separately.
    """

    result_id: str
    run_id: str
    company_name: str
    sector: str
    created_at: datetime

    # ── Composite index (0–100) ──────────────────────────────
    productivity_index: float = Field(ge=0.0, le=100.0)

    # ── Pillar scores (each 0–100) ───────────────────────────
    labour_efficiency: PillarResult
    financial_health: PillarResult

    # ── Digital Maturity (diagnostic, NOT in composite) ──────
    digital_maturity: DigitalMaturityResult

    # ── Conflict warnings ────────────────────────────────────
    conflict_warnings: List[ConflictWarning] = Field(default_factory=list)
    extraction_errors: List[ExtractionError] = Field(default_factory=list)

    # ── Recommendations (ranked, source-linked) ──────────────
    recommendations: List[Recommendation] = Field(default_factory=list)

    # ── Pipeline stage log (for UI progress display) ─────────
    pipeline_stages: Dict[str, str] = Field(default_factory=dict)


class AssessmentResponse(BaseModel):
    """Envelope for the /assess endpoint JSON response."""

    status: str  # "success" | "error"
    message: str
    result: Optional[AssessmentOutput] = None
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Auth schemas (preserved from existing prototype — out of spec scope)
# ─────────────────────────────────────────────────────────────


class UserSignup(BaseModel):
    email: str
    password: str
    confirm_password: str
    company_name: str


class UserLogin(BaseModel):
    email: str
    password: str


# ─────────────────────────────────────────────────────────────
# Strict LLM response schema (used for Pydantic validation of Groq output)
# ─────────────────────────────────────────────────────────────


class LLMMetricResponse(BaseModel):
    """
    Expected JSON structure returned by Groq for a single metric extraction call.
    Validated strictly — any missing required field raises ValidationError.
    On failure the caller returns an ExtractionError; no retry or fallback.
    """

    model_config = ConfigDict(strict=True)

    metric_name: str
    value: Optional[float]
    unit: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    source_quote: str = ""  # exact verbatim quote from the retrieved passage
