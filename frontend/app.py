"""
Vantly Streamlit Frontend — Premium SME Productivity Assessment Platform.

Key Screens:
  - Screen 1: Landing/Marketing Page
  - Screen 2: Assessment Input Form (centered 560px card, custom styled select/upload)
  - Screen 3: Results Dashboard (circular progress ring, benchmark bar charts, detail tabs)
  - Screen 4: How It Works / Methodology (vertical timeline, FAQ accordions, formulas)
"""

import time
import requests
import streamlit as st
import sys
import socket
import subprocess
from typing import Any, Dict, List

def start_backend_if_needed() -> None:
    port = 8000
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        is_open = s.connect_ex(('127.0.0.1', port)) == 0
        
    if not is_open:
        try:
            # Launch FastAPI backend as a background process using the current python executable
            subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # Short sleep to let the server spin up
            time.sleep(2.5)
        except Exception as e:
            st.warning(f"Could not automatically launch the backend process: {e}")

# ── Page Config ────────────────────────────────────────────────
st.set_page_config(
    page_title="Vantly — See your business clearly.",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

import os
API_BASE_URL = os.getenv("API_BASE_URL", os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000"))

# ── Session State Initialisation ──────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "landing"
if "assessment_result" not in st.session_state:
    st.session_state.assessment_result = None

# ── Global CSS Injection ───────────────────────────────────────
def inject_custom_css() -> None:
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Global Styles */
    html, body, [data-testid="stAppViewContainer"] {
      background-color: #0B0E14 !important;
      color: #F5F6FA !important;
      font-family: 'Inter', -apple-system, sans-serif !important;
    }
    
    /* Header/Footer cleanups */
    header[data-testid="stHeader"] {
      visibility: hidden;
      height: 0px !important;
    }
    footer {
      visibility: hidden;
      height: 0px !important;
    }
    .block-container {
      padding-top: 1.5rem !important;
      padding-bottom: 6rem !important;
      max-width: 1200px !important;
    }
    
    /* Faint background pattern */
    .vantly-bg {
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background-image: radial-gradient(rgba(99, 102, 241, 0.07) 1px, transparent 0);
      background-size: 24px 24px;
      pointer-events: none;
      z-index: -1;
    }
    
    /* Layout Cards and Containers */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.form-card) {
      background-color: #151923 !important;
      border: 1px solid #262B38 !important;
      border-radius: 12px !important;
      padding: 36px !important;
      box-shadow: 0 4px 24px rgba(0, 0, 0, 0.45) !important;
      max-width: 560px !important;
      margin: 40px auto !important;
    }
    
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.pillar-card) {
      background-color: #151923 !important;
      border: 1px solid #262B38 !important;
      border-radius: 12px !important;
      padding: 24px !important;
      height: 100% !important;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2) !important;
    }
    
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.digital-card) {
      background-color: #151923 !important;
      border: 1px solid #262B38 !important;
      border-radius: 12px !important;
      padding: 24px !important;
      margin: 24px 0 !important;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2) !important;
    }
    
    /* Form input visual updates */
    [data-testid="stFileUploader"] {
      border: 2px dashed #262B38 !important;
      border-radius: 8px !important;
      background-color: #0B0E14 !important;
      padding: 24px !important;
      transition: border-color 0.15s ease !important;
    }
    [data-testid="stFileUploader"]:hover {
      border-color: #3D4457 !important;
    }
    [data-testid="stFileUploader"] section {
      background-color: transparent !important;
    }
    
    /* Dropdown and inputs */
    [data-testid="stSelectbox"] > div[data-baseweb="select"] > div,
    [data-testid="stTextInput"] input {
      background-color: #151923 !important;
      border: 1px solid #262B38 !important;
      border-radius: 8px !important;
      color: #F5F6FA !important;
    }
    
    /* Tab Styling (Underline-style) */
    div[data-testid="stTabs"] {
      margin-top: 32px !important;
    }
    button[data-baseweb="tab"] {
      border-bottom: 2px solid transparent !important;
      background-color: transparent !important;
      color: #9AA3B5 !important;
      font-weight: 500 !important;
      padding: 12px 20px !important;
      font-size: 14px !important;
      transition: all 0.15s ease !important;
    }
    button[data-baseweb="tab"]:hover {
      color: #F5F6FA !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
      border-bottom: 2px solid #6366F1 !important;
      color: #F5F6FA !important;
      font-weight: 600 !important;
    }
    
    /* Header/Navbar Elements */
    .custom-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 0;
      border-bottom: 1px solid #262B38;
      margin-bottom: 24px;
    }
    .logo-container {
      display: flex;
      align-items: baseline;
      gap: 8px;
    }
    .logo-text {
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.03em;
      color: #F5F6FA;
    }
    .logo-dot {
      color: #6366F1;
    }
    .logo-tagline {
      font-size: 11px;
      color: #9AA3B5;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-weight: 500;
    }
    
    /* Nav Buttons Style */
    .st-key-nav_btn_home button, 
    .st-key-nav_btn_assess button, 
    .st-key-nav_btn_meth button {
      background-color: transparent !important;
      border: none !important;
      color: #9AA3B5 !important;
      border-bottom: 2px solid transparent !important;
      border-radius: 0px !important;
      padding: 6px 12px !important;
      font-weight: 500 !important;
      font-size: 14px !important;
    }
    .st-key-nav_btn_home button:hover, 
    .st-key-nav_btn_assess button:hover, 
    .st-key-nav_btn_meth button:hover {
      color: #F5F6FA !important;
    }
    
    /* Primary buttons */
    .stButton button {
      border-radius: 8px !important;
      transition: all 0.15s ease !important;
      font-weight: 500 !important;
    }
    .stButton button[kind="primary"] {
      background-color: #6366F1 !important;
      color: #F5F6FA !important;
      border: none !important;
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25) !important;
    }
    .stButton button[kind="primary"]:hover {
      background-color: #4F52D9 !important;
      transform: translateY(-1px) !important;
      box-shadow: 0 6px 16px rgba(99, 102, 241, 0.35) !important;
    }
    .stButton button[kind="primary"]:active {
      transform: scale(0.98) !important;
    }
    
    /* Secondary buttons */
    .stButton button[kind="secondary"],
    .stButton button:not([kind="primary"]) {
      background-color: #151923 !important;
      color: #9AA3B5 !important;
      border: 1px solid #262B38 !important;
    }
    .stButton button:not([kind="primary"]):hover {
      color: #F5F6FA !important;
      border-color: #3D4457 !important;
    }
    
    /* Floating action bar styling at bottom */
    div[data-testid="stHorizontalBlock"]:has(.st-key-export_pdf_btn) {
      position: fixed !important;
      bottom: 0 !important;
      left: 0 !important;
      right: 0 !important;
      background-color: #151923 !important;
      border-top: 1px solid #262B38 !important;
      padding: 16px 10% !important;
      z-index: 99 !important;
      box-shadow: 0 -4px 20px rgba(0,0,0,0.5) !important;
      margin: 0 !important;
      width: 100% !important;
      display: flex !important;
      justify-content: flex-end !important;
      align-items: center !important;
      gap: 16px !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.st-key-export_pdf_btn) > div {
      width: auto !important;
      flex: none !important;
    }
    
    .sticky-spacer {
      height: 100px;
    }
    
    /* Landing Elements */
    .landing-hero {
      text-align: center;
      padding: 64px 0 32px 0;
    }
    .hero-tag {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      color: #6366F1;
      margin-bottom: 16px;
    }
    .hero-title {
      font-size: 52px;
      font-weight: 700;
      letter-spacing: -0.02em;
      background: linear-gradient(135deg, #F5F6FA 0%, #9AA3B5 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 16px;
    }
    .hero-subtitle {
      font-size: 17px;
      color: #9AA3B5;
      max-width: 600px;
      margin: 0 auto 32px auto;
      line-height: 1.6;
    }
    
    /* Social proof */
    .social-proof {
      text-align: center;
      margin: 48px 0;
      padding-top: 32px;
      border-top: 1px solid #262B38;
    }
    .social-proof-title {
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: #5C6478;
      margin-bottom: 20px;
    }
    .logo-grid {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 48px;
    }
    .mock-logo {
      font-size: 15px;
      font-weight: 600;
      color: #5C6478;
      letter-spacing: -0.02em;
    }
    
    /* Features */
    .feature-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 24px;
      margin-bottom: 48px;
    }
    .feature-card {
      background-color: #151923;
      border: 1px solid #262B38;
      border-radius: 12px;
      padding: 24px;
      transition: all 0.2s ease;
    }
    .feature-card:hover {
      border-color: #3D4457;
      transform: translateY(-2px);
      box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    }
    .feature-icon {
      color: #6366F1;
      margin-bottom: 16px;
    }
    .feature-title {
      font-size: 16px;
      font-weight: 600;
      color: #F5F6FA;
      margin-bottom: 8px;
    }
    .feature-desc {
      font-size: 13px;
      color: #9AA3B5;
      line-height: 1.5;
    }
    
    /* Centered Form Indicator */
    .step-indicator {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #6366F1;
      margin-bottom: 12px;
    }
    
    /* Circular Progress Design */
    .progress-ring-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      position: relative;
      margin: 24px 0;
    }
    .progress-ring-text {
      position: absolute;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
    }
    .score-number {
      font-size: 48px;
      font-weight: 700;
      font-family: monospace;
      color: #F5F6FA;
      line-height: 1;
    }
    .score-label {
      font-size: 11px;
      color: #9AA3B5;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-top: 4px;
    }
    .progress-ring__circle {
      transform: rotate(-90deg);
      transform-origin: 50% 50%;
      transition: stroke-dashoffset 0.8s ease-out;
      animation: progress-anim 0.8s ease-out forwards;
    }
    @keyframes progress-anim {
      from { stroke-dashoffset: 502.65; }
      to { stroke-dashoffset: var(--target-offset); }
    }
    
    /* Benchmark sliders */
    .benchmark-container {
      margin: 16px 0;
      position: relative;
    }
    .benchmark-ticks {
      display: flex;
      justify-content: space-between;
      font-size: 10px;
      color: #5C6478;
      margin-bottom: 6px;
      position: relative;
      height: 14px;
    }
    .benchmark-ticks span {
      position: absolute;
      transform: translateX(-50%);
    }
    .benchmark-bar-bg {
      height: 6px;
      background-color: #262B38;
      border-radius: 3px;
      position: relative;
      overflow: visible;
    }
    .benchmark-bar-fill {
      height: 100%;
      border-radius: 3px;
      transition: width 0.8s ease-out;
    }
    .benchmark-marker {
      position: absolute;
      top: 50%;
      width: 10px;
      height: 10px;
      background-color: #F5F6FA;
      border: 2px solid #0B0E14;
      border-radius: 50%;
      transform: translate(-50%, -50%);
      box-shadow: 0 0 4px rgba(255,255,255,0.6);
      transition: left 0.8s ease-out;
    }
    
    /* Custom lists / tables */
    .metrics-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 16px;
    }
    .metrics-table th {
      color: #5C6478;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 6px 0;
      border-bottom: 1px solid #262B38;
      text-align: left;
      font-weight: 500;
    }
    .metrics-table td {
      padding: 10px 0;
      font-size: 13px;
      color: #9AA3B5;
      border-bottom: 1px solid #1C212E;
    }
    .metrics-table tr:last-child td {
      border-bottom: none;
    }
    .metrics-table td.metric-value {
      color: #F5F6FA;
      font-weight: 500;
      font-family: monospace;
    }
    
    /* Badges */
    .confidence-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 600;
      border: 1px solid transparent;
    }
    .high-conf {
      background-color: rgba(34, 197, 94, 0.08);
      color: #22C55E;
      border-color: rgba(34, 197, 94, 0.15);
    }
    .med-conf {
      background-color: rgba(245, 158, 11, 0.08);
      color: #F59E0B;
      border-color: rgba(245, 158, 11, 0.15);
    }
    .low-conf {
      background-color: rgba(239, 68, 68, 0.08);
      color: #EF4444;
      border-color: rgba(239, 68, 68, 0.15);
    }
    .conf-dot {
      width: 5px;
      height: 5px;
      border-radius: 50%;
      background-color: currentColor;
    }
    
    .diagnostic-tag {
      display: inline-block;
      background-color: rgba(99, 102, 241, 0.08);
      color: #6366F1;
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      margin-bottom: 16px;
      border: 1px solid rgba(99, 102, 241, 0.15);
    }
    
    /* Alerts styling */
    .custom-alert {
      border-radius: 8px;
      padding: 14px;
      margin: 16px 0;
      border: 1px solid;
      display: flex;
      gap: 12px;
      font-size: 13px;
    }
    .alert-warning {
      background-color: rgba(245, 158, 11, 0.04);
      color: #9AA3B5;
      border-color: rgba(245, 158, 11, 0.15);
    }
    .alert-danger {
      background-color: rgba(239, 68, 68, 0.04);
      color: #9AA3B5;
      border-color: rgba(239, 68, 68, 0.15);
    }
    .alert-title {
      font-weight: 600;
      color: #F5F6FA;
      margin-bottom: 4px;
    }
    
    /* Recommendations */
    .rec-card {
      background-color: #151923;
      border: 1px solid #262B38;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 12px;
    }
    .rec-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
    }
    .rec-priority {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 10px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .priority-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
    }
    .rec-pillar {
      font-size: 11px;
      color: #6366F1;
      font-weight: 500;
    }
    .rec-text {
      font-size: 13px;
      color: #F5F6FA;
      line-height: 1.5;
      margin-bottom: 12px;
    }
    
    details {
      border-top: 1px solid #262B38;
      padding-top: 8px;
    }
    details summary {
      cursor: pointer;
      font-size: 11px;
      color: #5C6478;
      font-weight: 500;
      display: flex;
      justify-content: space-between;
      align-items: center;
      user-select: none;
      list-style: none;
    }
    details summary::-webkit-details-marker {
      display: none;
    }
    details summary::after {
      content: '→';
      transition: transform 0.2s ease;
      font-family: monospace;
    }
    details[open] summary::after {
      transform: rotate(90deg);
    }
    .passage-box {
      background-color: #0B0E14;
      border-left: 2px solid #6366F1;
      padding: 8px 12px;
      margin-top: 8px;
      font-size: 12px;
      color: #9AA3B5;
      line-height: 1.5;
      font-style: italic;
    }
    
    /* Timeline styles */
    .timeline {
      position: relative;
      padding-left: 32px;
      margin: 24px 0;
    }
    .timeline::before {
      content: '';
      position: absolute;
      left: 11px;
      top: 6px;
      bottom: 6px;
      width: 2px;
      background-color: #262B38;
    }
    .timeline-item {
      position: relative;
      margin-bottom: 24px;
    }
    .timeline-item:last-child {
      margin-bottom: 0;
    }
    .timeline-marker {
      position: absolute;
      left: -32px;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background-color: #151923;
      border: 2px solid #6366F1;
      color: #F5F6FA;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 600;
      font-family: monospace;
      box-shadow: 0 0 0 4px #0B0E14;
    }
    .timeline-content {
      background-color: #151923;
      border: 1px solid #262B38;
      border-radius: 8px;
      padding: 16px;
    }
    .timeline-title {
      font-size: 15px;
      font-weight: 600;
      color: #F5F6FA;
      margin-bottom: 4px;
    }
    .timeline-desc {
      font-size: 13px;
      color: #9AA3B5;
      line-height: 1.4;
    }
    
    .formula-block {
      background-color: #151923;
      border: 1px solid #262B38;
      border-radius: 8px;
      padding: 16px;
      font-family: monospace;
      font-size: 12px;
      color: #9AA3B5;
      overflow-x: auto;
      margin: 16px 0;
      line-height: 1.4;
    }
    .formula-title {
      color: #F5F6FA;
      font-weight: 600;
      margin-bottom: 6px;
    }
    
    /* Loading States */
    .loading-card {
      background-color: #151923;
      border: 1px solid #262B38;
      border-radius: 12px;
      padding: 36px;
      max-width: 500px;
      margin: 40px auto;
      text-align: center;
      box-shadow: 0 4px 24px rgba(0,0,0,0.4);
    }
    .pulsing {
      animation: pulse 1.5s infinite ease-in-out;
    }
    @keyframes pulse {
      0% { opacity: 0.6; }
      50% { opacity: 1; }
      100% { opacity: 0.6; }
    }
    .loader-spinner {
      border: 3px solid #1C212E;
      border-top: 3px solid #6366F1;
      border-radius: 50%;
      width: 40px;
      height: 40px;
      animation: spin 0.8s linear infinite;
      margin: 0 auto 20px auto;
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    """
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    st.markdown('<div class="vantly-bg"></div>', unsafe_allow_html=True)

# ── Dynamic Active Nav Indicator ──────────────────────────────
def inject_active_nav_style() -> None:
    active_page = st.session_state.page
    if active_page in ["input", "results"]:
        active_key = "nav_btn_assess"
    elif active_page == "methodology":
        active_key = "nav_btn_meth"
    else:
        active_key = "nav_btn_home"

    st.markdown(f"""
    <style>
    .st-key-{active_key} button {{
      border-bottom: 2px solid #6366F1 !important;
      color: #F5F6FA !important;
      font-weight: 600 !important;
    }}
    </style>
    """, unsafe_allow_html=True)

# ── Header / Navigation ────────────────────────────────────────
def render_header() -> None:
    col_logo, col_nav = st.columns([1, 1])
    with col_logo:
        st.markdown("""
        <div class="logo-container">
          <div class="logo-text">Vantly<span class="logo-dot">.</span></div>
          <div class="logo-tagline">See your business clearly</div>
        </div>
        """, unsafe_allow_html=True)
    with col_nav:
        col_home, col_assess, col_meth = st.columns(3)
        with col_home:
            if st.button("Home", key="nav_btn_home", use_container_width=True):
                st.session_state.page = "landing"
                st.rerun()
        with col_assess:
            if st.button("Assessment", key="nav_btn_assess", use_container_width=True):
                if st.session_state.assessment_result:
                    st.session_state.page = "results"
                else:
                    st.session_state.page = "input"
                st.rerun()
        with col_meth:
            if st.button("Methodology", key="nav_btn_meth", use_container_width=True):
                st.session_state.page = "methodology"
                st.rerun()
    inject_active_nav_style()

# ── Screen Helpers ─────────────────────────────────────────────

def _render_confidence_badge(confidence: float) -> str:
    if confidence >= 80:
        return f'<div class="confidence-badge high-conf"><span class="conf-dot"></span> {confidence:.0f}% confidence</div>'
    elif confidence >= 50:
        return f'<div class="confidence-badge med-conf"><span class="conf-dot"></span> {confidence:.0f}% confidence</div>'
    else:
        return f'<div class="confidence-badge low-conf"><span class="conf-dot"></span> {confidence:.0f}% confidence</div>'

def _render_benchmark_slider(score: float, p25: float = 25, p50: float = 50, p75: float = 75) -> str:
    if score >= 67:
        color = "#22C55E"
    elif score >= 34:
        color = "#F59E0B"
    else:
        color = "#EF4444"
    return f"""
    <div class="benchmark-container">
      <div class="benchmark-ticks">
        <span style="left: 25%">p25 ({p25:.0f})</span>
        <span style="left: 50%">p50 ({p50:.0f})</span>
        <span style="left: 75%">p75 ({p75:.0f})</span>
      </div>
      <div class="benchmark-bar-bg">
        <div class="benchmark-bar-fill" style="width: {score}%; background-color: {color};"></div>
        <div class="benchmark-marker" style="left: {score}%;"></div>
      </div>
    </div>
    """

def _render_metrics_table(metrics_list: List[Dict[str, Any]]) -> str:
    import textwrap
    rows = []
    pretty_names = {
        "revenue_per_employee": "Revenue per Employee",
        "output_per_payroll": "Output per Payroll",
        "headcount_efficiency_ratio": "Headcount Efficiency Ratio",
        "gross_margin": "Gross Margin",
        "operating_margin": "Operating Margin",
        "current_ratio": "Current Ratio",
        "quick_ratio": "Quick Ratio"
    }
    
    for m in metrics_list:
        name = pretty_names.get(m.get("metric_name"), m.get("metric_name"))
        
        if m.get("excluded", False):
            val_str = '<span style="color:#5C6478;">Excluded</span>'
            p50_str = "-"
            score_str = '<span style="color:#5C6478;">-</span>'
        else:
            raw_val = m.get("raw_value")
            if "margin" in m.get("metric_name", "").lower():
                val_str = f"{raw_val:.1f}%" if raw_val is not None else "-"
            elif "ratio" in m.get("metric_name", "").lower():
                val_str = f"{raw_val:.2f}" if raw_val is not None else "-"
            else:
                val_str = f"£{raw_val:,.0f}" if raw_val is not None else "-"
                
            p50 = m.get("p50", 50.0)
            if "margin" in m.get("metric_name", "").lower():
                p50_str = f"{p50:.1f}%"
            elif "ratio" in m.get("metric_name", "").lower():
                p50_str = f"{p50:.2f}"
            else:
                p50_str = f"£{p50:,.0f}"
                
            norm = m.get("normalised_score", 0.0)
            score_str = f"{norm:.1f}"
            
        rows.append(textwrap.dedent(f"""\
        <tr>
          <td>{name}</td>
          <td class="metric-value" style="text-align: right;">{val_str}</td>
          <td style="text-align: right; color: #5C6478;">{p50_str}</td>
          <td style="text-align: right; font-weight: 600; color: #F5F6FA;">{score_str}</td>
        </tr>"""))
        
    return textwrap.dedent(f"""\
    <table class="metrics-table">
      <thead>
        <tr>
          <th>Metric</th>
          <th style="text-align: right;">Value</th>
          <th style="text-align: right;">p50 Benchmark</th>
          <th style="text-align: right;">Score</th>
        </tr>
      </thead>
      <tbody>
        {"".join(rows)}
      </tbody>
    </table>""")

def _render_pillar_dashboard(pillar: Dict[str, Any], title: str, icon_svg: str) -> None:
    score = pillar.get("score", 0.0)
    confidence = pillar.get("confidence", 0.0)
    excluded = pillar.get("excluded_metrics", [])
    exclusion_reasons = pillar.get("exclusion_reasons", {})
    metrics = pillar.get("metrics", [])
    
    st.markdown(f"""
    <div class="card-header">
      <div class="card-title-container">
        {icon_svg}
        <span class="card-title">{title}</span>
      </div>
      {_render_confidence_badge(confidence)}
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f'<div class="card-score">{score:.1f} <span style="font-size:14px; color:#5C6478; font-weight:normal;">/ 100</span></div>', unsafe_allow_html=True)
    
    # Custom interactive benchmark bar
    st.markdown(_render_benchmark_slider(score), unsafe_allow_html=True)
    
    # Detailed metric breakdown list/table
    if metrics:
        st.markdown(_render_metrics_table(metrics), unsafe_allow_html=True)
        
    # Show exclusions inline inside card
    if excluded:
        exclusions_list = "".join(f"<li><strong>{m}</strong>: {exclusion_reasons.get(m, 'No context provided')}</li>" for m in excluded)
        st.markdown(f"""
        <div style="background-color: rgba(245, 158, 11, 0.03); border: 1px solid rgba(245, 158, 11, 0.15); border-radius: 8px; padding: 12px; margin-top: 16px; font-size: 12px; color: #9AA3B5;">
          <strong style="color: #F59E0B;">Excluded Metrics (Missing Input):</strong>
          <ul style="margin: 6px 0 0 16px; padding: 0;">
            {exclusions_list}
          </ul>
        </div>
        """, unsafe_allow_html=True)

