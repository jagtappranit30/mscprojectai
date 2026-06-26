import streamlit as st
from datetime import datetime

st.set_page_config(page_title="Assessment Results", layout="wide")

# Inject Custom Beautiful Dark Design System
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .accent-card {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1.8rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(8px);
    }
    
    .metric-badge {
        font-size: 0.95rem;
        padding: 0.3rem 0.8rem;
        border-radius: 9999px;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 0.5rem;
    }
    
    .badge-above {
        background-color: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    
    .badge-at {
        background-color: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    
    .badge-below {
        background-color: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Your Productivity Assessment Results")

# Check if result exists
if "last_result" not in st.session_state:
    st.warning("⚠️ No assessment results available. Please run an assessment first.")
    if st.button("← Back to Input Page"):
        st.switch_page("app.py")
    st.stop()

result = st.session_state.last_result

# Display metadata
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown('<div class="accent-card">', unsafe_allow_html=True)
    st.metric("Company Name", result.get("company_name", "Unknown"))
    st.markdown('</div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="accent-card">', unsafe_allow_html=True)
    st.metric("Business Sector", result.get("sector", "Unknown"))
    st.markdown('</div>', unsafe_allow_html=True)
with col3:
    st.markdown('<div class="accent-card">', unsafe_allow_html=True)
    st.metric("AI Confidence Level", f"{result.get('confidence_overall', 0.0):.1f}%")
    st.markdown('</div>', unsafe_allow_html=True)

st.divider()

# Main productivity index (large card)
col_left, col_right = st.columns([3, 2])

with col_left:
    index = result.get("productivity_index", 0.0)
    
    # Custom colored card based on productivity score
    if index >= 67.0:
        gradient = "linear-gradient(135deg, #059669 0%, #10b981 100%)"
        status_text = "🟢 Above Sector Median Performance"
        badge_cls = "badge-above"
    elif index >= 45.0:
        gradient = "linear-gradient(135deg, #d97706 0%, #f59e0b 100%)"
        status_text = "🟡 At Sector Median Performance"
        badge_cls = "badge-at"
    else:
        gradient = "linear-gradient(135deg, #dc2626 0%, #ef4444 100%)"
        status_text = "🔴 Below Sector Median Performance"
        badge_cls = "badge-below"
        
    st.markdown(f"""
    <div style='background: {gradient}; padding: 40px; border-radius: 16px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.25);'>
        <h2 style='color: white; margin: 0; font-size: 1.8rem; font-weight: 600;'>Productivity Index</h2>
        <h1 style='color: white; margin: 15px 0; font-size: 4.5rem; font-weight: 800;'>{index:.1f}/100</h1>
        <p style='color: rgba(255,255,255,0.9); margin: 0; font-size: 1.2rem; font-weight: 500;'>{status_text}</p>
    </div>
    """, unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="accent-card" style="height: 100%;">', unsafe_allow_html=True)
    st.markdown("### Pillar Contribution")
    
    # Progress bars and values
    labour_score = result.get("labour_efficiency_score", 0.0)
    financial_score = result.get("financial_health_score", 0.0)
    
    st.write(f"**Labour Efficiency Score:** {labour_score:.1f} / 50")
    st.progress(min(max(labour_score / 50.0, 0.0), 1.0))
    
    st.write(f"**Financial Health Score:** {financial_score:.1f} / 50")
    st.progress(min(max(financial_score / 50.0, 0.0), 1.0))
    st.markdown('</div>', unsafe_allow_html=True)

st.divider()

# Detailed metrics tabs
tab1, tab2, tab3 = st.tabs(["👥 Labour Efficiency Metrics", "📈 Financial Health Benchmarks", "💻 Digital Maturity Check"])

with tab1:
    st.markdown('<div class="accent-card">', unsafe_allow_html=True)
    st.subheader("Labour Efficiency Breakdown")
    
    c1, c2 = st.columns(2)
    with c1:
        st.metric(
            label="Your Revenue per Employee", 
            value=f"£{result.get('revenue_per_employee', 0.0):,.0f}",
            delta=f"Sector Median: £{result.get('sector_benchmark_revenue_per_emp', 0.0):,.0f}"
        )
    with c2:
        st.metric(
            label="Your Output per Payroll £", 
            value=f"{result.get('output_per_payroll', 0.0):.2f}",
            delta=f"Sector Median: {result.get('sector_benchmark_output_per_payroll', 0.0):.2f}"
        )
        
    st.markdown("""
    *Labour Efficiency evaluates the effectiveness of workforce deployment. Scoring points are calculated based on your productivity against sector benchmarks.*
    """)
    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="accent-card">', unsafe_allow_html=True)
    st.subheader("Financial Health Analysis")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(
            label="Your Gross Margin",
            value=f"{result.get('gross_margin', 0.0):.1f}%",
            delta=f"Sector Median: {result.get('sector_benchmark_gross_margin', 0.0):.1f}%"
        )
    with c2:
        st.metric(
            label="Your Operating Margin",
            value=f"{result.get('operating_margin', 0.0):.1f}%",
            delta=f"Sector Median: {result.get('sector_benchmark_operating_margin', 0.0):.1f}%"
        )
    with c3:
        st.metric(
            label="Your Current Ratio (Liquidity)",
            value=f"{result.get('current_ratio', 0.0):.2f}x",
            delta="Healthy Target: 1.5x - 2.0x"
        )
    st.markdown('</div>', unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="accent-card">', unsafe_allow_html=True)
    st.subheader("Digital Maturity Diagnosis")
    
    col_mat_1, col_mat_2 = st.columns(2)
    with col_mat_1:
        st.metric("Identified Maturity level", result.get("digital_maturity_level", "Low"))
    with col_mat_2:
        st.metric("Diagnostic Score (Out of 100)", f"{result.get('digital_maturity_score', 0.0):.0f}")
        
    st.markdown("#### Software & Tools Identified in Document Source:")
    st.info(result.get("digital_tools_identified", "None specifically identified in the uploaded statement."))
    st.markdown('</div>', unsafe_allow_html=True)

# Recommendations
st.markdown("## 💡 Actionable Insights & Recommendations")
recommendations = result.get("recommendations", [])
if isinstance(recommendations, list):
    for rec in recommendations:
        st.markdown(f"- {rec}")
else:
    # Split newline separated recommendations
    for rec in recommendations.split('\n'):
        if rec.strip():
            st.markdown(f"- {rec.strip()}")

st.divider()

# Navigation actions
col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("← Upload Another Document", use_container_width=True):
        st.switch_page("app.py")
with col_btn2:
    if st.button("📥 Download PDF Report (Coming Soon)", use_container_width=True):
        st.info("The PDF download service is currently in staging phase.")
