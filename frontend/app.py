"""
Streamlit frontend — SME Productivity Assessment Platform.

Layout is spec-exact (MSc assessment criteria):
  Page 1 — Input:
    - Sector selectbox (required before upload)
    - Multi-file uploader (PDF/CSV only)
    - "Run Assessment" button (disabled until sector + ≥1 file selected)
    - Stage-named spinner (parsing → embedding → retrieving → extracting → scoring)

  Page 2 — Results:
    - Composite Productivity Index (st.metric, large, 0–100) at the top
    - Labour Efficiency + Financial Health side-by-side (st.columns)
      Each pillar: st.progress bar with p25/p50/p75 markers, confidence, excluded metrics
    - Digital Maturity (visually distinct with st.info, explicit diagnostic label)
    - Non-dismissible warning banner (st.warning, always visible)
    - Recommendations as st.expander with source passages inside each expander

Default Streamlit widgets ONLY — no custom HTML/CSS injection.
"""

import time
from typing import Any, Dict, List

import requests
import streamlit as st

# ── Page config ────────────────────────────────────────────────
st.set_page_config(
    page_title="SME Productivity Assessment",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

API_BASE_URL = "http://localhost:8000"

# ── Session state initialisation ──────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "input"
if "assessment_result" not in st.session_state:
    st.session_state.assessment_result = None


# ──────────────────────────────────────────────────────────────
# Helper: benchmark bar with p25/p50/p75 markers
# ──────────────────────────────────────────────────────────────

def _render_pillar(pillar: Dict[str, Any], label: str) -> None:
    """
    Render a pillar score with a progress bar and p25/p50/p75 reference markers.
    Uses only st.metric, st.progress, st.caption, st.warning — no custom HTML.
    """
    score = pillar.get("score", 0.0)
    confidence = pillar.get("confidence", 0.0)
    excluded = pillar.get("excluded_metrics", [])
    exclusion_reasons = pillar.get("exclusion_reasons", {})

    # Confidence badge label
    if confidence >= 80:
        conf_label = "High"
    elif confidence >= 50:
        conf_label = "Medium"
    else:
        conf_label = "Low"

    st.metric(
        label=label,
        value=f"{score:.1f} / 100",
        delta=f"Confidence: {confidence:.0f}% ({conf_label})",
    )

    # Progress bar: score normalised to 0–1
    st.progress(score / 100.0)

    # p25 / p50 / p75 reference lines shown as text caption
    st.caption(
        "Sector reference: p25 = 25  |  p50 = 50  |  p75 = 75  "
        "(higher = closer to top quartile)"
    )

    # Excluded metrics (if any)
    if excluded:
        st.warning(
            f"**Excluded from {label} score** (missing data — not imputed):\n"
            + "\n".join(
                f"- **{m}**: {exclusion_reasons.get(m, 'input value not found')}"
                for m in excluded
            )
        )


# ──────────────────────────────────────────────────────────────
# PAGE 1 — Input
# ──────────────────────────────────────────────────────────────

def render_input_page() -> None:
    st.title("📊 SME Productivity Assessment")
    st.markdown(
        "Upload your business documents (PDF or CSV) to receive a "
        "data-driven productivity assessment against sector benchmarks."
    )

    st.divider()

    # Step 1: Sector selector (required first)
    st.subheader("Step 1 — Select Sector")
    sector = st.selectbox(
        "Business sector",
        options=["", "Retail", "Services", "Manufacturing"],
        index=0,
        help="Scores are normalised against sector-specific ONS/OECD benchmark percentiles.",
    )

    st.subheader("Step 2 — Upload Documents")
    uploaded_files = st.file_uploader(
        "Upload PDF and/or CSV files (multiple allowed)",
        type=["pdf", "csv"],
        accept_multiple_files=True,
        help="Accepted: annual accounts (PDF), financial data exports (CSV).",
    )

    company_name = st.text_input(
        "Company name (optional)",
        value="",
        placeholder="e.g. Acme Ltd",
    )

    st.divider()

    # Button disabled until sector is selected and ≥1 file uploaded
    sector_selected = bool(sector)
    files_present = bool(uploaded_files)
    button_disabled = not (sector_selected and files_present)

    if not sector_selected:
        st.info("Select a sector above to enable the assessment button.")
    elif not files_present:
        st.info("Upload at least one PDF or CSV file to proceed.")

    if st.button(
        "▶ Run Assessment",
        disabled=button_disabled,
        type="primary",
        help="Disabled until sector and at least one file are selected.",
    ):
        _run_assessment(uploaded_files, company_name, sector)


def _run_assessment(
    uploaded_files: List[Any],
    company_name: str,
    sector: str,
) -> None:
    """Submit files to the API with per-stage status display."""
    stages = [
        ("parsing",    "📄 Parsing documents…"),
        ("embedding",  "🔢 Generating embeddings…"),
        ("retrieving", "🔍 Retrieving relevant passages…"),
        ("extracting", "🤖 Extracting metrics with AI…"),
        ("scoring",    "📊 Computing productivity scores…"),
    ]

    status_placeholder = st.empty()

    for i, (stage_key, stage_label) in enumerate(stages):
        with status_placeholder.container():
            st.info(f"**Pipeline stage {i+1}/{len(stages)}:** {stage_label}")

        # On the last stage, make the actual API call
        if i == len(stages) - 1:
            try:
                file_tuples = [
                    ("files", (f.name, f.getvalue(), "application/octet-stream"))
                    for f in uploaded_files
                ]
                data = {
                    "company_name": company_name or "Unknown",
                    "sector": sector,
                }
                with st.spinner("Finalising assessment…"):
                    response = requests.post(
                        f"{API_BASE_URL}/assess",
                        files=file_tuples,
                        data=data,
                        timeout=120,
                    )

                status_placeholder.empty()

                if response.status_code == 200:
                    body = response.json()
                    if body.get("status") == "success":
                        st.session_state.assessment_result = body["result"]
                        st.session_state.page = "results"
                        st.rerun()
                    else:
                        st.error(f"Assessment failed: {body.get('message', 'Unknown error')}")
                else:
                    st.error(f"API error {response.status_code}: {response.text[:400]}")
            except requests.exceptions.ConnectionError:
                status_placeholder.empty()
                st.error(
                    "Could not connect to the backend API. "
                    "Ensure the FastAPI server is running on http://localhost:8000"
                )
            except Exception as exc:
                status_placeholder.empty()
                st.error(f"Unexpected error: {exc}")
        else:
            time.sleep(0.3)  # brief visual delay between stage labels


# ──────────────────────────────────────────────────────────────
# PAGE 2 — Results
# ──────────────────────────────────────────────────────────────

def render_results_page() -> None:
    res = st.session_state.assessment_result

    if not res:
        st.warning("No assessment data found. Please run an assessment first.")
        if st.button("← Back to Upload"):
            st.session_state.page = "input"
            st.rerun()
        return

    # ── Non-dismissible warning banner (always visible, top of page) ──
    st.warning(
        "⚠️ **Important:** Firm-level productivity scores measure aggregate business "
        "performance and are **not** an indicator of individual employee productivity or value."
    )

    st.title(f"Assessment Results — {res.get('company_name', 'Company')}")
    st.caption(f"Sector: **{res.get('sector', 'N/A')}**  |  "
               f"Run ID: `{res.get('run_id', 'N/A')}`")

    st.divider()

    # ── Composite Productivity Index (large, top) ──────────────
    st.subheader("Composite Productivity Index")
    composite = res.get("productivity_index", 0.0)
    labour = res.get("labour_efficiency", {})
    financial = res.get("financial_health", {})

    # Show overall composite prominently
    st.metric(
        label="Productivity Index (0–100)",
        value=f"{composite:.1f}",
        help=(
            "Equal-weighted average of Labour Efficiency and Financial Health pillar scores. "
            "Digital Maturity is a separate diagnostic input and is NOT included here."
        ),
    )
    st.progress(composite / 100.0)
    st.caption(
        "Interpretation: 0–33 = below sector p25  |  "
        "34–66 = between p25 and p75  |  "
        "67–100 = above sector p75"
    )

    st.divider()

    # ── Two pillar scores side-by-side ─────────────────────────
    st.subheader("Pillar Scores")
    col1, col2 = st.columns(2)

    with col1:
        _render_pillar(labour, "Labour Efficiency")

    with col2:
        _render_pillar(financial, "Financial Health")

    st.divider()

    # ── Digital Maturity (visually distinct — diagnostic only) ─
    digital = res.get("digital_maturity", {})
    dig_score = digital.get("score", 0.0)
    dig_level = digital.get("level", "N/A")
    dig_tools = digital.get("tools_identified", [])
    dig_auto   = digital.get("automation_detected", False)
    dig_procs  = digital.get("process_indicators", [])

    # Wrap in st.info for distinct visual treatment (blue tint, different icon)
    with st.container(border=True):
        st.info(
            "🔬 **Digital Maturity — Diagnostic Input**  \n"
            "This score is a **diagnostic axis only** and is **not** included in "
            "the Composite Productivity Index above."
        )
        col_a, col_b = st.columns([1, 2])
        with col_a:
            st.metric(
                label="Digital Maturity Score (0–100)",
                value=f"{dig_score:.0f}",
                delta=f"Level: {dig_level}",
            )
            st.progress(dig_score / 100.0)
        with col_b:
            if dig_tools:
                st.markdown("**Software tools identified:**")
                st.write(", ".join(dig_tools))
            else:
                st.markdown("*No specific software tools identified in documents.*")
            st.markdown(
                f"**Automation language detected:** {'Yes ✓' if dig_auto else 'No'}"
            )
            if dig_procs:
                st.markdown("**Digital process indicators:**")
                for ind in dig_procs:
                    st.write(f"• {ind}")

    st.divider()

    # ── Conflict warnings ──────────────────────────────────────
    conflicts = res.get("conflict_warnings", [])
    if conflicts:
        st.error(f"⚡ **{len(conflicts)} conflicting metric value(s) detected**")
        for cw in conflicts:
            st.warning(
                f"**{cw['metric_name']}** — two source passages returned values "
                f"differing by {cw['discrepancy_pct']:.1f}%:  \n"
                f"Value A: `{cw['value_a']}` — *\"{cw['passage_a'][:120]}…\"*  \n"
                f"Value B: `{cw['value_b']}` — *\"{cw['passage_b'][:120]}…\"*  \n"
                "The first extracted value was retained. Verify manually."
            )
        st.divider()

    # ── Extraction errors ──────────────────────────────────────
    errors = res.get("extraction_errors", [])
    if errors:
        with st.expander(f"⚠️ {len(errors)} extraction error(s) — expand for details"):
            for err in errors:
                st.error(
                    f"**{err['metric_name']}** — {err['error_detail']}  \n"
                    f"Raw response: `{err['raw_response'][:200]}`"
                )

    # ── Recommendations (ranked, expandable with source passages) ──
    st.subheader("Recommendations")
    recommendations = res.get("recommendations", [])
    if not recommendations:
        st.info("No recommendations generated.")
    else:
        for rec in sorted(recommendations, key=lambda r: r.get("rank", 999)):
            priority = rec.get("priority", "Medium")
            pillar   = rec.get("pillar", "")
            text     = rec.get("text", "")
            passages = rec.get("source_passages", [])

            # Priority icon
            icon = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(priority, "⚪")

            with st.expander(
                f"{icon} **[{priority} Priority — {pillar}]** {text[:80]}…",
                expanded=(priority == "High"),
            ):
                st.markdown(f"**Recommendation:** {text}")

                if passages:
                    st.markdown("**Source passage(s) from uploaded documents:**")
                    for i, passage in enumerate(passages, 1):
                        if passage:
                            st.markdown(
                                f"> *Passage {i}:* \"{passage[:400]}"
                                f"{'…' if len(passage) > 400 else ''}\""
                            )
                else:
                    st.caption("*(No specific source passage available for this recommendation.)*")

    st.divider()

    # ── Back navigation ────────────────────────────────────────
    if st.button("← Run Another Assessment"):
        st.session_state.page = "input"
        st.session_state.assessment_result = None
        st.rerun()


# ──────────────────────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────────────────────

if st.session_state.page == "input":
    render_input_page()
elif st.session_state.page == "results":
    render_results_page()
else:
    st.session_state.page = "input"
    st.rerun()
