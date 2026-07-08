# SME Productivity Assessment Platform

An MSc research prototype that assesses small-to-medium enterprise (SME) productivity from uploaded business documents using a RAG (retrieval-augmented generation) pipeline.

**Research prototype — prioritises correctness, transparency, and reproducibility.**

---

## Architecture

```
Upload (PDF/CSV)
      │
      ▼
┌─────────────────────────────────────────┐
│  FastAPI  POST /assess                  │
│  1. Parse (PyMuPDF / csv module)        │
│  2. Chunk (500 words, 50 overlap)       │
│  3. Embed (FastEmbed bge-small-en-v1.5) │──► Supabase pgvector
│  4. Retrieve (per-metric RAG, top-5)   │◄── Supabase pgvector
│  5. Extract (Groq Llama 3.3 70B)       │
│  6. Score  (NumPy min-max, no LLM)     │
└─────────────────────────────────────────┘
      │
      ▼
Streamlit UI (port 8501)
```

| Layer | Technology |
|---|---|
| Container | Docker, multi-stage, Python 3.12, non-root user |
| Backend | FastAPI, single `POST /assess` endpoint |
| Frontend | Streamlit (default widgets only — no custom HTML/CSS) |
| Document parsing | PyMuPDF (PDF), `csv` module (CSV) |
| Embeddings | `bge-small-en-v1.5` via FastEmbed (ONNX), 384-dim |
| Vector store | Supabase pgvector (HNSW index) |
| LLM extraction | Groq API — Llama 3.3 70B, temperature=0 |
| Scoring | Pure Python + NumPy, min-max normalisation, no model inference |
| CI/CD | GitHub Actions (pytest on PR, deploy to Render on main) |

---

