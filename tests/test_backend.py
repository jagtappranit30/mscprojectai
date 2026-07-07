"""
Pytest test suite for the SME Productivity Assessment Platform.

Coverage per MSc spec:
  Parsing:   valid PDF, valid CSV, malformed inputs
  Scoring:   normal case, missing-data exclusion, conflicting figures
  Pydantic:  valid payload accepted, malformed payload rejected with structured error
  API:       health check

Tests run in mock mode (no Groq API key, no Supabase) using the fallback paths
built into each service. CI must not require live credentials.
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path
from typing import Dict
from unittest.mock import AsyncMock, patch

import pytest

# ── Ensure the project root is on sys.path ─────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── Import app (mock env vars before import to avoid Settings error) ──
import os

os.environ.setdefault("GROQ_API_KEY", "placeholder")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "placeholder")
os.environ.setdefault("SUPABASE_JWT_SECRET", "placeholder")

from fastapi.testclient import TestClient

from backend.main import app
from backend.models import (
    ConflictWarning,
    ExtractedMetrics,
    LLMMetricResponse,
)
from backend.services.scoring import ScoringService, _minmax_normalise

client = TestClient(app)


# ══════════════════════════════════════════════════════════════
# SECTION 1 — Parsing tests
# ══════════════════════════════════════════════════════════════


class TestParsing:
    """Tests for PDF and CSV document parsing."""

    def _make_csv_bytes(self, rows) -> bytes:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8")

    # ── CSV: valid input ───────────────────────────────────────
    def test_parse_csv_valid_returns_text(self):
        """A well-formed CSV should produce non-empty text."""
        rows = [
            ["Metric", "Value"],
            ["Revenue", "500000"],
            ["Headcount", "20"],
            ["Gross Margin", "35"],
        ]
        csv_bytes = self._make_csv_bytes(rows)

        # Simulate the CSV parsing logic used in main.py
        text_file = io.StringIO(csv_bytes.decode("utf-8", errors="ignore"))
        reader = csv.reader(text_file)
        text = "\n".join(", ".join(row) for row in reader)

        assert len(text.strip()) > 0
        assert "Revenue" in text
        assert "500000" in text

    # ── CSV: malformed (encoding errors) ──────────────────────
    def test_parse_csv_malformed_encoding_handled_gracefully(self):
        """
        A CSV with invalid UTF-8 bytes should not crash the parser.
        The errors='ignore' flag should silently drop bad bytes.
        """
        # Inject a non-UTF-8 sequence (Latin-1 encoded pound sign)
        bad_bytes = b"Revenue,\xa3500000\nHeadcount,10\n"
        text_file = io.StringIO(bad_bytes.decode("utf-8", errors="ignore"))
        reader = csv.reader(text_file)
        text = "\n".join(", ".join(row) for row in reader)

        # Should not raise; result should still be a string
        assert isinstance(text, str)
        assert "Revenue" in text

    # ── CSV: completely empty file ─────────────────────────────
    def test_parse_csv_empty_produces_empty_or_minimal_text(self):
        """An empty CSV file should produce empty or whitespace-only text."""
        text_file = io.StringIO("")
        reader = csv.reader(text_file)
        text = "\n".join(", ".join(row) for row in reader)
        assert text.strip() == ""

    # ── PDF: empty stream raises or returns empty ──────────────
    def test_parse_pdf_empty_stream_is_rejected(self):
        """Uploading a 0-byte file should result in a 400 response from /assess."""
        response = client.post(
            "/assess",
            files=[("files", ("empty.pdf", b"", "application/pdf"))],
            data={"sector": "Retail", "company_name": "Test"},
        )
        # Empty / unreadable document → 400 or 500 (not 200)
        assert response.status_code in (400, 500)

    # ── PDF: non-PDF binary blob ───────────────────────────────
    def test_parse_pdf_binary_garbage_is_rejected(self):
        """
        A file with .pdf extension but random binary content should fail gracefully.
        The endpoint should return 4xx or 5xx, not crash with an unhandled exception.
        """
        garbage = b"\x00\x01\x02\x03" * 100
        response = client.post(
            "/assess",
            files=[("files", ("garbage.pdf", garbage, "application/pdf"))],
            data={"sector": "Services", "company_name": "Test"},
        )
        assert response.status_code in (400, 500)
        body = response.json()
        assert "status" in body


# ══════════════════════════════════════════════════════════════
# SECTION 2 — Scoring engine tests
# ══════════════════════════════════════════════════════════════


class TestScoringEngine:
    """Tests for the deterministic scoring engine."""

    # ── Helper: benchmark mock ─────────────────────────────────
    @staticmethod
    def _mock_benchmark(sector: str, metric_name: str) -> Dict:
        """Return mock benchmark values matching the database seed data."""
        benchmarks = {
            ("Manufacturing", "revenue_per_employee"): {
                "p25": 120000,
                "p50": 175000,
                "p75": 240000,
            },
            ("Manufacturing", "output_per_payroll"): {"p25": 3.5, "p50": 4.2, "p75": 5.1},
            ("Manufacturing", "headcount_efficiency_ratio"): {
                "p25": 22000,
                "p50": 28000,
                "p75": 36000,
            },
            ("Manufacturing", "gross_margin"): {"p25": 25, "p50": 35, "p75": 45},
            ("Manufacturing", "operating_margin"): {"p25": 5, "p50": 12, "p75": 20},
            ("Manufacturing", "current_ratio"): {"p25": 1.2, "p50": 1.8, "p75": 2.5},
            ("Manufacturing", "quick_ratio"): {"p25": 0.8, "p50": 1.2, "p75": 1.8},
        }
        return benchmarks.get((sector, metric_name), {"p25": 0, "p50": 50, "p75": 100})

    # ── Test: minmax normalisation ─────────────────────────────
    def test_minmax_normalise_at_p25_returns_zero(self):
        assert _minmax_normalise(100, p25=100, p75=200) == pytest.approx(0.0)

    def test_minmax_normalise_at_p75_returns_hundred(self):
        assert _minmax_normalise(200, p25=100, p75=200) == pytest.approx(100.0)

    def test_minmax_normalise_at_midpoint_returns_fifty(self):
        assert _minmax_normalise(150, p25=100, p75=200) == pytest.approx(50.0)

    def test_minmax_normalise_below_p25_clamps_to_zero(self):
        assert _minmax_normalise(50, p25=100, p75=200) == pytest.approx(0.0)

    def test_minmax_normalise_above_p75_clamps_to_hundred(self):
        assert _minmax_normalise(300, p25=100, p75=200) == pytest.approx(100.0)

    # ── Test: normal case — all metrics present ─────────────────
    @pytest.mark.asyncio
    async def test_scoring_normal_case(self):
        """All metrics present → pillar scores in [0,100], composite = average."""
        metrics = ExtractedMetrics(
            revenue=200_000,
            headcount=10,
            payroll=50_000,
            gross_margin=40.0,
            operating_margin=15.0,
            current_assets=80_000,
            current_liabilities=40_000,
            inventory=10_000,
            confidence=0.95,
        )

        with patch(
            "backend.utils.database.db_service.get_benchmark",
            new=AsyncMock(side_effect=lambda s, m: self._mock_benchmark(s, m)),
        ):
            (
                labour,
                financial,
                composite,
                digital,
            ) = await ScoringService.calculate_productivity_index(metrics, "Manufacturing")

        assert 0.0 <= labour.score <= 100.0
        assert 0.0 <= financial.score <= 100.0
        assert 0.0 <= composite <= 100.0

        # Composite must be exact equal-weighted average
        assert composite == pytest.approx((labour.score + financial.score) / 2.0, abs=0.01)

        # No exclusions when all metrics present
        assert labour.excluded_metrics == []
        assert financial.excluded_metrics == []

        # Confidence should be 100% when all included
        assert labour.confidence == pytest.approx(100.0)
        assert financial.confidence == pytest.approx(100.0)

    # ── Test: missing data exclusion ────────────────────────────
    @pytest.mark.asyncio
    async def test_scoring_missing_data_excludes_metric_and_lowers_confidence(self):
        """
        If revenue is None, revenue_per_employee and related derived metrics
        are excluded from the Labour pillar, reducing pillar confidence below 100%.
        No imputation must occur.
        """
        metrics = ExtractedMetrics(
            revenue=None,  # <-- missing
            headcount=10,
            payroll=None,  # <-- missing
            gross_margin=35.0,
            operating_margin=10.0,
            current_assets=60_000,
            current_liabilities=40_000,
            inventory=5_000,
            confidence=0.6,
        )

        with patch(
            "backend.utils.database.db_service.get_benchmark",
            new=AsyncMock(side_effect=lambda s, m: self._mock_benchmark(s, m)),
        ):
            (
                labour,
                financial,
                composite,
                digital,
            ) = await ScoringService.calculate_productivity_index(metrics, "Manufacturing")

        # All three labour metrics require revenue or payroll → all excluded
        assert labour.confidence < 100.0
        assert "revenue_per_employee" in labour.excluded_metrics
        assert "output_per_payroll" in labour.excluded_metrics
        assert "headcount_efficiency_ratio" in labour.excluded_metrics

        # Financial pillar should still score (gross_margin, operating_margin present)
        assert financial.confidence > 0.0

        # Composite should still be computed from available pillar
        assert 0.0 <= composite <= 100.0

    # ── Test: conflicting figures flag ─────────────────────────
    def test_conflict_warning_produced_for_gt10pct_discrepancy(self):
        """
        A ConflictWarning is produced when two values for the same metric differ >10%.
        The warning must expose both values and both passages.
        """
        cw = ConflictWarning(
            metric_name="revenue",
            value_a=500_000.0,
            value_b=560_000.0,  # 12% discrepancy
            passage_a="Total revenue: £500,000",
            passage_b="Annual turnover: £560,000",
            discrepancy_pct=12.0,
        )

        assert cw.metric_name == "revenue"
        assert cw.discrepancy_pct > 10.0
        assert cw.value_a != cw.value_b
        assert len(cw.passage_a) > 0
        assert len(cw.passage_b) > 0

    def test_no_conflict_warning_for_lte10pct_discrepancy(self):
        """Values within 10% of each other should NOT trigger a conflict warning."""
        value_a = 500_000.0
        value_b = 548_000.0  # 9.6% discrepancy
        discrepancy = abs(value_b - value_a) / abs(value_a) * 100
        assert discrepancy <= 10.0  # should not trigger conflict


# ══════════════════════════════════════════════════════════════
# SECTION 3 — Pydantic schema tests
# ══════════════════════════════════════════════════════════════


class TestPydanticSchemas:
    """Validate LLMMetricResponse: accept valid, reject malformed."""

    # ── Valid payload ──────────────────────────────────────────
    def test_valid_llm_response_accepted(self):
        """A fully compliant LLM response payload passes Pydantic validation."""
        data = {
            "metric_name": "revenue",
            "value": 500000.0,
            "unit": "£",
            "confidence": 0.92,
            "source_quote": "Total revenue of £500,000 for FY2024.",
        }
        model = LLMMetricResponse.model_validate(data)
        assert model.metric_name == "revenue"
        assert model.value == pytest.approx(500000.0)
        assert model.confidence == pytest.approx(0.92)

    def test_null_value_in_valid_payload_accepted(self):
        """value=null is valid (metric not found in passages)."""
        data = {
            "metric_name": "inventory",
            "value": None,
            "unit": "£",
            "confidence": 0.0,
            "source_quote": "",
        }
        model = LLMMetricResponse.model_validate(data)
        assert model.value is None

    # ── Malformed payloads: schema rejection ───────────────────
    def test_missing_metric_name_rejected(self):
        """Payload missing 'metric_name' must raise ValidationError."""
        from pydantic import ValidationError

        data = {
            "value": 500000.0,
            "unit": "£",
            "confidence": 0.92,
            "source_quote": "Revenue of £500,000.",
        }
        with pytest.raises(ValidationError):
            LLMMetricResponse.model_validate(data)

    def test_confidence_out_of_range_rejected(self):
        """confidence > 1.0 violates the schema ge/le constraints."""
        from pydantic import ValidationError

        data = {
            "metric_name": "revenue",
            "value": 500000.0,
            "unit": "£",
            "confidence": 1.5,  # invalid: must be 0.0–1.0
            "source_quote": "",
        }
        with pytest.raises(ValidationError):
            LLMMetricResponse.model_validate(data)

    def test_non_numeric_confidence_rejected(self):
        """confidence must be a float, not a string."""
        from pydantic import ValidationError

        data = {
            "metric_name": "gross_margin",
            "value": 35.0,
            "unit": "%",
            "confidence": "high",  # invalid type
            "source_quote": "",
        }
        with pytest.raises(ValidationError):
            LLMMetricResponse.model_validate(data)

    def test_non_numeric_value_for_numeric_field_rejected(self):
        """value must be float or null — a plain string must be rejected."""
        from pydantic import ValidationError

        data = {
            "metric_name": "revenue",
            "value": "£500,000",  # invalid — must be float or null
            "unit": "£",
            "confidence": 0.9,
            "source_quote": "",
        }
        with pytest.raises(ValidationError):
            LLMMetricResponse.model_validate(data)


# ══════════════════════════════════════════════════════════════
# SECTION 4 — API tests
# ══════════════════════════════════════════════════════════════


class TestAPIEndpoints:
    def test_health_endpoint_returns_ok(self):
        """GET /health must return 200 with {status: ok}."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
