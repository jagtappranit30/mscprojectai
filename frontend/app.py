import streamlit as st
from pathlib import Path
import sys
import requests

# Add backend to path in case of direct local import or testing
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# Page config
st.set_page_config(
    page_title="SME Productivity Assessment Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Design System using CSS inject
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Main container styling */
    .main {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        color: #f8fafc;
    }
    
    /* Custom button styling */
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #6366f1 0%, #4f46e5 100%);
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.6rem 1.8rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
    }
    
    div.stButton > button:first-child:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6);
        background: linear-gradient(90deg, #4f46e5 0%, #4338ca 100%);
    }
    
    /* Input element headers styling */
    h1, h2, h3 {
        color: #f1f5f9 !important;
        font-weight: 700 !important;
    }
    
    /* Accent Cards */
    .accent-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("📊 SME Productivity Assessment Platform")
st.markdown("""
Analyze your SME's productivity using AI-powered financial document analysis. 
Upload accounting statements to receive instant diagnostic benchmarks and actionable recommendations.
""")

# Navigation
page = st.sidebar.radio(
    "Navigation",
    ["📝 Input Assessment", "📊 View Results", "ℹ️ About"]
)

if page == "📝 Input Assessment":
    st.markdown("### Step 1: Company Profile & Document Upload")
    
    # Grid columns
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="accent-card">', unsafe_allow_html=True)
        st.subheader("Company Information")
        company_name = st.text_input("Company Name", placeholder="e.g. Acme Manufacturing Ltd")
        sector = st.selectbox(
            "Business Sector",
            ["Manufacturing", "Services", "Retail", "Other"]
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col2:
        st.markdown('<div class="accent-card">', unsafe_allow_html=True)
        st.subheader("Document Upload")
        doc_type = st.radio("Document Type", ["PDF", "CSV"], horizontal=True)
        
        uploaded_file = st.file_uploader(
            f"Upload {doc_type} Statement",
            type=["pdf"] if doc_type == "PDF" else ["csv"],
            help=f"Max 10MB file limit."
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
    # Trigger assessment
    if st.button("🚀 Analyze Document & Assess Productivity", use_container_width=True):
        if not uploaded_file:
            st.error("❌ Please upload a statement file to analyze.")
            st.stop()
            
        with st.spinner("Analyzing document metrics using AI models..."):
            # Prepare multipart request
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            data = {
                "company_name": company_name or "Acme Corp",
                "sector": sector,
                "document_type": doc_type
            }
            
            # API address
            api_url = "http://localhost:8000/assess"
            
            try:
                response = requests.post(api_url, files=files, data=data, timeout=45)
                if response.status_code == 200:
                    payload = response.json()
                    st.session_state.last_result = payload.get("result")
                    st.success("✅ Assessment completed successfully!")
                    
                    # Direct streamlit redirect to pages/results.py
                    st.switch_page("pages/results.py")
                else:
                    st.error(f"❌ API Assessment failure: {response.text}")
            except Exception as e:
                st.error(f"❌ Could not connect to API server: {str(e)}")

elif page == "📊 View Results":
    if "last_result" in st.session_state:
        st.switch_page("pages/results.py")
    else:
        st.warning("⚠️ No active assessment results. Please complete Step 1 to generate results.")

elif page == "ℹ️ About":
    st.markdown("""
    <div class="accent-card">
        <h3>About the Platform</h3>
        <p>This platform serves as a modern tool for Small and Medium Enterprises (SMEs) to assess operations and productivity.</p>
        
        <h4>Core Pillars:</h4>
        <ul>
            <li><strong>Labour Efficiency:</strong> Evaluates revenue generation efficiency relative to human resources.</li>
            <li><strong>Financial Health:</strong> Measures profitability and short-term liquidity stability.</li>
            <li><strong>Digital Maturity:</strong> Diagnostics of software tools, workflows, and automated pipeline integration.</li>
        </ul>
        
        <h4>Tech Architecture:</h4>
        <ul>
            <li>Front-end: Streamlit Dashboard</li>
            <li>API Backend: FastAPI Asynchronous Server</li>
            <li>Database: Supabase (PostgreSQL with pgvector)</li>
            <li>LLM Orchestrator: Groq Llama 3.3</li>
            <li>Semantic Search: FastEmbed</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
