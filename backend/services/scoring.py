"""
Deterministic scoring engine for the SME Productivity Assessment Platform.

Design principles (MSc spec):
- No LLM inference here. Pure Python + NumPy.
- Min-max normalisation anchored to sector p25/p75 from the benchmark database.
- Exclusion (not imputation): missing metric inputs drop the metric from its pillar,
  and pillar confidence decreases proportionally.
- Composite Productivity Index = equal-weighted average of Labour Efficiency
  and Financial Health pillar scores (each 0–100).
- Digital Maturity is computed separately and NOT included in the composite.
- Each recommendation is linked to the source passage that triggered it.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from ..models import (
    DigitalMaturityResult,
    ExtractedMetrics,
    MetricScore,
    PillarResult,
    Recommendation,
)
from ..utils.database import db_service

# ──────────────────────────────────────────────────────────────
# Known software tools for Digital Maturity rubric
# (extracted from document text by the extraction service and passed in)
# ──────────────────────────────────────────────────────────────
KNOWN_DIGITAL_TOOLS: List[str] = [
    "xero",
    "quickbooks",
    "sage",
    "sap",
    "oracle",
    "netsuite",
    "salesforce",
    "hubspot",
    "dynamics",
    "zoho",
    "monday.com",
    "asana",
    "trello",
    "jira",
    "slack",
    "teams",
    "shopify",
    "woocommerce",
    "magento",
    "excel",
    "google sheets",
    "power bi",
    "tableau",
    "zapier",
    "make",
    "n8n",
]

AUTOMATION_KEYWORDS: List[str] = [
    "automat",
    "workflow",
    "robotic process",
    "rpa",
    "bot",
    "digital transform",
    "paperless",
    "e-invoic",
    "api integrat",
]


def _minmax_normalise(
    value: float,
    p25: float,
    p75: float,
) -> float:
    """
    Min-max normalise a single metric value against sector p25/p75 percentiles.
    Returns a score in [0, 100]. Values below p25 → 0; above p75 → 100.
    """
    if p75 <= p25:
        # Degenerate benchmark — can't normalise; return midpoint
        return 50.0
    raw = (value - p25) / (p75 - p25) * 100.0
    return float(np.clip(raw, 0.0, 100.0))


def _score_metric(
    metric_name: str,
    value: Optional[float],
    benchmark: Dict,
    source_passage: str = "",
) -> MetricScore:
    """
    Produce a MetricScore for one metric.
    If value is None → excluded (score=None, excluded=True).
    """
    p25 = float(benchmark.get("p25", 0))
    p50 = float(benchmark.get("p50", 0))
    p75 = float(benchmark.get("p75", 0))

    if value is None:
        return MetricScore(
            metric_name=metric_name,
            raw_value=None,
            normalised_score=None,
            p25=p25,
            p50=p50,
            p75=p75,
            source_passage=source_passage,
            excluded=True,
            exclusion_reason="Input value not found in document",
        )

    score = _minmax_normalise(value, p25, p75)
    return MetricScore(
        metric_name=metric_name,
        raw_value=value,
        normalised_score=score,
        p25=p25,
        p50=p50,
        p75=p75,
        source_passage=source_passage,
        excluded=False,
    )


def _pillar_from_metrics(
    pillar_name: str,
    metric_scores: List[MetricScore],
) -> PillarResult:
    """
    Average included (non-excluded) metric scores to produce a PillarResult.
    Confidence = included / total * 100.
    """
    included = [m for m in metric_scores if not m.excluded]
    excluded = [m for m in metric_scores if m.excluded]

    if included:
        pillar_score = float(np.mean([m.normalised_score for m in included]))
    else:
        pillar_score = 0.0

    confidence = len(included) / len(metric_scores) * 100.0 if metric_scores else 0.0

    return PillarResult(
        pillar_name=pillar_name,
        score=float(np.clip(pillar_score, 0.0, 100.0)),
        confidence=confidence,
        metrics=metric_scores,
        excluded_metrics=[m.metric_name for m in excluded],
        exclusion_reasons={m.metric_name: m.exclusion_reason for m in excluded},
    )


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────


class ScoringService:
    @staticmethod
    async def calculate_productivity_index(
        metrics: ExtractedMetrics,
        sector: str,
        source_passages: Optional[Dict[str, str]] = None,
    ) -> Tuple[PillarResult, PillarResult, float, DigitalMaturityResult]:
        """
        Compute both pillar scores, the composite index, and digital maturity.

        Parameters
        ----------
        metrics:
            Validated extracted metrics (None = not found in document).
        sector:
            One of "Retail", "Services", "Manufacturing".
        source_passages:
            Optional dict mapping metric_name → source passage text.
            Used to link each MetricScore to the document passage that produced it.

        Returns
        -------
        (labour_pillar, financial_pillar, composite_index, digital_maturity)
        """
        passages = source_passages or {}

        # ── Derived metric values ─────────────────────────────
        revenue = metrics.revenue
        headcount = metrics.headcount
        payroll = metrics.payroll
        current_assets = metrics.current_assets
        current_liabilities = metrics.current_liabilities
        inventory = metrics.inventory

        # Compute derived ratios — None if any input is missing
        revenue_per_employee: Optional[float] = (
            revenue / headcount
            if revenue is not None and headcount is not None and headcount > 0
            else None
        )
        output_per_payroll: Optional[float] = (
            revenue / payroll
            if revenue is not None and payroll is not None and payroll > 0
            else None
        )
        headcount_efficiency_ratio: Optional[float] = (
            payroll / headcount
            if payroll is not None and headcount is not None and headcount > 0
            else None
        )
        current_ratio: Optional[float] = (
            current_assets / current_liabilities
            if current_assets is not None
            and current_liabilities is not None
            and current_liabilities > 0
            else None
        )
        quick_ratio: Optional[float] = (
            (current_assets - (inventory or 0.0)) / current_liabilities
            if current_assets is not None
            and current_liabilities is not None
            and current_liabilities > 0
            else None
        )

        # ── Fetch benchmarks ──────────────────────────────────
        async def bench(metric_name: str) -> Dict:
            return await db_service.get_benchmark(sector, metric_name)

        b_rev_emp = await bench("revenue_per_employee")
        b_payroll = await bench("output_per_payroll")
        b_hc_eff = await bench("headcount_efficiency_ratio")
        b_gross = await bench("gross_margin")
        b_op = await bench("operating_margin")
        b_cur_r = await bench("current_ratio")
        b_quick_r = await bench("quick_ratio")

        # ── Labour Efficiency pillar ──────────────────────────
        labour_metrics = [
            _score_metric(
                "revenue_per_employee",
                revenue_per_employee,
                b_rev_emp,
                passages.get("revenue_per_employee", passages.get("revenue", "")),
            ),
            _score_metric(
                "output_per_payroll",
                output_per_payroll,
                b_payroll,
                passages.get("output_per_payroll", passages.get("payroll", "")),
            ),
            _score_metric(
                "headcount_efficiency_ratio",
                headcount_efficiency_ratio,
                b_hc_eff,
                passages.get("headcount_efficiency_ratio", passages.get("headcount", "")),
            ),
        ]
        labour_pillar = _pillar_from_metrics("Labour Efficiency", labour_metrics)

        # ── Financial Health pillar ───────────────────────────
        financial_metrics = [
            _score_metric(
                "gross_margin",
                metrics.gross_margin,
                b_gross,
                passages.get("gross_margin", ""),
            ),
            _score_metric(
                "operating_margin",
                metrics.operating_margin,
                b_op,
                passages.get("operating_margin", ""),
            ),
            _score_metric(
                "current_ratio",
                current_ratio,
                b_cur_r,
                passages.get("current_ratio", ""),
            ),
            _score_metric(
                "quick_ratio",
                quick_ratio,
                b_quick_r,
                passages.get("quick_ratio", ""),
            ),
        ]
        financial_pillar = _pillar_from_metrics("Financial Health", financial_metrics)

        # ── Composite Productivity Index ──────────────────────
        # Equal-weighted average of both pillar scores (both 0–100).
        composite = (labour_pillar.score + financial_pillar.score) / 2.0

        # ── Digital Maturity (diagnostic, NOT in composite) ───
        digital_maturity = ScoringService.compute_digital_maturity(metrics)

        return labour_pillar, financial_pillar, float(composite), digital_maturity

    # ──────────────────────────────────────────────────────────
    @staticmethod
    def compute_digital_maturity(metrics: ExtractedMetrics) -> DigitalMaturityResult:
        """
        Rubric-based Digital Maturity score (0–100).
        NOT included in the Composite Productivity Index.

        Rubric:
          - Named software tools: +5 per recognised tool, max 40 pts
          - Automation language detected: +20 pts
          - Digital process indicators from LLM extraction: up to +40 pts
            (5 pts per indicator phrase, max 8 phrases)
        """
        tools_pts = min(len(metrics.digital_tools_mentioned) * 5, 40)
        automation_pts = 20 if metrics.automation_mentioned else 0
        indicator_pts = min(len(metrics.digital_process_indicators) * 5, 40)

        total = float(np.clip(tools_pts + automation_pts + indicator_pts, 0.0, 100.0))

        if total >= 70:
            level = "High"
        elif total >= 40:
            level = "Medium"
        else:
            level = "Low"

        return DigitalMaturityResult(
            score=total,
            level=level,
            tools_identified=metrics.digital_tools_mentioned,
            automation_detected=metrics.automation_mentioned,
            process_indicators=metrics.digital_process_indicators,
            rubric_breakdown={
                "software_tools": float(tools_pts),
                "automation_language": float(automation_pts),
                "digital_process_indicators": float(indicator_pts),
            },
        )

    # ──────────────────────────────────────────────────────────
    @staticmethod
    def generate_recommendations(
        labour_pillar: PillarResult,
        financial_pillar: PillarResult,
        composite: float,
        sector: str,
        source_passages: Optional[Dict[str, str]] = None,
    ) -> List[Recommendation]:
        """
        Produce a ranked list of Recommendations.
        Each recommendation references the source passage(s) from the metric that triggered it.
        """
        passages = source_passages or {}
        recs: List[Recommendation] = []
        rank = 1

        # ── Labour Efficiency ─────────────────────────────────
        labour_score = labour_pillar.score
        labour_passage = passages.get("revenue_per_employee", passages.get("revenue", ""))

        if labour_score < 34:
            recs.append(
                Recommendation(
                    rank=rank,
                    priority="High",
                    pillar="Labour Efficiency",
                    text=(
                        "Revenue per employee is significantly below the sector p25 threshold. "
                        "Investigate staff utilisation rates, automate repetitive manual workflows, "
                        "and consider sales-enablement or upskilling programmes."
                    ),
                    source_passages=[labour_passage] if labour_passage else [],
                )
            )
        elif labour_score < 67:
            recs.append(
                Recommendation(
                    rank=rank,
                    priority="Medium",
                    pillar="Labour Efficiency",
                    text=(
                        "Labour efficiency is between sector p25 and p75. "
                        "Explore workforce optimisation strategies, cross-train staff, "
                        "and streamline operational tasks to increase output per employee."
                    ),
                    source_passages=[labour_passage] if labour_passage else [],
                )
            )
        else:
            recs.append(
                Recommendation(
                    rank=rank,
                    priority="Low",
                    pillar="Labour Efficiency",
                    text=(
                        "Revenue per employee is above sector p75 — strong performance. "
                        "Maintain talent-retention schemes and scale by standardising "
                        "the processes driving this efficiency."
                    ),
                    source_passages=[labour_passage] if labour_passage else [],
                )
            )
        rank += 1

        # ── Financial Health ──────────────────────────────────
        financial_score = financial_pillar.score
        fin_passage = passages.get("gross_margin", passages.get("operating_margin", ""))

        if financial_score < 34:
            recs.append(
                Recommendation(
                    rank=rank,
                    priority="High",
                    pillar="Financial Health",
                    text=(
                        "Financial health metrics are below sector p25. "
                        "Review supplier contracts to reduce COGS, renegotiate overheads, "
                        "and improve debtor collection cycles to shore up liquidity."
                    ),
                    source_passages=[fin_passage] if fin_passage else [],
                )
            )
        elif financial_score < 67:
            recs.append(
                Recommendation(
                    rank=rank,
                    priority="Medium",
                    pillar="Financial Health",
                    text=(
                        "Margins or liquidity ratios are at or near sector median. "
                        "Review pricing strategy and optimise inventory levels "
                        "to free working capital and push toward p75."
                    ),
                    source_passages=[fin_passage] if fin_passage else [],
                )
            )
        else:
            recs.append(
                Recommendation(
                    rank=rank,
                    priority="Low",
                    pillar="Financial Health",
                    text=(
                        "Profit margins and liquidity are above sector p75. "
                        "Leverage this financial strength to invest in R&D, "
                        "digital tools, or strategic expansion."
                    ),
                    source_passages=[fin_passage] if fin_passage else [],
                )
            )
        rank += 1

        # ── Overall composite ─────────────────────────────────
        overall_passage = labour_passage or fin_passage
        if composite < 34:
            recs.append(
                Recommendation(
                    rank=rank,
                    priority="High",
                    pillar="Overall",
                    text=(
                        "The composite productivity index is in the bottom third of the sector. "
                        "Conduct a thorough internal process audit to identify bottlenecks "
                        "and create a prioritised improvement roadmap."
                    ),
                    source_passages=[overall_passage] if overall_passage else [],
                )
            )
        elif composite < 67:
            recs.append(
                Recommendation(
                    rank=rank,
                    priority="Medium",
                    pillar="Overall",
                    text=(
                        "Productivity is around the sector median. "
                        "Focus on continuous incremental improvements in your weakest pillar "
                        "to transition into the top third."
                    ),
                    source_passages=[overall_passage] if overall_passage else [],
                )
            )
        else:
            recs.append(
                Recommendation(
                    rank=rank,
                    priority="Low",
                    pillar="Overall",
                    text=(
                        "High-productivity performer — above sector p75 on the composite index. "
                        "Consider aggressive expansion, new geographies, or new product lines "
                        "to sustain this competitive position."
                    ),
                    source_passages=[overall_passage] if overall_passage else [],
                )
            )

        return recs
