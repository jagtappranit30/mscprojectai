import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from backend.main import app
from backend.services.scoring import ScoringService

client = TestClient(app)

def test_health_endpoint():
    """Verify that the health check endpoint works"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_scoring_formulas():
    """Verify productivity score calculations and ranges"""
    metrics = {
        "revenue": 200000.0,
        "headcount": 10,
        "payroll": 50000.0,
        "gross_margin": 40.0,
        "operating_margin": 15.0,
        "current_assets": 80000.0,
        "current_liabilities": 40000.0,
        "confidence": 95.0
    }
    
    labour_score, financial_score, prod_index, digital_score = \
        await ScoringService.calculate_productivity_index(metrics, "Manufacturing")
        
    assert 0.0 <= labour_score <= 50.0
    assert 0.0 <= financial_score <= 50.0
    assert 0.0 <= prod_index <= 100.0
    
    # Verify exact math (since revenue/headcount is 20000, and sector median p50 for Manufacturing is 175000)
    # revenue_per_emp = 20000. Ratio = 20000 / 175000 = 0.114.
    # Score = 0.114 * 25 = 2.85 points.
    assert abs(labour_score - 2.857) < 0.1

def test_recommendations_generator():
    """Verify the recommendation rules engine output"""
    recs = ScoringService.generate_recommendations(
        labour_score=15.0,
        financial_score=15.0,
        productivity_index=30.0,
        sector="Manufacturing"
    )
    
    assert len(recs) == 3
    # Check for presence of warning tags
    assert any("🔴 Urgent" in rec for rec in recs)