## Required Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description | Where to get it |
|---|---|---|
| `GROQ_API_KEY` | Groq API key for Llama 3.3 70B inference | [console.groq.com](https://console.groq.com) |
| `SUPABASE_URL` | Your Supabase project URL | Supabase Dashboard → Settings → API |
| `SUPABASE_KEY` | Supabase anon/service key | Supabase Dashboard → Settings → API |
| `SUPABASE_JWT_SECRET` | JWT secret (for auth endpoints, out of spec scope) | Supabase Dashboard → Settings → API |
| `RENDER_EXTERNAL_URL` | External URL of the Render service | Render dashboard (set after first deploy) |

---

## Database Setup (Supabase)

1. Open your Supabase project SQL Editor.
2. Paste the entire contents of `schema.sql` and run it.
3. This creates: `sectors`, `benchmark_metrics`, `ingestion_runs`, `document_chunks`,
   `extracted_metrics`, `assessment_results`, `users` tables, the `match_documents`
   pgvector RPC function, and seeds placeholder benchmark data.

> [!IMPORTANT]
> The benchmark values in `schema.sql` (and `data/benchmarks.json`) are **dummy placeholders**
> loosely derived from ONS Annual Business Survey guidance. Replace them with verified
> ONS/OECD percentile data before your MSc submission. Look for `-- TODO` comments in
> `schema.sql` to find every value that needs updating.

---

## Local Development

### Prerequisites
- Python 3.12
- A Supabase project (or run in mock mode without one)
- A Groq API key (or run without one — extraction returns null values, scoring still works)

### Setup

```bash
# 1. Clone and create virtual environment
python3.12 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install pinned dependencies
pip install -r requirements.lock

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 4. Set up Supabase schema
# Paste schema.sql into your Supabase SQL Editor and run
```

### Run Locally

```bash
# Terminal 1 — FastAPI backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — Streamlit frontend
streamlit run frontend/app.py --server.port 8501
```

- API docs: http://localhost:8000/docs
- Frontend: http://localhost:8501

### Mock mode (no API keys)

If `GROQ_API_KEY` or `SUPABASE_*` are missing/placeholder, both services degrade gracefully:
- Extraction returns `null` for all metrics (pillar confidence → 0%)
- Benchmarks use in-memory values from `database.py`
- Embeddings fall back to zero-vectors (retrieval still runs, similarity scores = 0)

---

## Running Tests

```bash
pytest tests/ -v --asyncio-mode=auto
```

Tests run entirely in mock mode — no live API keys required. Coverage:
- **Parsing**: valid CSV, malformed encoding, empty/binary PDF
- **Scoring**: normal case, missing-data exclusion with confidence check, conflict detection
- **Pydantic**: valid payload accepted, 4 malformed payload rejection cases
- **API**: health check

---

## Docker

```bash
# Build (from project root)
docker build -t sme-platform -f docker/Dockerfile .

# Run (supply env vars at runtime — never commit .env)
docker run \
  -e GROQ_API_KEY=your_key \
  -e SUPABASE_URL=your_url \
  -e SUPABASE_KEY=your_key \
  -p 8000:8000 \
  -p 8501:8501 \
  sme-platform
```

The container runs as non-root user `appuser` (UID 1001).

---

## Scoring Methodology

### Composite Productivity Index (0–100)

```
Composite = (Labour Efficiency Score + Financial Health Score) / 2
```

Equal-weighted average of two pillar scores. Both pillars normalised 0–100.

### Labour Efficiency Pillar

Metrics:
- `revenue_per_employee` = revenue / headcount
- `output_per_payroll` = revenue / payroll
- `headcount_efficiency_ratio` = payroll / headcount

### Financial Health Pillar

Metrics:
- `gross_margin` (%)
- `operating_margin` (%)
- `current_ratio` = current_assets / current_liabilities
- `quick_ratio` = (current_assets − inventory) / current_liabilities

### Normalisation

Each metric is min-max normalised against sector percentile benchmarks:

```
score = (value − p25) / (p75 − p25) × 100   [clamped to 0–100]
```

Pillar score = mean of included (non-excluded) metric scores.

### Missing Data Handling

**Exclusion, not imputation.** If a metric's inputs are `None`, the metric is excluded from
its pillar. Pillar confidence = `included_metrics / total_metrics × 100%`.

### Digital Maturity (Diagnostic Only)

Reported separately — **NOT included in the Composite Index**.  
Rubric: named software tools (+5 pts each, max 40), automation language (+20), digital process indicators (+5 each, max 40).

### Conflict Detection

If two retrieved passages produce values for the same metric differing by >10%, a
`ConflictWarning` is surfaced in the API response and shown in the UI. Neither value
is silently chosen — the user must verify manually.

---

## Project Structure

```
/
├── backend/
│   ├── main.py          # FastAPI app, POST /assess
│   ├── models.py        # Pydantic v2 schemas (strict)
│   ├── services/
│   │   ├── extraction.py  # Per-metric RAG + Groq extraction
│   │   ├── rag.py         # FastEmbed + pgvector RAG
│   │   ├── scoring.py     # Deterministic scoring engine
│   │   └── pdf_generator.py
│   └── utils/
│       ├── config.py
│       └── database.py
├── frontend/
│   └── app.py           # Streamlit UI (default widgets only)
├── tests/
│   └── test_backend.py
├── docker/
│   └── Dockerfile       # Python 3.12, multi-stage, non-root
├── .github/workflows/
│   ├── ci.yml           # pytest on every PR
│   └── deploy.yml       # pytest + Render deploy on main
├── schema.sql           # Full Supabase schema + seed data
├── data/benchmarks.json # Same benchmark data as JSON
├── requirements.txt     # Direct dependencies (pinned)
├── requirements.lock    # Full transitive dependency tree (pip freeze)
└── .env.example         # Required environment variables
```

---

## 🤖 Interchangeable LLM Providers (Groq & Ollama)

The platform supports interchangeable LLM backends. You can switch between Groq (production) and Ollama (local development/testing) by changing environment variables.

### How to use Ollama locally

1. **Install Ollama**:
   * macOS/Windows: Download from [ollama.com](https://ollama.com)
   * Linux: Run `curl -fsSL https://ollama.com/install.sh | sh`

2. **Pull the model**:
   * Open a terminal and run:
     ```bash
     ollama pull qwen2.5:7b
     ```

3. **Start Ollama server**:
   * Run:
     ```bash
     ollama serve
     ```

4. **Update `.env`**:
   * Set the provider and parameters:
     ```env
     LLM_PROVIDER=ollama
     OLLAMA_BASE_URL=http://localhost:11434/v1
     OLLAMA_MODEL=qwen2.5:7b
     ```

### Switching back to Groq
* Set in `.env`:
  ```env
  LLM_PROVIDER=groq
  GROQ_API_KEY=your_actual_groq_api_key
  ```

### Troubleshooting
* **Ollama server is not available**: Make sure you have started Ollama using `ollama serve`.
* **Requested Ollama model not found**: Run `ollama pull qwen2.5:7b` to download the required model weight first.