# ── SCREEN 1: Landing/Marketing Page ───────────────────────────
def render_landing_page() -> None:
    st.markdown("""
    <div class="landing-hero">
      <div class="hero-tag">SME Productivity Engine</div>
      <h1 class="hero-title">See your business clearly.</h1>
      <p class="hero-subtitle">
        AI-powered productivity assessment for small-to-medium enterprises.
        Upload your financials and get a benchmarked score in under 60 seconds.
      </p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1.5, 1, 1.5])
    with col2:
        if st.button("Start free assessment", key="start_assessment_cta", use_container_width=True, type="primary"):
            st.session_state.page = "input"
            st.rerun()
            
    st.markdown("""
    <div class="social-proof">
      <p class="social-proof-title">Trusted by finance teams at growing SMEs</p>
      <div class="logo-grid">
        <div class="mock-logo">ACME CORP</div>
        <div class="mock-logo">LINEAR B</div>
        <div class="mock-logo">STRIPE ANALYTICS</div>
        <div class="mock-logo">VERCEL PARTNERS</div>
      </div>
    </div>
    
    <div class="feature-grid">
      <div class="feature-card">
        <div class="feature-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>
        </div>
        <div class="feature-title">Precise Benchmarking</div>
        <div class="feature-desc">Compare your revenue per employee and gross margins against validated ONS and OECD sector percentiles.</div>
      </div>
      <div class="feature-card">
        <div class="feature-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="M12 6v6l4 2"/></svg>
        </div>
        <div class="feature-title">AI-Powered Extraction</div>
        <div class="feature-desc">Automatically extract financial metrics from PDF statements and raw CSVs using verified RAG logic.</div>
      </div>
      <div class="feature-card">
        <div class="feature-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.886H3.894l4.948 3.596L6.93 18.368 12 14.772l5.07 3.596-1.912-5.886 4.948-3.596h-6.194L12 3z"/></svg>
        </div>
        <div class="feature-title">Actionable Insights</div>
        <div class="feature-desc">Receive ranked optimization recommendations based on your performance anomalies with direct audit lines.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── SCREEN 2: Assessment Input Form ───────────────────────────
def render_input_page() -> None:
    with st.container(border=True):
        st.markdown('<div class="form-card"></div>', unsafe_allow_html=True)
        st.markdown('<div class="step-indicator">Step 1 of 2</div>', unsafe_allow_html=True)
        st.markdown('<h2 style="margin: 0 0 20px 0; font-size:22px;">New Productivity Assessment</h2>', unsafe_allow_html=True)
        
        # Sector setup
        sector = st.selectbox(
            "Business Sector (required)",
            options=["", "Retail", "Services", "Manufacturing"],
            index=0,
            help="Benchmarked targets will adjust to ONS percentiles of your selected sector.",
        )
        
        company_name = st.text_input(
            "Company Name (optional)",
            value="",
            placeholder="e.g. Acme Ltd",
        )
        
        uploaded_files = st.file_uploader(
            "Financial Documents (PDF or CSV)",
            type=["pdf", "csv"],
            accept_multiple_files=True,
            help="Upload annual accounts or raw financial data logs.",
        )
        
        sector_selected = bool(sector)
        files_present = bool(uploaded_files)
        button_disabled = not (sector_selected and files_present)
        
        st.markdown('<div style="height: 12px;"></div>', unsafe_allow_html=True)
        
        # Validation alerts
        if not sector_selected:
            st.markdown('<div class="custom-alert alert-warning" style="margin:0 0 16px 0;">Select a business sector to activate the assessment.</div>', unsafe_allow_html=True)
        elif not files_present:
            st.markdown('<div class="custom-alert alert-warning" style="margin:0 0 16px 0;">Upload at least one PDF or CSV document to start extraction.</div>', unsafe_allow_html=True)
            
        if st.button(
            "Run Assessment",
            disabled=button_disabled,
            type="primary",
            use_container_width=True,
        ):
            _run_assessment(uploaded_files, company_name, sector)

def _run_assessment(
    uploaded_files: List[Any],
    company_name: str,
    sector: str,
) -> None:
    stages = [
        ("parsing",    "📄 Parsing uploaded documents…"),
        ("embedding",  "🔢 Creating vector embeddings…"),
        ("retrieving", "🔍 Executing similarity searches…"),
        ("extracting", "🤖 Running metric extraction models…"),
        ("scoring",    "📊 Evaluating peer benchmarks…"),
    ]

    status_placeholder = st.empty()

    for i, (stage_key, stage_label) in enumerate(stages):
        with status_placeholder.container():
            st.markdown(f"""
            <div class="loading-card">
              <div class="loader-spinner"></div>
              <div class="step-indicator" style="margin-bottom: 12px;">Pipeline Stage {i+1} of {len(stages)}</div>
              <h3 style="margin: 0 0 8px 0; color: #F5F6FA; font-size: 18px;">{stage_label}</h3>
              <p style="color: #9AA3B5; font-size: 13px; margin: 0;" class="pulsing">Processing secure data pipeline...</p>
            </div>
            """, unsafe_allow_html=True)

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
                
                response = requests.post(
                    f"{API_BASE_URL}/assess",
                    files=file_tuples,
                    data=data,
                    timeout=240,
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
                st.error("Connection failed. Ensure the FastAPI backend is running locally on http://localhost:8000")
            except Exception as exc:
                status_placeholder.empty()
                st.error(f"Error during analysis: {exc}")
        else:
            time.sleep(0.3)

# ── SCREEN 3: Results Dashboard ───────────────────────────────
def render_results_page() -> None:
    res = st.session_state.assessment_result

    if not res:
        st.warning("No assessment data available. Run an assessment first.")
        if st.button("Back to Setup"):
            st.session_state.page = "input"
            st.rerun()
        return

    # Warning / Info Disclaimer Card (always visible, top)
    st.markdown("""
    <div class="custom-alert alert-warning" style="margin-top: 0;">
      <div>
        <div class="alert-title">⚠️ Disclaimer Note</div>
        Firm-level productivity scores measure aggregate operational benchmarks and are <strong>not</strong> indicative of individual employee performance or value.
      </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Top info and confidence overview
    col_info, col_badge = st.columns([2, 1])
    with col_info:
        st.markdown(f'<h1 style="margin: 0; font-size:32px;">{res.get("company_name", "Company")} Assessment</h1>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: #9AA3B5; font-size:13px; margin: 4px 0 0 0;">Sector: <strong>{res.get("sector", "N/A")}</strong> &nbsp;|&nbsp; Run ID: <code>{res.get("run_id", "N/A")}</code></p>', unsafe_allow_html=True)
    
    with col_badge:
        composite = res.get("productivity_index", 0.0)
        # Determine average confidence across both pillars
        labour_conf = res.get("labour_efficiency", {}).get("confidence", 0.0)
        fin_conf = res.get("financial_health", {}).get("confidence", 0.0)
        avg_conf = (labour_conf + fin_conf) / 2.0
        
        st.markdown(f'<div style="text-align: right; margin-top: 8px;">{_render_confidence_badge(avg_conf)}</div>', unsafe_allow_html=True)
        
    st.divider()
    
    # Large Circular Progress Hero
    composite_score = res.get("productivity_index", 0.0)
    # Color calculations
    if composite_score >= 67:
        accent_color = "#22C55E"
    elif composite_score >= 34:
        accent_color = "#F59E0B"
    else:
        accent_color = "#EF4444"
        
    # Circumference calculations (2 * pi * r => 2 * 3.14159 * 80 = 502.65)
    offset = 502.65 - (composite_score / 100.0) * 502.65
    
    st.markdown(f"""
    <div class="progress-ring-container">
      <svg class="progress-ring" width="200" height="200">
        <circle class="progress-ring__circle-bg" stroke="#262B38" stroke-width="12" fill="transparent" r="80" cx="100" cy="100"/>
        <circle class="progress-ring__circle" stroke="{accent_color}" stroke-dasharray="502.65" stroke-dashoffset="{offset}" stroke-width="12" stroke-linecap="round" fill="transparent" r="80" cx="100" cy="100" style="--target-offset: {offset}; filter: drop-shadow(0 0 6px {accent_color});"/>
      </svg>
      <div class="progress-ring-text">
        <span class="score-number">{composite_score:.1f}</span>
        <span class="score-label">Productivity Index</span>
      </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Navigation tabs (underline style via CSS)
    tab_pillars, tab_dm, tab_warnings, tab_recs = st.tabs([
        "Pillar Benchmarks", 
        "Digital Maturity Diagnostic", 
        "Anomalies & Warnings", 
        "Recommendations & Citations"
    ])
    
    # ── TAB 1: Pillars Side-by-side
    with tab_pillars:
        labour = res.get("labour_efficiency", {})
        financial = res.get("financial_health", {})
        
        col_lab, col_fin = st.columns(2)
        with col_lab:
            with st.container(border=True):
                st.markdown('<div class="pillar-card"></div>', unsafe_allow_html=True)
                labour_icon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #6366F1;"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>'
                _render_pillar_dashboard(labour, "Labour Efficiency", labour_icon)
                
        with col_fin:
            with st.container(border=True):
                st.markdown('<div class="pillar-card"></div>', unsafe_allow_html=True)
                financial_icon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #6366F1;"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>'
                _render_pillar_dashboard(financial, "Financial Health", financial_icon)
                
    # ── TAB 2: Digital Maturity
    with tab_dm:
        digital = res.get("digital_maturity", {})
        dig_score = digital.get("score", 0.0)
        dig_level = digital.get("level", "N/A")
        dig_tools = digital.get("tools_identified", [])
        dig_auto   = digital.get("automation_detected", False)
        dig_procs  = digital.get("process_indicators", [])
        
        with st.container(border=True):
            st.markdown('<div class="digital-card"></div>', unsafe_allow_html=True)
            st.markdown('<div class="diagnostic-tag">Diagnostic Only</div>', unsafe_allow_html=True)
            st.markdown('<h3 style="margin-top: 0; font-size:18px;">Digital Maturity Score</h3>', unsafe_allow_html=True)
            
            col_d_val, col_d_desc = st.columns([1, 2])
            with col_d_val:
                st.markdown(f'<div class="card-score">{dig_score:.0f} <span style="font-size:14px; color:#5C6478; font-weight:normal;">/ 100</span></div>', unsafe_allow_html=True)
                st.markdown(f'<p style="color: #9AA3B5; font-size:13px; margin: 4px 0 0 0;">Evaluation Level: <strong>{dig_level}</strong></p>', unsafe_allow_html=True)
                st.markdown(_render_benchmark_slider(dig_score), unsafe_allow_html=True)
                
            with col_d_desc:
                if dig_tools:
                    st.markdown("**Core business tools detected:**")
                    st.markdown(", ".join(f"`{t}`" for t in dig_tools))
                else:
                    st.markdown("*No specific software applications detected.*")
                    
                st.markdown(f"**Automation capability language detected:** {'Yes ✓' if dig_auto else 'No'}")
                
                if dig_procs:
                    st.markdown("**Identified digital processes:**")
                    for ind in dig_procs:
                        st.markdown(f"• {ind}")
                        
    # ── TAB 3: Warnings and Errors
    with tab_warnings:
        conflicts = res.get("conflict_warnings", [])
        errors = res.get("extraction_errors", [])
        
        if not conflicts and not errors:
            st.markdown('<p style="color:#9AA3B5; font-size:14px;">No anomalies or conflicting figures detected during verification.</p>', unsafe_allow_html=True)
            
        if conflicts:
            for cw in conflicts:
                st.markdown(f"""
                <div class="custom-alert alert-warning">
                  <div>
                    <div class="alert-title">⚡ Conflicting Data Point: {cw['metric_name']}</div>
                    Values differ by {cw['discrepancy_pct']:.1f}% across document chunks:<br/>
                    • Value A: <code>{cw['value_a']}</code> &mdash; <em>"{cw['passage_a'][:120]}..."</em><br/>
                    • Value B: <code>{cw['value_b']}</code> &mdash; <em>"{cw['passage_b'][:120]}..."</em><br/>
                    The system retained the initial value. Please review manually.
                  </div>
                </div>
                """, unsafe_allow_html=True)
                
        if errors:
            for err in errors:
                st.markdown(f"""
                <div class="custom-alert alert-danger">
                  <div>
                    <div class="alert-title">⚠️ Model Validation Error: {err['metric_name']}</div>
                    {err['error_detail']}<br/>
                    Raw payload response: <code>{err['raw_response'][:180]}</code>
                  </div>
                </div>
                """, unsafe_allow_html=True)
                
    # ── TAB 4: Recommendations
    with tab_recs:
        recommendations = res.get("recommendations", [])
        if not recommendations:
            st.markdown('<div class="custom-alert alert-warning">No recommendations calculated.</div>', unsafe_allow_html=True)
        else:
            for rec in sorted(recommendations, key=lambda r: r.get("rank", 999)):
                priority = rec.get("priority", "Medium")
                pillar   = rec.get("pillar", "")
                text     = rec.get("text", "")
                passages = rec.get("source_passages", [])
                
                # Priority Styling
                dot_color = {"High": "#EF4444", "Medium": "#F59E0B", "Low": "#22C55E"}.get(priority, "#9AA3B5")
                
                passages_html = ""
                if passages:
                    p_boxes = []
                    for i, p in enumerate(passages, 1):
                        if p:
                            p_esc = p.replace('"', '&quot;')
                            p_boxes.append(f'<div class="passage-box">Citation {i}: &ldquo;{p_esc}&rdquo;</div>')
                    passages_html = f"""
                    <details>
                      <summary>View audit trails / cited source passages</summary>
                      {"".join(p_boxes)}
                    </details>
                    """
                    
                st.markdown(f"""
                <div class="rec-card">
                  <div class="rec-header">
                    <span class="rec-pillar">{pillar}</span>
                    <span class="rec-priority" style="color: {dot_color};">
                      <span class="priority-dot" style="background-color: {dot_color};"></span>
                      {priority} Priority
                    </span>
                  </div>
                  <div class="rec-text">{text}</div>
                  {passages_html}
                </div>
                """, unsafe_allow_html=True)

    # ── Sticky Bottom Action Bar ───────────────────────────────
    # Generates a spacer to keep content from getting cut off
    st.markdown('<div class="sticky-spacer"></div>', unsafe_allow_html=True)
    
    col_spacer, col_pdf, col_new = st.columns([3, 1, 1])
    
    with col_pdf:
        # Request report pdf content in-memory
        run_id = res.get("run_id", "N/A")
        try:
            pdf_resp = requests.get(f"{API_BASE_URL}/reports/{run_id}/pdf")
            if pdf_resp.status_code == 200:
                st.download_button(
                    label="Export PDF Report",
                    data=pdf_resp.content,
                    file_name=f"Assessment_Report_{run_id}.pdf",
                    mime="application/pdf",
                    key="export_pdf_btn",
                )
            else:
                st.button("Export PDF (Error)", key="export_pdf_btn", disabled=True)
        except Exception:
            st.button("Export PDF (Offline)", key="export_pdf_btn", disabled=True)
            
    with col_new:
        if st.button("New Assessment", key="new_assessment_btn", type="primary", use_container_width=True):
            st.session_state.page = "input"
            st.session_state.assessment_result = None
            st.rerun()

# ── SCREEN 4: Methodology ─────────────────────────────────────
def render_methodology_page() -> None:
    st.markdown("""
    <h2 style="text-align: center; margin-bottom: 8px; font-size: 26px;">Methodology & Tech Stack</h2>
    <p style="text-align: center; color: #9AA3B5; max-width: 600px; margin: 0 auto 36px auto; font-size:14px;">
      Vantly runs a secure Retrieval-Augmented Generation (RAG) pipeline to analyze documents and evaluate business metrics.
    </p>
    """, unsafe_allow_html=True)
    
    col_timeline, col_formulas = st.columns([1, 1])
    
    with col_timeline:
        st.markdown('<h3 style="font-size:18px; margin-bottom:16px;">Assessment Workflow</h3>', unsafe_allow_html=True)
        st.markdown("""
        <div class="timeline">
          <div class="timeline-item">
            <span class="timeline-marker">1</span>
            <div class="timeline-content">
              <div class="timeline-title">Secure Extraction</div>
              <div class="timeline-desc">Documents (PDF/CSV) are parsed locally. Plain texts are split into overlapping blocks.</div>
            </div>
          </div>
          <div class="timeline-item">
            <span class="timeline-marker">2</span>
            <div class="timeline-content">
              <div class="timeline-title">Dense Embeddings</div>
              <div class="timeline-desc">BGE-small-en-v1.5 converts chunks to dense vector structures inside the FastEmbed local runtime.</div>
            </div>
          </div>
          <div class="timeline-item">
            <span class="timeline-marker">3</span>
            <div class="timeline-content">
              <div class="timeline-title">Vector Search</div>
              <div class="timeline-desc">The pipeline runs queries on Supabase pgvector, retrieving top-relevant sections.</div>
            </div>
          </div>
          <div class="timeline-item">
            <span class="timeline-marker">4</span>
            <div class="timeline-content">
              <div class="timeline-title">AI Processing & Validation</div>
              <div class="timeline-desc">Llama 3.3 70B extracts target numbers and verbatim evidence schemas under strict Pydantic structures.</div>
            </div>
          </div>
          <div class="timeline-item">
            <span class="timeline-marker">5</span>
            <div class="timeline-content">
              <div class="timeline-title">Benchmark Scoring</div>
              <div class="timeline-desc">Scores are normalise-mapped to 25th/75th percentiles of ONS peer industry surveys.</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_formulas:
        st.markdown('<h3 style="font-size:18px; margin-bottom:16px;">Core Formulas</h3>', unsafe_allow_html=True)
        st.markdown("""
        <div class="formula-block">
          <div class="formula-title">Composite Productivity Index (CPI)</div>
          CPI = (Labour Efficiency Score + Financial Health Score) / 2
        </div>
        
        <div class="formula-block">
          <div class="formula-title">Min-Max Industry Normalisation</div>
          Score = ((value - p25) / (p75 - p25)) * 100
          <div style="font-size: 11px; margin-top:4px; color: #5C6478;">* Result is strictly clamped between [0.0, 100.0]</div>
        </div>
        
        <div class="formula-block">
          <div class="formula-title">Labour Pillars</div>
          • Revenue per Employee = Revenue / Headcount<br/>
          • Output per Payroll = Revenue / Payroll<br/>
          • Headcount Efficiency Ratio = Payroll / Headcount
        </div>
        
        <div class="formula-block">
          <div class="formula-title">Financial Health Pillars</div>
          • Gross Margin & Operating Margin (%)<br/>
          • Current Ratio = Current Assets / Current Liabilities<br/>
          • Quick Ratio = (Current Assets - Inventory) / Current Liabilities
        </div>
        """, unsafe_allow_html=True)
        
    st.divider()
    
    st.markdown('<h3 style="font-size:18px; margin-bottom:16px;">FAQ</h3>', unsafe_allow_html=True)
    
    faqs = [
        ("How does industry classification normalise my scores?", 
         "Each sector carries specific percentile benchmarks derived from business activity datasets. Normalisation reflects how your metrics perform compared to actual top-quartile (p75) and bottom-quartile (p25) peer data."),
        ("What happens if some values are missing in my accounts?", 
         "Vantly uses strict exclusion logic. Missing numbers do not get assumed or filled with zero. Instead, they are left out of scoring entirely, which lowers the relative confidence score of the assessment."),
        ("What does the Digital Maturity Score calculate?", 
         "It counts specific tool mentions (+5 each), script/automation indicators (+20), and structural process keywords. This is kept as a separate diagnostic category and does not inflate your CPI score.")
    ]
    
    for q, a in faqs:
        st.markdown(f"""
        <div style="background-color:#151923; border:1px solid #262B38; border-radius:8px; padding:14px; margin-bottom:12px;">
          <details>
            <summary style="font-size:14px; font-weight:600; color:#F5F6FA; outline:none;">{q}</summary>
            <div style="color:#9AA3B5; font-size:13px; margin-top:8px; line-height:1.4;">{a}</div>
          </details>
        </div>
        """, unsafe_allow_html=True)

# ── Main Application Router ────────────────────────────────────
def main() -> None:
    start_backend_if_needed()
    inject_custom_css()
    render_header()
    
    if st.session_state.page == "landing":
        render_landing_page()
    elif st.session_state.page == "input":
        render_input_page()
    elif st.session_state.page == "results":
        render_results_page()
    elif st.session_state.page == "methodology":
        render_methodology_page()
    else:
        st.session_state.page = "landing"
        st.rerun()

if __name__ == "__main__":
    main()
