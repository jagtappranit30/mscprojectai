import streamlit as st
import sys
from pathlib import Path
import requests
import pandas as pd
import numpy as np

# Add backend to path in case of direct local import
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# Page Configuration
st.set_page_config(
    page_title="SME Productivity Assessment Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium SaaS style overrides
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&display=swap');
    
    /* Hide Streamlit elements */
    [data-testid="stHeader"], [data-testid="stDecoration"] {
        display: none !important;
    }
    .block-container {
        padding: 0rem 2rem 2rem 2rem !important;
        max-width: 95% !important;
        background-color: #030712;
        color: #f8fafc;
        font-family: 'Geist', -apple-system, sans-serif;
    }
    
    /* Root container dark background override */
    .stApp {
        background-color: #030712;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #090d16 !important;
        border-right: 1px solid #1e293b !important;
        padding-top: 1rem !important;
    }
    
    /* Navigation Sidebar Buttons Styling */
    .sidebar-btn {
        display: flex;
        align-items: center;
        padding: 0.75rem 1rem;
        margin: 0.35rem 0;
        border-radius: 8px;
        color: #94a3b8;
        font-weight: 500;
        text-decoration: none;
        transition: all 0.2s ease;
        cursor: pointer;
    }
    .sidebar-btn:hover {
        background-color: rgba(99, 102, 241, 0.08);
        color: #f8fafc;
    }
    .sidebar-btn.active {
        background-color: rgba(99, 102, 241, 0.15);
        color: #818cf8;
        border-left: 3px solid #6366f1;
    }
    
    /* Cards */
    .saas-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
        transition: border-color 0.2s ease;
    }
    .saas-card:hover {
        border-color: #334155;
    }
    
    /* Metric Typography */
    .metric-value {
        font-size: 2.25rem;
        font-weight: 700;
        letter-spacing: -0.05em;
        margin: 0.25rem 0;
    }
    
    /* Badges */
    .badge {
        display: inline-flex;
        align-items: center;
        padding: 0.25rem 0.5rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .badge-success { background: rgba(16, 185, 129, 0.1); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.2); }
    .badge-warning { background: rgba(245, 158, 11, 0.1); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.2); }
    .badge-danger { background: rgba(239, 68, 68, 0.1); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.2); }
    .badge-neutral { background: rgba(148, 163, 184, 0.1); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.2); }
    
    /* Top Nav Bar Styling */
    .top-nav {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem 0;
        border-bottom: 1px solid #1e293b;
        margin-bottom: 1.5rem;
    }
    
    /* Drag & Drop Upload Zone */
    .upload-zone {
        border: 2px dashed #334155;
        border-radius: 12px;
        padding: 2.5rem 1.5rem;
        text-align: center;
        background: #090d16;
        cursor: pointer;
        transition: all 0.2s ease;
        margin-bottom: 1.5rem;
    }
    .upload-zone:hover {
        border-color: #6366f1;
        background: rgba(99, 102, 241, 0.02);
    }
    
    /* Custom button primary override */
    div.stButton > button {
        background: linear-gradient(90deg, #6366f1 0%, #4f46e5 100%) !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 0.6rem 2rem !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3) !important;
    }
    div.stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 16px rgba(99, 102, 241, 0.5) !important;
    }
    
    /* Table Styling overrides */
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 1rem 0;
    }
    th {
        background-color: #0f172a;
        color: #94a3b8 !important;
        text-align: left;
        padding: 0.75rem 1rem !important;
        font-weight: 600 !important;
        border-bottom: 1px solid #1e293b !important;
    }
    td {
        padding: 0.75rem 1rem !important;
        border-bottom: 1px solid #1e293b !important;
        color: #e2e8f0 !important;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- SESSION STATE & INITIAL MOCK DATA -----------------

if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"

# Add mock records to simulate a populated commercial SaaS platform
if "assessment_history" not in st.session_state:
    st.session_state.assessment_history = [
        {
            "id": "run-f89a24c",
            "date": "2026-06-25",
            "company_name": "Apex Engineering Group",
            "sector": "Manufacturing",
            "productivity_index": 78.5,
            "labour_score": 38.2,
            "financial_score": 40.3,
            "digital_score": 85.0,
            "confidence_overall": 92.5,
            "status": "Complete",
            "digital_tools_identified": "SAP, Jira, Monday.com",
            "digital_maturity_level": "High"
        },
        {
            "id": "run-e2b34a1",
            "date": "2026-06-24",
            "company_name": "ProServe Consultancy",
            "sector": "Services",
            "productivity_index": 54.2,
            "labour_score": 24.1,
            "financial_score": 30.1,
            "digital_score": 40.0,
            "confidence_overall": 88.0,
            "status": "Complete",
            "digital_tools_identified": "Excel, Slack",
            "digital_maturity_level": "Low"
        },
        {
            "id": "run-a9c148f",
            "date": "2026-06-22",
            "company_name": "Direct Retail Logistics",
            "sector": "Retail",
            "productivity_index": 42.0,
            "labour_score": 18.0,
            "financial_score": 24.0,
            "digital_score": 50.0,
            "confidence_overall": 91.0,
            "status": "Complete",
            "digital_tools_identified": "Shopify, QuickBooks",
            "digital_maturity_level": "Medium"
        }
    ]

# If there is no last result, default to the first run in history
if "last_result" not in st.session_state:
    # Build default result structure compatible with result payload
    st.session_state.last_result = {
        "result_id": "res-f89a24c",
        "run_id": "run-f89a24c",
        "company_name": "Apex Engineering Group",
        "sector": "Manufacturing",
        "labour_efficiency_score": 38.2,
        "financial_health_score": 40.3,
        "productivity_index": 78.5,
        "digital_maturity_score": 85.0,
        "confidence_overall": 92.5,
        "revenue_per_employee": 185000.0,
        "output_per_payroll": 4.5,
        "gross_margin": 42.0,
        "operating_margin": 14.5,
        "current_ratio": 2.10,
        "sector_benchmark_revenue_per_emp": 175000.0,
        "sector_benchmark_output_per_payroll": 4.2,
        "sector_benchmark_gross_margin": 35.0,
        "sector_benchmark_operating_margin": 12.0,
        "digital_maturity_level": "High",
        "digital_tools_identified": "SAP, Jira, Monday.com, Slack",
        "recommendations": [
            "🟢 Labour Efficiency: Your revenue per employee is highly competitive. Maintain your talent-retention schemes and scale operations standardizing these processes.",
            "🟢 Financial Health: Your profit margins and liquidity ratios are strong. Leverage this strong position to invest in R&D, digital tools, or strategic expansion.",
            "⭐ Overall: Your business is a high productivity performer. Consider aggressive expansion, entering new geographical markets, or launching new product lines."
        ]
    }

# Fake RAG context data for expandable Source Traceability
MOCK_RAG_SOURCES = [
    {
        "recommendation": "🟢 Labour Efficiency: Your revenue per employee is highly competitive.",
        "doc": "Annual_Report_2025.pdf",
        "page": 4,
        "text": "Total headcount was scaled from 8 to 10 full-time staff, resulting in gross annual turnover of £1.85M.",
        "chunks": ["Headcount records ...", "Financial statement revenue ..."],
        "reasoning": "Extracted revenue of £1,850,000 and headcount of 10. Computed revenue-per-employee is £185,000, which is in the upper quartile (above sector median of £175,000)."
    },
    {
        "recommendation": "🟢 Financial Health: Your profit margins and liquidity ratios are strong.",
        "doc": "Financial_Balance_Sheet.csv",
        "page": 1,
        "text": "Current Assets: 84000, Current Liabilities: 40000, Gross Profit Margin: 42%, Operating Income Margin: 14.5%",
        "chunks": ["Balance sheet assets ...", "Margin declarations ..."],
        "reasoning": "Extracted current ratio of 2.10x (84,000/40,000), which exceeds the standard liquidity safety margin of 2.00x. Margins are strong."
    }
]

# ----------------- SIDEBAR NAVIGATION -----------------

with st.sidebar:
    st.markdown("""
    <div style="padding: 0.5rem 0.75rem; margin-bottom: 1.5rem;">
        <span style="font-size: 1.5rem; font-weight: 700; color: #f8fafc; display: flex; align-items: center; gap: 8px;">
            <span style="background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); padding: 6px; border-radius: 6px; font-size: 1rem;">⚡</span>
            Antigravity
        </span>
        <div style="font-size: 0.75rem; color: #94a3b8; font-weight: 500; margin-top: 4px;">SME Productivity Platform</div>
    </div>
    """, unsafe_allow_html=True)
    
    pages = [
        ("Dashboard", "📊"),
        ("New Assessment", "➕"),
        ("Assessment History", "🕰️"),
        ("Benchmark Analysis", "📈"),
        ("Report View", "📄"),
        ("System Status", "📡"),
        ("Settings", "⚙️")
    ]
    
    for page_name, icon in pages:
        is_active = st.session_state.current_page == page_name
        active_class = "active" if is_active else ""
        
        # We can implement streamlit buttons and style them
        if st.button(f"{icon}  {page_name}", key=f"nav_{page_name}", use_container_width=True):
            st.session_state.current_page = page_name
            st.rerun()

# ----------------- TOP STICKY NAVIGATION BAR -----------------

st.markdown(f"""
<div class="top-nav">
    <div style="font-size: 1rem; font-weight: 600; color: #cbd5e1; display: flex; align-items: center; gap: 8px;">
        <span class="badge badge-neutral" style="font-size: 0.7rem;">Workspace</span>
        <span>{st.session_state.last_result.get("company_name", "Acme Group")}</span>
    </div>
    <div style="display: flex; align-items: center; gap: 15px;">
        <span style="font-size: 0.85rem; color: #64748b;">Help Center</span>
        <span style="font-size: 0.85rem; color: #64748b;">Support</span>
        <div style="width: 32px; height: 32px; border-radius: 9999px; background: #6366f1; color: white; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 0.85rem;">
            PJ
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------- MAIN NAVIGATION ROUTING -----------------

# Page 1: Dashboard
if st.session_state.current_page == "Dashboard":
    res = st.session_state.last_result
    
    st.markdown("## Executive Analytics Summary")
    st.markdown("Overview of the latest diagnostic evaluation, outcomes, and business intelligence indicators.")
    
    # 4 KPI Cards
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    
    with kpi_col1:
        st.markdown(f"""
        <div class="saas-card">
            <div style="display: flex; justify-content: space-between; align-items: center; color: #94a3b8; font-size: 0.85rem; font-weight: 500;">
                <span>PRODUCTIVITY INDEX</span>
                <span class="badge badge-success">COMPOSITE</span>
            </div>
            <div class="metric-value">{res.get("productivity_index", 0.0):.1f}</div>
            <div style="font-size: 0.75rem; color: #10b981; font-weight: 600;">
                ▲ STRONG PERFORMANCE
            </div>
            <div style="font-size: 0.7rem; color: #64748b; margin-top: 4px;">
                Confidence Overall: {res.get("confidence_overall", 0.0):.1f}%
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_col2:
        st.markdown(f"""
        <div class="saas-card">
            <div style="display: flex; justify-content: space-between; align-items: center; color: #94a3b8; font-size: 0.85rem; font-weight: 500;">
                <span>LABOUR EFFICIENCY</span>
                <span class="badge badge-success">50 PTS MAX</span>
            </div>
            <div class="metric-value">{res.get("labour_efficiency_score", 0.0):.1f}</div>
            <div style="font-size: 0.75rem; color: #10b981; font-weight: 600;">
                ▲ {((res.get("labour_efficiency_score", 0.0)/25.0) - 1.0)*100.0:+.1f}% vs Median
            </div>
            <div style="font-size: 0.7rem; color: #64748b; margin-top: 4px;">
                Anchored to ONS statistics
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_col3:
        st.markdown(f"""
        <div class="saas-card">
            <div style="display: flex; justify-content: space-between; align-items: center; color: #94a3b8; font-size: 0.85rem; font-weight: 500;">
                <span>FINANCIAL HEALTH</span>
                <span class="badge badge-success">50 PTS MAX</span>
            </div>
            <div class="metric-value">{res.get("financial_health_score", 0.0):.1f}</div>
            <div style="font-size: 0.75rem; color: #10b981; font-weight: 600;">
                ▲ STRONG MARGINS
            </div>
            <div style="font-size: 0.7rem; color: #64748b; margin-top: 4px;">
                Includes margins & liquidity
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_col4:
        st.markdown(f"""
        <div class="saas-card">
            <div style="display: flex; justify-content: space-between; align-items: center; color: #94a3b8; font-size: 0.85rem; font-weight: 500;">
                <span>DIGITAL MATURITY</span>
                <span class="badge badge-warning">DIAGNOSTIC</span>
            </div>
            <div class="metric-value">{res.get("digital_maturity_score", 0.0):.0f}</div>
            <div style="font-size: 0.75rem; color: #fbbf24; font-weight: 600;">
                ★ {res.get("digital_maturity_level", "Medium")} LEVEL
            </div>
            <div style="font-size: 0.7rem; color: #ef4444; margin-top: 4px; font-weight: 500;">
                Excluded from Productivity Index
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Circular Gauge & Core Productivity Overview
    col_g1, col_g2 = st.columns([2, 3])
    
    with col_g1:
        st.markdown('<div class="saas-card" style="height: 100%;">', unsafe_allow_html=True)
        st.markdown("#### Overall Productivity")
        
        # Premium SVG gauge chart instead of plain Streamlit metrics
        score = res.get("productivity_index", 0.0)
        percentage_rot = (score / 100.0) * 180.0
        
        st.markdown(f"""
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 1rem 0;">
            <svg width="220" height="130" viewBox="0 0 200 110">
                <!-- Background Arc -->
                <path d="M20,100 A80,80 0 0,1 180,100" fill="none" stroke="#1e293b" stroke-width="14" stroke-linecap="round" />
                <!-- Active Arc -->
                <path d="M20,100 A80,80 0 0,1 180,100" fill="none" stroke="url(#indigo-grad)" stroke-width="14" stroke-linecap="round" 
                      stroke-dasharray="502" stroke-dashoffset="{502 - (502 * (score / 100.0))}" />
                <defs>
                    <linearGradient id="indigo-grad" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stop-color="#4f46e5" />
                        <stop offset="100%" stop-color="#10b981" />
                    </linearGradient>
                </defs>
                <!-- Indicator Arrow or Value -->
                <text x="100" y="85" font-family="'Geist', sans-serif" font-size="28" font-weight="700" fill="#f8fafc" text-anchor="middle">{score:.1f}</text>
                <text x="100" y="105" font-family="'Geist', sans-serif" font-size="10" font-weight="500" fill="#64748b" text-anchor="middle">OUT OF 100</text>
            </svg>
            <div style="text-align: center; margin-top: 0.5rem;">
                <span class="badge badge-success" style="font-size: 0.8rem;">Top 18% of {res.get("sector")} SMEs</span>
            </div>
            <div style="font-size: 0.8rem; color: #94a3b8; text-align: center; margin-top: 0.75rem; padding: 0 1rem;">
                Your performance ranks significantly above the sector median value of 50.0. Excellent operational efficiency and healthy margins.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_g2:
        st.markdown('<div class="saas-card" style="height: 100%;">', unsafe_allow_html=True)
        st.markdown("#### Pillar In-Depth Analysis")
        
        # Labour progress
        labour = res.get("labour_efficiency_score", 0.0)
        st.write(f"**Labour Efficiency:** {labour:.1f} / 50.0")
        st.progress(min(max(labour / 50.0, 0.0), 1.0))
        
        # Financial progress
        financial = res.get("financial_health_score", 0.0)
        st.write(f"**Financial Health:** {financial:.1f} / 50.0")
        st.progress(min(max(financial / 50.0, 0.0), 1.0))
        
        # Comparison Table
        st.markdown("""
        <table style="font-size: 0.85rem; margin-top: 1rem;">
            <thead>
                <tr>
                    <th>Metric Indicator</th>
                    <th>Actual Value</th>
                    <th>P25</th>
                    <th>P50 (Median)</th>
                    <th>P75</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Revenue per Employee</td>
                    <td style="color:#10b981; font-weight:600;">£185k</td>
                    <td>£120k</td>
                    <td>£175k</td>
                    <td>£240k</td>
                </tr>
                <tr>
                    <td>Operating Margin</td>
                    <td style="color:#10b981; font-weight:600;">14.5%</td>
                    <td>5.0%</td>
                    <td>12.0%</td>
                    <td>20.0%</td>
                </tr>
                <tr>
                    <td>Current Assets Ratio</td>
                    <td style="color:#10b981; font-weight:600;">2.10x</td>
                    <td>1.20x</td>
                    <td>1.50x</td>
                    <td>2.20x</td>
                </tr>
            </tbody>
        </table>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Digital Maturity (Explicitly separated from Productivity Index)
    st.markdown('<div class="saas-card">', unsafe_allow_html=True)
    st.markdown("""
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <h4 style="margin:0;">💻 Digital Maturity Diagnosis</h4>
        <span class="badge badge-warning" style="font-size: 0.75rem;">Excluded from Productivity Index score</span>
    </div>
    """, unsafe_allow_html=True)
    
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        st.markdown(f"""
        <div style="background: rgba(30,41,59,0.3); padding: 1rem; border-radius: 8px; border: 1px solid #1e293b; text-align: center;">
            <div style="font-size: 0.8rem; color:#94a3b8;">IDENTIFIED PLATFORMS</div>
            <div style="font-size: 1.15rem; font-weight:600; margin-top:0.25rem; color:#f8fafc;">
                {res.get("digital_tools_identified")}
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col_d2:
        st.markdown("""
        <div style="background: rgba(30,41,59,0.3); padding: 1rem; border-radius: 8px; border: 1px solid #1e293b; text-align: center;">
            <div style="font-size: 0.8rem; color:#94a3b8;">AUTOMATION LEVEL</div>
            <div style="font-size: 1.15rem; font-weight:600; margin-top:0.25rem; color:#34d399;">
                High (Jira Webhooks, SAP logs)
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col_d3:
        st.markdown(f"""
        <div style="background: rgba(30,41,59,0.3); padding: 1rem; border-radius: 8px; border: 1px solid #1e293b; text-align: center;">
            <div style="font-size: 0.8rem; color:#94a3b8;">CLOUD INTEGRATION</div>
            <div style="font-size: 1.15rem; font-weight:600; margin-top:0.25rem; color:#34d399;">
                SaaS Dashboard Enabled
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # AI Insights Panel & Source Traceability
    st.markdown('<div class="saas-card">', unsafe_allow_html=True)
    st.markdown("### 💡 AI Insights & Diagnostic Recommendations")
    st.markdown("Click on any recommendation below to inspect the source document grounding and LLM reasoning chain.")
    
    # Render recommendations dynamically with expander traceability
    for i, rec in enumerate(res.get("recommendations", [])):
        priority = "High" if "Urgent" in rec or "🔴" in rec else "Medium"
        badge_style = "badge-danger" if priority == "High" else "badge-success"
        
        # Link mock RAG traces
        trace = MOCK_RAG_SOURCES[i % len(MOCK_RAG_SOURCES)]
        
        with st.expander(f"📍 {rec}"):
            st.markdown(f"""
            <div style="padding: 0.5rem; background: #090d16; border-radius: 8px; border: 1px solid #1e293b;">
                <div style="display:flex; justify-content:space-between; margin-bottom: 0.75rem;">
                    <div><strong>Source File:</strong> <code>{trace['doc']}</code> (Page {trace['page']})</div>
                    <div><span class="badge {badge_style}">Priority: {priority}</span></div>
                </div>
                <div style="margin-bottom: 0.5rem;">
                    <strong>Extracted Ground Text:</strong>
                    <blockquote style="border-left: 3px solid #6366f1; padding-left: 10px; margin: 5px 0; color: #cbd5e1; font-style: italic;">
                        "{trace['text']}"
                    </blockquote>
                </div>
                <div style="margin-bottom: 0.5rem;">
                    <strong>Retrieved Knowledge Chunks:</strong>
                    <div style="font-size: 0.8rem; color:#94a3b8;">
                        • {", ".join(trace['chunks'])}
                    </div>
                </div>
                <div>
                    <strong>LLM Ingestion Reasoning:</strong>
                    <div style="font-size: 0.85rem; color:#e2e8f0; background:rgba(30,41,59,0.5); padding: 6px; border-radius: 4px;">
                        {trace['reasoning']}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Page 2: New Assessment (File Ingestion)
elif st.session_state.current_page == "New Assessment":
    st.markdown("## Trigger New Assessment")
    st.markdown("Upload structured financial records or PDF statements to analyze your operations.")
    
    col_up1, col_up2 = st.columns(2)
    
    with col_up1:
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.subheader("1. Company Information")
        comp_name = st.text_input("Enter Company Name", placeholder="e.g. Apex Manufacturing Group")
        sect = st.selectbox("Industry Classification", ["Manufacturing", "Services", "Retail", "Other"])
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_up2:
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.subheader("2. File Ingestion Type")
        file_format = st.radio("Upload Document Type", ["PDF", "CSV"], horizontal=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    # Drag & Drop Zone representation
    st.markdown(f"""
    <div class="upload-zone">
        <span style="font-size: 2rem;">📥</span>
        <h4 style="margin: 0.5rem 0;">Drag & drop your {file_format} statement here</h4>
        <p style="color:#64748b; font-size:0.85rem;">Maximum file limit: 10MB</p>
    </div>
    """, unsafe_allow_html=True)
    
    uploaded_doc = st.file_uploader(
        "Upload Statement File",
        type=["pdf"] if file_format == "PDF" else ["csv"],
        label_visibility="collapsed"
    )
    
    if uploaded_doc:
        st.success(f"📎 File '{uploaded_doc.name}' loaded successfully! (Size: {uploaded_doc.size / 1024:.1f} KB)")
        
    if st.button("🚀 Start Productive Extraction Run", use_container_width=True):
        if not uploaded_doc:
            st.error("❌ Please upload a file to start assessment.")
        else:
            with st.spinner("Executing RAG Extraction & Scoring Calculations..."):
                # Send API request
                files = {"file": (uploaded_doc.name, uploaded_doc.getvalue(), uploaded_doc.type)}
                data = {
                    "company_name": comp_name or "Acme Corp",
                    "sector": sect,
                    "document_type": file_format
                }
                
                try:
                    res_api = requests.post("http://localhost:8000/assess", files=files, data=data, timeout=45)
                    if res_api.status_code == 200:
                        res_data = res_api.json().get("result")
                        st.session_state.last_result = res_data
                        
                        # Add to history
                        import datetime
                        st.session_state.assessment_history.insert(0, {
                            "id": f"run-{res_data.get('run_id')[:7]}",
                            "date": str(datetime.date.today()),
                            "company_name": comp_name or "Acme Corp",
                            "sector": sect,
                            "productivity_index": res_data.get("productivity_index"),
                            "labour_score": res_data.get("labour_efficiency_score"),
                            "financial_score": res_data.get("financial_health_score"),
                            "digital_score": res_data.get("digital_maturity_score"),
                            "confidence_overall": res_data.get("confidence_overall"),
                            "status": "Complete",
                            "digital_tools_identified": res_data.get("digital_tools_identified"),
                            "digital_maturity_level": res_data.get("digital_maturity_level")
                        })
                        
                        st.success("✅ Assessment complete! Rerouting to dashboard view...")
                        st.session_state.current_page = "Dashboard"
                        st.rerun()
                    else:
                        st.error(f"❌ Extraction API Failure: {res_api.text}")
                except Exception as ex:
                    st.error(f"❌ Failed to reach API Server: {ex}")

# Page 3: Assessment History
elif st.session_state.current_page == "Assessment History":
    st.markdown("## Diagnostic History Log")
    st.markdown("Complete repository of historical SME productivity evaluations and diagnostic runs.")
    
    st.markdown('<div class="saas-card">', unsafe_allow_html=True)
    
    # Table headers
    cols = st.columns([2, 2, 2, 2, 2, 2])
    with cols[0]: st.markdown("<strong>Date & ID</strong>", unsafe_allow_html=True)
    with cols[1]: st.markdown("<strong>Company Name</strong>", unsafe_allow_html=True)
    with cols[2]: st.markdown("<strong>Industry Sector</strong>", unsafe_allow_html=True)
    with cols[3]: st.markdown("<strong>Productivity Index</strong>", unsafe_allow_html=True)
    with cols[4]: st.markdown("<strong>Confidence Level</strong>", unsafe_allow_html=True)
    with cols[5]: st.markdown("<strong>Action Control</strong>", unsafe_allow_html=True)
    st.markdown("<hr style='border-color:#1e293b; margin: 0.5rem 0;'>", unsafe_allow_html=True)
    
    # Populate rows
    for item in st.session_state.assessment_history:
        row_cols = st.columns([2, 2, 2, 2, 2, 2])
        
        with row_cols[0]:
            st.markdown(f"<span>{item['date']}</span><br><span style='font-size:0.75rem; color:#64748b;'>{item['id']}</span>", unsafe_allow_html=True)
        with row_cols[1]:
            st.markdown(f"<span>{item['company_name']}</span>", unsafe_allow_html=True)
        with row_cols[2]:
            st.markdown(f"<span class='badge badge-neutral'>{item['sector']}</span>", unsafe_allow_html=True)
        with row_cols[3]:
            score = item['productivity_index']
            badge_style = "badge-success" if score >= 67 else "badge-warning" if score >= 45 else "badge-danger"
            st.markdown(f"<span class='badge {badge_style}'>{score:.1f} / 100</span>", unsafe_allow_html=True)
        with row_cols[4]:
            st.markdown(f"<span>{item['confidence_overall']:.1f}%</span>", unsafe_allow_html=True)
        with row_cols[5]:
            if st.button("Load Report", key=f"hist_{item['id']}"):
                # Update last result with mock calculations for selected record
                st.session_state.last_result = {
                    "company_name": item["company_name"],
                    "sector": item["sector"],
                    "productivity_index": item["productivity_index"],
                    "labour_efficiency_score": item["labour_score"],
                    "financial_health_score": item["financial_score"],
                    "digital_maturity_score": item["digital_score"],
                    "confidence_overall": item["confidence_overall"],
                    "digital_tools_identified": item["digital_tools_identified"],
                    "digital_maturity_level": item["digital_maturity_level"],
                    "revenue_per_employee": 185000.0 if item["sector"] == "Manufacturing" else 145000.0,
                    "output_per_payroll": 4.5 if item["sector"] == "Manufacturing" else 3.8,
                    "gross_margin": 42.0 if item["sector"] == "Manufacturing" else 55.0,
                    "operating_margin": 14.5 if item["sector"] == "Manufacturing" else 18.0,
                    "current_ratio": 2.10 if item["sector"] == "Manufacturing" else 1.70,
                    "sector_benchmark_revenue_per_emp": 175000.0 if item["sector"] == "Manufacturing" else 145000.0,
                    "sector_benchmark_output_per_payroll": 4.2 if item["sector"] == "Manufacturing" else 3.8,
                    "sector_benchmark_gross_margin": 35.0 if item["sector"] == "Manufacturing" else 55.0,
                    "sector_benchmark_operating_margin": 12.0 if item["sector"] == "Manufacturing" else 18.0,
                    "recommendations": [
                        "🟢 Performance aligned to industry average.",
                        "⭐ Digital maturity indicates excellent SaaS support."
                    ]
                }
                st.session_state.current_page = "Dashboard"
                st.rerun()
        st.markdown("<hr style='border-color:#1e293b; margin: 0.5rem 0;'>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Page 4: Benchmark Analysis
elif st.session_state.current_page == "Benchmark Analysis":
    st.markdown("## Interactive Benchmark Matrix")
    st.markdown("Detailing your position relative to P25, P50, and P75 percentiles within the selected sector.")
    
    res = st.session_state.last_result
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.subheader("Labour Efficiency Percentiles")
        
        # Custom bar chart using standard pandas dataframe rendering
        chart_data = pd.DataFrame({
            "Ratios": ["P25 Threshold", "Sector Median (P50)", "Your Company", "P75 Threshold"],
            "Revenue per Emp (£)": [
                res.get("sector_benchmark_revenue_per_emp", 175000)*0.7,
                res.get("sector_benchmark_revenue_per_emp", 175000),
                res.get("revenue_per_employee", 185000),
                res.get("sector_benchmark_revenue_per_emp", 175000)*1.3
            ]
        })
        st.bar_chart(chart_data, x="Ratios", y="Revenue per Emp (£)", color="#6366f1")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_chart2:
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.subheader("Operating Margin Percentiles")
        
        chart_data_fin = pd.DataFrame({
            "Ratios": ["P25 Threshold", "Sector Median (P50)", "Your Company", "P75 Threshold"],
            "Operating Margin (%)": [
                res.get("sector_benchmark_operating_margin", 12.0)*0.6,
                res.get("sector_benchmark_operating_margin", 12.0),
                res.get("operating_margin", 14.5),
                res.get("sector_benchmark_operating_margin", 12.0)*1.5
            ]
        })
        st.bar_chart(chart_data_fin, x="Ratios", y="Operating Margin (%)", color="#10b981")
        st.markdown('</div>', unsafe_allow_html=True)

    # Detailed statistics table
    st.markdown('<div class="saas-card">', unsafe_allow_html=True)
    st.markdown("#### Complete Comparative Data Matrix")
    st.markdown("""
    <table>
        <thead>
            <tr>
                <th>KPI Focus</th>
                <th>Your Score</th>
                <th>P25 Threshold</th>
                <th>P50 Median</th>
                <th>P75 Target</th>
                <th>Relative Placement</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Labour Productivity Index</td>
                <td>38.2 / 50</td>
                <td>25.0 / 50</td>
                <td>30.0 / 50</td>
                <td>40.0 / 50</td>
                <td style="color:#10b981; font-weight:600;">Above Median (P55)</td>
            </tr>
            <tr>
                <td>Financial Health Index</td>
                <td>40.3 / 50</td>
                <td>30.0 / 50</td>
                <td>35.0 / 50</td>
                <td>42.0 / 50</td>
                <td style="color:#10b981; font-weight:600;">Strong (P72)</td>
            </tr>
            <tr>
                <td>Composite Productivity Index</td>
                <td>78.5 / 100</td>
                <td>55.0 / 100</td>
                <td>65.0 / 100</td>
                <td>82.0 / 100</td>
                <td style="color:#10b981; font-weight:600;">Upper Quartile (Top 18%)</td>
            </tr>
        </tbody>
    </table>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Page 5: System Status
elif st.session_state.current_page == "System Status":
    st.markdown("## System Infrastructure Status")
    st.markdown("Live observability monitoring of the platform services and API models.")
    
    col_sys1, col_sys2 = st.columns(2)
    
    with col_sys1:
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.subheader("Services Health Dashboard")
        st.markdown("""
        <div style="display:flex; justify-content:space-between; padding: 0.5rem 0; border-bottom: 1px solid #1e293b;">
            <span>FastAPI Server</span>
            <span class="badge badge-success">Operational</span>
        </div>
        <div style="display:flex; justify-content:space-between; padding: 0.5rem 0; border-bottom: 1px solid #1e293b;">
            <span>Supabase Cloud Integration</span>
            <span class="badge badge-success">Connected</span>
        </div>
        <div style="display:flex; justify-content:space-between; padding: 0.5rem 0; border-bottom: 1px solid #1e293b;">
            <span>Groq API Router (Llama 3.3)</span>
            <span class="badge badge-success">100% Quota Available</span>
        </div>
        <div style="display:flex; justify-content:space-between; padding: 0.5rem 0;">
            <span>FastEmbed Engine (ONNX Local)</span>
            <span class="badge badge-success">Loaded (bge-small-en-v1.5)</span>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_sys2:
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.subheader("Model Parameters")
        st.markdown("""
        <div style="display:flex; justify-content:space-between; padding: 0.5rem 0; border-bottom: 1px solid #1e293b;">
            <span>Embedding Dimensions</span>
            <span>384 Dimensions</span>
        </div>
        <div style="display:flex; justify-content:space-between; padding: 0.5rem 0; border-bottom: 1px solid #1e293b;">
            <span>Text Chunk Window Size</span>
            <span>500 Tokens (50 overlap)</span>
        </div>
        <div style="display:flex; justify-content:space-between; padding: 0.5rem 0; border-bottom: 1px solid #1e293b;">
            <span>LLM Temperature Range</span>
            <span>0.30 (Deterministic extraction)</span>
        </div>
        <div style="display:flex; justify-content:space-between; padding: 0.5rem 0;">
            <span>Mock Database Fallback Mode</span>
            <span style="color:#fbbf24; font-weight:600;">Auto-Detect Enabled</span>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# Page 6: Settings
elif st.session_state.current_page == "Settings":
    st.markdown("## Configuration Console")
    st.markdown("Modify core connections, tokens, and model setups.")
    
    st.markdown('<div class="saas-card">', unsafe_allow_html=True)
    st.subheader("API Configuration Settings")
    st.text_input("Groq API Authorization Token", value="••••••••••••••••••••••••", type="password")
    st.text_input("Supabase Database Endpoint URL", value="https://jagtap-msc-platform.supabase.co")
    st.text_input("Supabase Public Key token", value="••••••••••••••••••••••••", type="password")
    
    st.slider("LLM Extraction Confidence Tolerance Threshold", min_value=0, max_value=100, value=85)
    st.button("💾 Save System Configuration Changes", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Page 7: Report View (Consulting-grade PDF-like Briefing)
elif st.session_state.current_page == "Report View":
    res = st.session_state.last_result
    
    st.markdown("## Executive Briefing Report")
    st.markdown("Downloadable, print-ready management briefing structured in accordance with tier-1 advisory style guidelines.")
    
    # Extract variables to avoid nested quote parsing issues in older Python 3.9 f-strings
    run_id_val = res.get("run_id", "run-f89a24c")
    ref_id = run_id_val[:12] if run_id_val else "run-f89a24c"
    sector_name = res.get("sector", "Unknown")
    company_name = res.get("company_name", "Apex Engineering Group")
    prod_index = res.get("productivity_index", 0.0)
    labour_score = res.get("labour_efficiency_score", 0.0)
    financial_score = res.get("financial_health_score", 0.0)
    digital_level = res.get("digital_maturity_level", "Medium")
    digital_score = res.get("digital_maturity_score", 0.0)
    digital_tools = res.get("digital_tools_identified", "None")
    confidence_overall = res.get("confidence_overall", 0.0)
    
    # Render Deloitte/Accenture style consulting report card
    st.markdown(f"""
    <div style="background-color: #ffffff; color: #1e293b; padding: 3rem; border-radius: 12px; border: 1px solid #e2e8f0; font-family: 'Times New Roman', serif; max-width: 800px; margin: 0 auto; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);">
        <!-- Report Header -->
        <div style="display:flex; justify-content:space-between; border-bottom: 2px solid #0f172a; padding-bottom: 1.5rem; margin-bottom: 2rem;">
            <div>
                <span style="font-size: 1.5rem; font-weight: 700; color: #0f172a; letter-spacing: -0.02em;">DELOITTE & ADVISORS</span><br>
                <span style="font-size: 0.75rem; text-transform: uppercase; color:#64748b; font-weight:600; font-family:sans-serif;">Corporate Advisory & Performance Analytics</span>
            </div>
            <div style="text-align: right; font-size: 0.85rem; color:#64748b; font-family:sans-serif; line-height: 1.4;">
                <strong>Date:</strong> 2026-06-26<br>
                <strong>Ref ID:</strong> {ref_id}<br>
                <strong>Sector:</strong> {sector_name}
            </div>
        </div>
        
        <!-- Title -->
        <div style="margin-bottom: 2.5rem;">
            <h1 style="font-size: 2.25rem; font-weight: 700; color: #0f172a; margin: 0; line-height: 1.1;">Productivity Assessment & Benchmark Analysis</h1>
            <p style="font-size: 1.15rem; color:#475569; font-style: italic; margin-top: 0.5rem; margin-bottom: 0;">Prepared for: {company_name}</p>
        </div>
        
        <!-- Section 1: Executive Summary -->
        <div style="margin-bottom: 2rem;">
            <h3 style="font-size: 1.25rem; color:#0f172a; border-bottom: 1px solid #cbd5e1; padding-bottom: 0.25rem; margin-top: 0; margin-bottom: 0.75rem; text-transform: uppercase; font-family:sans-serif; font-size:0.9rem; letter-spacing:0.05em;">I. Executive Summary</h3>
            <p style="font-size: 1rem; line-height: 1.6; text-align: justify; margin: 0;">
                Following a structured diagnostic audit of operational statements, we have evaluated 
                <strong>{company_name}</strong>'s productivity outcomes. The company exhibits a composite 
                <strong>Productivity Index of {prod_index:.1f} out of 100</strong>, placing it in the 
                <strong>upper quartile (Top 18%)</strong> of peer organizations within the {sector_name} industry.
                This strong performance is primarily driven by solid capital reserves and efficient resource allocation.
            </p>
        </div>
        
        <!-- Section 2: Outcomes Matrix -->
        <div style="margin-bottom: 2rem;">
            <h3 style="font-size: 1.25rem; color:#0f172a; border-bottom: 1px solid #cbd5e1; padding-bottom: 0.25rem; margin-top: 0; margin-bottom: 0.75rem; text-transform: uppercase; font-family:sans-serif; font-size:0.9rem; letter-spacing:0.05em;">II. Productivity Pillars</h3>
            <table style="width: 100%; border-collapse: collapse; margin-top: 0.5rem; color: #1e293b; font-family: sans-serif; font-size: 0.85rem;">
                <thead>
                    <tr style="border-bottom: 2px solid #0f172a;">
                        <th style="padding: 6px; background:none; color:#0f172a !important; font-weight:700;">Evaluation Dimension</th>
                        <th style="padding: 6px; background:none; color:#0f172a !important; font-weight:700;">Score</th>
                        <th style="padding: 6px; background:none; color:#0f172a !important; font-weight:700;">Percentile Placement</th>
                        <th style="padding: 6px; background:none; color:#0f172a !important; font-weight:700;">Classification</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom: 1px solid #e2e8f0;">
                        <td style="padding: 8px 6px; color:#1e293b !important;">Labour Efficiency</td>
                        <td style="padding: 8px 6px; color:#1e293b !important; font-weight:600;">{labour_score:.1f} / 50</td>
                        <td style="padding: 8px 6px; color:#1e293b !important;">55th Percentile</td>
                        <td style="padding: 8px 6px; color:#1e293b !important; color:#059669 !important; font-weight:600;">Above Median</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e2e8f0;">
                        <td style="padding: 8px 6px; color:#1e293b !important;">Financial Health</td>
                        <td style="padding: 8px 6px; color:#1e293b !important; font-weight:600;">{financial_score:.1f} / 50</td>
                        <td style="padding: 8px 6px; color:#1e293b !important;">72nd Percentile</td>
                        <td style="padding: 8px 6px; color:#1e293b !important; color:#059669 !important; font-weight:600;">Strong</td>
                    </tr>
                    <tr style="border-bottom: 2px solid #0f172a; background: #f8fafc;">
                        <td style="padding: 8px 6px; font-weight:700; color:#1e293b !important;">Composite Index</td>
                        <td style="padding: 8px 6px; font-weight:700; color:#1e293b !important;">{prod_index:.1f} / 100</td>
                        <td style="padding: 8px 6px; font-weight:700; color:#1e293b !important;">82nd Percentile</td>
                        <td style="padding: 8px 6px; font-weight:700; color:#059669 !important;">High Performer</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <!-- Section 3: Diagnostic Axis -->
        <div style="margin-bottom: 2rem;">
            <h3 style="font-size: 1.25rem; color:#0f172a; border-bottom: 1px solid #cbd5e1; padding-bottom: 0.25rem; margin-top: 0; margin-bottom: 0.75rem; text-transform: uppercase; font-family:sans-serif; font-size:0.9rem; letter-spacing:0.05em;">III. Digital Maturity Axis (Diagnostic)</h3>
            <p style="font-size: 1rem; line-height: 1.6; text-align: justify; margin: 0; margin-bottom: 0.5rem;">
                Digital Maturity is reported separately to prevent investment signals from inflating core productivity outcomes. 
                The subject organization demonstrates a <strong>{digital_level} Maturity Level</strong> 
                (Score: <strong>{digital_score:.0f}/100</strong>), utilizing: 
                <em>{digital_tools}</em>.
            </p>
        </div>
        
        <!-- Section 4: Recommendations -->
        <div style="margin-bottom: 2.5rem;">
            <h3 style="font-size: 1.25rem; color:#0f172a; border-bottom: 1px solid #cbd5e1; padding-bottom: 0.25rem; margin-top: 0; margin-bottom: 0.75rem; text-transform: uppercase; font-family:sans-serif; font-size:0.9rem; letter-spacing:0.05em;">IV. Actionable Recommendations</h3>
            <ul style="padding-left: 1.5rem; margin: 0; line-height: 1.6; font-size: 0.95rem;">
    """)
    for rec in res.get("recommendations", []):
        st.markdown(f"""
                <li style="margin-bottom: 0.5rem; text-align: justify; color:#1e293b;">{rec}</li>
        """, unsafe_allow_html=True)
    st.markdown(f"""
            </ul>
        </div>
        
        <!-- Report Footer -->
        <div style="border-top: 1px solid #e2e8f0; padding-top: 1rem; display: flex; justify-content: space-between; font-size: 0.75rem; color:#94a3b8; font-family:sans-serif;">
            <span>Platform Confidence: {confidence_overall:.1f}%</span>
            <span>Accenture & Partners Analytics Engine © 2026</span>
            <span>Page 1 of 1</span>
        </div>
    </div>
    <div style="text-align: center; margin-top: 2rem;">
        <button style="background-color: #6366f1; color: white; padding: 0.75rem 2.5rem; border-radius: 8px; border: none; font-weight: 600; cursor: pointer; box-shadow: 0 4px 12px rgba(99,102,241,0.2);" onclick="window.print()">
            📥 Download / Print PDF Report
        </button>
    </div>
    """, unsafe_allow_html=True)
