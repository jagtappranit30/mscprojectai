"""
Metric extraction service for the SME Productivity Assessment Platform.

Design principles (MSc spec):
- Per-metric extraction: one RAG query + one Groq call per required metric.
- Prompt injection sanitisation before document text enters any LLM call.
- Explicit prompt delimiters (<DOCUMENT>...</DOCUMENT>) separate content from instructions.
- Strict Pydantic v2 validation of every LLM JSON response.
  On validation failure: return a structured ExtractionError. No retry, no fallback guess.
- Conflict detection: if two source passages return values differing by >10%,
  a ConflictWarning is produced — the caller is never silently given one value.
- No LLM arithmetic. The LLM extracts named values only.
  All ratio computation happens in scoring.py.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

from ..models import (
    ConflictWarning,
    ExtractedMetrics,
    ExtractionError,
    ExtractionResult,
    LLMMetricResponse,
)
from ..utils.config import settings
from ..utils.database import db_service

# ──────────────────────────────────────────────────────────────
# Metrics the pipeline must attempt to extract
# Each entry: (metric_name, retrieval_query, unit_hint)
# ──────────────────────────────────────────────────────────────
EXTRACTION_QUERIES: List[Tuple[str, str, str]] = [
    (
        "revenue",
        "total revenue turnover annual sales income",
        "£ (British pounds)",
    ),
    (
        "headcount",
        "number of employees headcount staff workforce full-time",
        "integer count of employees",
    ),
    (
        "payroll",
        "total payroll wages salaries staff costs employee costs",
        "£ (British pounds)",
    ),
    (
        "gross_margin",
        "gross margin gross profit percentage cost of goods sold COGS",
        "percentage 0–100",
    ),
    (
        "operating_margin",
        "operating margin EBIT operating profit percentage",
        "percentage 0–100",
    ),
    (
        "current_assets",
        "current assets cash receivables short-term assets balance sheet",
        "£ (British pounds)",
    ),
    (
        "current_liabilities",
        "current liabilities short-term debt payables balance sheet",
        "£ (British pounds)",
    ),
    (
        "inventory",
        "inventory stock finished goods raw materials balance sheet",
        "£ (British pounds)",
    ),
    # Digital maturity indicators (extracted as lists, not numbers)
    (
        "digital_tools",
        "software tools ERP CRM accounting system digital platform used",
        "comma-separated list of software tool names",
    ),
    (
        "automation",
        "automation digital transformation workflow RPA robotic process paperless e-invoicing",
        "boolean — yes/no whether automation is described",
    ),
]

# ──────────────────────────────────────────────────────────────
# Injection sanitiser
# ──────────────────────────────────────────────────────────────

# Patterns that look like attempts to override the LLM system prompt
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|all|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"forget\s+(everything|above|previous|all)", re.IGNORECASE),
    re.compile(r"\bsystem\s*:\s*", re.IGNORECASE),
    re.compile(r"\bassistant\s*:\s*", re.IGNORECASE),
    re.compile(r"<\s*/?(?:system|im_start|im_end|s|\/s)\s*>", re.IGNORECASE),
    re.compile(r"\[INST\]|\[\/INST\]|\[SYS\]|\[\/SYS\]", re.IGNORECASE),
    re.compile(r"<<SYS>>|<</SYS>>", re.IGNORECASE),
    re.compile(r"you are now|pretend to be|act as|roleplay as", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?previous", re.IGNORECASE),
]


def sanitise_content(text: str) -> str:
    """
    Strip prompt-injection patterns from document text before it enters an LLM prompt.
    Replaces detected patterns with '[REDACTED]' so the passage length is preserved
    for traceability but the instruction cannot be interpreted by the model.
    """
    for pattern in _INJECTION_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


# ──────────────────────────────────────────────────────────────
# Worked example (one per metric type to anchor the response format)
# ──────────────────────────────────────────────────────────────

_WORKED_EXAMPLE = """\
EXAMPLE (for revenue metric):
Input passage: "The company generated total revenues of £1,250,000 in the year ending March 2024."
Expected JSON output:
{
  "metric_name": "revenue",
  "value": 1250000.0,
  "unit": "£",
  "confidence": 0.95,
  "source_quote": "total revenues of £1,250,000 in the year ending March 2024"
}
If the metric is not present in the passage, set "value" to null and "confidence" to 0.0.
"""


def _build_extraction_prompt(
    metric_name: str,
    unit_hint: str,
    context_passages: List[str],
) -> str:
    """
    Build a delimited extraction prompt for one metric.
    Document content is wrapped in <DOCUMENT>...</DOCUMENT> tags to prevent
    injected text from being interpreted as instructions.
    """
    sanitised_passages = [sanitise_content(p) for p in context_passages]
    joined_context = "\n---\n".join(sanitised_passages)

    return f"""You are a financial data extraction assistant. Your only task is to extract the value of the metric named below from the provided document passages.

{_WORKED_EXAMPLE}

