from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime

# Request models
class AssessmentRequest(BaseModel):
    company_name: str = "Unknown"
    sector: str
    document_type: str  # PDF or CSV

# Extracted metrics model
class ExtractedMetrics(BaseModel):
    revenue: Optional[float] = None
    headcount: Optional[int] = None
    cogs: Optional[float] = None
    payroll: Optional[float] = None
    gross_margin: Optional[float] = None  # percentage
    operating_margin: Optional[float] = None  # percentage
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    inventory: Optional[float] = None
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)

# Assessment result model
class AssessmentResult(BaseModel):
    result_id: UUID
    run_id: UUID
    company_name: str
    sector: str
    labour_efficiency_score: float  # 0-50
    financial_health_score: float   # 0-50
    productivity_index: float        # 0-100
    digital_maturity_score: float    # 0-100 (diagnostic)
    confidence_overall: float        # 0-100
    
    # Raw metrics
    revenue_per_employee: Optional[float] = None
    output_per_payroll: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    current_ratio: Optional[float] = None
    
    # Sector benchmarks
    sector_benchmark_revenue_per_emp: Optional[float] = None
    sector_benchmark_output_per_payroll: Optional[float] = None
    sector_benchmark_gross_margin: Optional[float] = None
    sector_benchmark_operating_margin: Optional[float] = None
    
    # Text results
    recommendations: List[str]
    digital_maturity_level: str  # Low, Medium, High
    digital_tools_identified: str
    
    created_at: datetime

# Response model
class AssessmentResponse(BaseModel):
    status: str
    message: str
    result: Optional[AssessmentResult] = None
    error: Optional[str] = None
