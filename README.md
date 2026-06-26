# SME Productivity Assessment Platform

An AI-powered productivity assessment platform for Small-to-Medium Enterprises (SMEs) with FastAPI backend, Streamlit frontend, and Supabase data storage.

## Architecture

- **Frontend:** Streamlit 1.28+ dashboard for interactive reports.
- **Backend:** FastAPI for asynchronous metrics extraction and scoring.
- **Document Processing:** PyMuPDF (PDF) and Python standard csv (CSV).
- **RAG Engine:** FastEmbed with ONNX embedding format and Supabase `pgvector` indexing.
- **Extraction Model:** Groq Llama 3.3.

## Local Development Setup

1. **Clone & Setup Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. **Configuration:**
   Copy `.env.example` to `.env` and fill in API keys:
   ```bash
   cp .env.example .env
   ```

3. **Database Migration:**
   Paste the database schema from `implementation_plan.md` into your Supabase SQL editor.

4. **Run Services:**
   - **Backend API:**
     ```bash
     uvicorn backend.main:app --reload --port 8000
     ```
   - **Frontend Streamlit:**
     ```bash
     streamlit run frontend/app.py --server.port 8501
     ```

5. **Access:**
   - Backend API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
   - Frontend Dashboard: [http://localhost:8501](http://localhost:8501)

## Running Tests
```bash
pytest tests/ -v
```

## Docker Container Running
```bash
docker build -t sme-platform -f docker/Dockerfile .
docker run -p 8000:8000 -p 8501:8501 sme-platform
```