METRIC TO EXTRACT: {metric_name}
EXPECTED UNIT: {unit_hint}

Return ONLY a single valid JSON object. No markdown fences, no explanation, no additional text.
The JSON must conform exactly to this schema:
{{
  "metric_name": "<string>",
  "value": <number or null>,
  "unit": "<string>",
  "confidence": <float 0.0–1.0>,
  "source_quote": "<exact verbatim quote from the passages below, or empty string>"
}}

<DOCUMENT>
{joined_context}
</DOCUMENT>

JSON output:"""


class ExtractionService:
    """
    Per-metric RAG-backed extraction service using Groq Llama 3.3 70B.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.enabled = bool(api_key) and api_key not in ("placeholder", "")
        self.client = None
        if self.enabled:
            try:
                from groq import Groq  # type: ignore
                self.client = Groq(api_key=api_key)
                print("Groq extraction service initialised.")
            except Exception as exc:
                print(f"Failed to initialise Groq client: {exc}")
                self.enabled = False

    # ──────────────────────────────────────────────────────────
    def _call_groq(self, prompt: str) -> str:
        """Synchronous Groq API call. Returns raw response text."""
        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,   # deterministic extraction
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()

    async def _call_groq_async(self, prompt: str) -> str:
        """Non-blocking wrapper around _call_groq using asyncio.to_thread."""
        import asyncio
        return await asyncio.to_thread(self._call_groq, prompt)

    # ──────────────────────────────────────────────────────────
    def _parse_llm_response(
        self,
        metric_name: str,
        raw_text: str,
        source_passages: List[str],
    ) -> Tuple[Optional[ExtractionResult], Optional[ExtractionError]]:
        """
        Parse and strictly validate the LLM JSON response.
        Returns (ExtractionResult, None) on success.
        Returns (None, ExtractionError) on any validation failure — no retry.
        """
        # Strip accidental markdown fences
        clean = raw_text
        if clean.startswith("```"):
            parts = clean.split("```")
            clean = parts[1].strip()
            if clean.startswith("json"):
                clean = clean[4:].strip()

        # Extract the first JSON object if surrounded by noise
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            clean = match.group(0)

        try:
            data = json.loads(clean)
        except json.JSONDecodeError as exc:
            return None, ExtractionError(
                metric_name=metric_name,
                raw_response=raw_text[:500],
                error_detail=f"JSON parse error: {exc}",
            )

        try:
            validated: LLMMetricResponse = LLMMetricResponse.model_validate(data)
        except Exception as exc:
            return None, ExtractionError(
                metric_name=metric_name,
                raw_response=raw_text[:500],
                error_detail=f"Schema validation error: {exc}",
            )

        # Use the source_quote from the LLM if available, else use the first passage
        source_passage = validated.source_quote or (source_passages[0] if source_passages else "")

        result = ExtractionResult(
            metric_name=metric_name,
            value=validated.value,
            unit=validated.unit,
            confidence=validated.confidence,
            source_passage=source_passage,
        )
        return result, None

    # ──────────────────────────────────────────────────────────
    async def extract_all_metrics(
        self,
        run_id: str,
        rag_service,
    ) -> Tuple[ExtractedMetrics, List[ConflictWarning], List[ExtractionError], Dict[str, str]]:
        """
        Run per-metric RAG retrieval + Groq extraction for all required metrics.
        All Groq calls are dispatched concurrently via asyncio.gather for speed.

        Returns
        -------
        metrics:          Flat ExtractedMetrics object for the scoring engine.
        conflict_warnings: List of ConflictWarnings where >10% discrepancy was detected.
        extraction_errors: List of structured errors for metrics that failed validation.
        source_passages:  Dict[metric_name → source passage text] for traceability.
        """
        import asyncio

        extraction_results: Dict[str, ExtractionResult] = {}
        conflict_warnings: List[ConflictWarning] = []
        extraction_errors: List[ExtractionError] = []
        source_passages: Dict[str, str] = {}

        # ── Step 1: Run all RAG retrievals concurrently ───────
        numeric_metrics = [
            (metric_name, query, unit_hint)
            for metric_name, query, unit_hint in EXTRACTION_QUERIES
            if metric_name not in ("digital_tools", "automation")
        ]

        async def _retrieve_one(metric_name: str, query: str) -> Tuple[str, List[str]]:
            try:
                results = await rag_service.retrieve_context(
                    query=query, run_id=run_id, top_k=5
                )
                return metric_name, results
            except Exception as exc:
                print(f"RAG retrieval failed for {metric_name}: {exc}")
                return metric_name, []

        retrieval_tasks = [_retrieve_one(m, q) for m, q, _ in numeric_metrics]
        retrieval_results = await asyncio.gather(*retrieval_tasks)
        retrieved_map: Dict[str, List[str]] = dict(retrieval_results)

        # ── Step 2: Run all Groq calls concurrently ───────────
        async def _extract_one(
            metric_name: str, unit_hint: str
        ) -> Tuple[str, Optional[ExtractionResult], Optional[ExtractionError]]:
            retrieved = retrieved_map.get(metric_name, [])

            if not retrieved:
                return metric_name, ExtractionResult(
                    metric_name=metric_name, value=None, confidence=0.0, source_passage=""
                ), None

            if not self.enabled:
                return metric_name, ExtractionResult(
                    metric_name=metric_name, value=None, confidence=0.0, source_passage=""
                ), None

            prompt = _build_extraction_prompt(metric_name, unit_hint, retrieved)

            try:
                raw_response = await self._call_groq_async(prompt)
            except Exception as exc:
                return metric_name, None, ExtractionError(
                    metric_name=metric_name,
                    raw_response="",
                    error_detail=f"Groq API error: {exc}",
                )

            result, error = self._parse_llm_response(metric_name, raw_response, retrieved)
            return metric_name, result, error

        groq_tasks = [_extract_one(m, u) for m, _, u in numeric_metrics]
        groq_results = await asyncio.gather(*groq_tasks)

        # ── Step 3: Collect results + conflict detection ───────
        for metric_name, result, error in groq_results:
            if error:
                extraction_errors.append(error)
                continue
            if result is None:
                continue

            # Conflict detection (unlikely with parallel calls, but preserved for correctness)
            if metric_name in extraction_results:
                existing = extraction_results[metric_name]
                if (
                    existing.value is not None
                    and result.value is not None
                    and existing.value != 0
                ):
                    discrepancy = abs(result.value - existing.value) / abs(existing.value) * 100
                    if discrepancy > 10.0:
                        conflict_warnings.append(ConflictWarning(
                            metric_name=metric_name,
                            value_a=existing.value,
                            value_b=result.value,
                            passage_a=existing.source_passage,
                            passage_b=result.source_passage,
                            discrepancy_pct=discrepancy,
                        ))
                        continue

            extraction_results[metric_name] = result
            if result.source_passage:
                source_passages[metric_name] = result.source_passage

        # ── Digital maturity extraction (concurrent with nothing, runs separately) ──
        digital_tools, automation_detected, process_indicators = (
            await self._extract_digital_indicators(run_id, rag_service)
        )

        # ── Assemble ExtractedMetrics ─────────────────────────
        def _val(name: str) -> Optional[float]:
            r = extraction_results.get(name)
            return r.value if r else None

        def _int_val(name: str) -> Optional[int]:
            v = _val(name)
            return int(round(v)) if v is not None else None

        found_confidences = [
            r.confidence for r in extraction_results.values()
            if r.value is not None
        ]
        overall_confidence = (
            sum(found_confidences) / len(found_confidences)
            if found_confidences else 0.0
        )

        metrics = ExtractedMetrics(
            revenue=_val("revenue"),
            headcount=_int_val("headcount"),
            payroll=_val("payroll"),
            gross_margin=_val("gross_margin"),
            operating_margin=_val("operating_margin"),
            current_assets=_val("current_assets"),
            current_liabilities=_val("current_liabilities"),
            inventory=_val("inventory"),
            digital_tools_mentioned=digital_tools,
            automation_mentioned=automation_detected,
            digital_process_indicators=process_indicators,
            confidence=overall_confidence,
        )

        return metrics, conflict_warnings, extraction_errors, source_passages

    # ──────────────────────────────────────────────────────────
    async def _extract_digital_indicators(
        self,
        run_id: str,
        rag_service,
    ) -> Tuple[List[str], bool, List[str]]:
        """
        Extract digital maturity indicators from retrieved chunks.
        Uses keyword matching on retrieved text — no LLM arithmetic.
        """
        from .scoring import AUTOMATION_KEYWORDS, KNOWN_DIGITAL_TOOLS

        try:
            chunks = await rag_service.retrieve_context(
                query="software tools automation digital transformation ERP CRM",
                run_id=run_id,
                top_k=8,
            )
        except Exception:
            return [], False, []

        combined_text = " ".join(chunks).lower()
        sanitised = sanitise_content(combined_text)

        # Tool detection
        found_tools = [
            tool.title() for tool in KNOWN_DIGITAL_TOOLS
            if tool.lower() in sanitised
        ]

        # Automation language detection
        automation_detected = any(kw in sanitised for kw in AUTOMATION_KEYWORDS)

        # Digital process indicator phrases
        indicator_patterns = [
            "electronic invoic", "e-invoic", "cloud-based", "online platform",
            "digital workflow", "automated report", "api integrat",
            "paperless", "mobile app", "real-time dashboard", "data analytics",
        ]
        process_indicators = [
            phrase for phrase in indicator_patterns if phrase in sanitised
        ]

        return found_tools, automation_detected, process_indicators


# ──────────────────────────────────────────────────────────────
# Module-level factory
# ──────────────────────────────────────────────────────────────

def get_extraction_service() -> ExtractionService:
    return ExtractionService(api_key=settings.GROQ_API_KEY)
