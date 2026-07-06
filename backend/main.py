"""
FastAPI application — SME Productivity Assessment Platform.

POST /assess:
  Accepts multiple PDF/CSV file uploads + form fields (company_name, sector).
  Pipeline stages (reported in response):
    1. parsing   — extract text from each uploaded file
    2. chunking  — split into 500-word / 50-word overlap chunks
    3. embedding — FastEmbed bge-small-en-v1.5 ONNX embeddings → Supabase pgvector
    4. retrieving — per-metric RAG retrieval (top-5 chunks per metric query)
    5. extracting — Groq Llama 3.3 70B per-metric extraction + Pydantic validation
    6. scoring    — deterministic min-max scoring (NumPy, no model inference)

Hard constraints respected:
  - No LLM arithmetic. LLM extracts named values; scoring.py does all maths.
  - Strict Pydantic v2 validation; extraction errors returned as structured data.
  - Conflict warnings (>10% discrepancy) surfaced in response, never silently resolved.
  - Exclusion (not imputation) for missing metrics, with per-pillar confidence.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

load_dotenv()

# Auth dependencies (preserved from existing prototype — out of spec scope)
import jwt
from passlib.context import CryptContext

from .models import (
    AssessmentOutput,
    AssessmentResponse,
    UserLogin,
    UserSignup,
)
from .services.extraction import get_extraction_service
from .services.pdf_generator import generate_assessment_report
from .services.rag import rag_service
from .services.scoring import ScoringService
from .utils.database import db_service

# ── Auth configuration (out of spec scope — preserved) ────────
SECRET_KEY = os.getenv("SUPABASE_JWT_SECRET", "supersecretkey")
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── App ────────────────────────────────────────────────────────
app = FastAPI(
    title="SME Productivity Assessment API",
    description=(
        "AI-powered productivity assessment for SMEs. "
        "RAG pipeline: FastEmbed (ONNX) → Supabase pgvector → Groq Llama 3.3 70B → "
        "Deterministic NumPy scoring."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Document parsing helpers ───────────────────────────────────


async def _parse_pdf(file: UploadFile) -> str:
    """Extract plain text from a PDF using PyMuPDF."""
    import fitz  # PyMuPDF

    content = await file.read()
    doc = fitz.open(stream=content, filetype="pdf")
    text = "".join(page.get_text() for page in doc)
    await file.seek(0)
    return text


async def _parse_csv(file: UploadFile) -> str:
    """Convert CSV rows to plain text (one row per line, comma-joined)."""
    import csv
    import io

    content = await file.read()
    reader = csv.reader(io.StringIO(content.decode("utf-8", errors="ignore")))
    text = "\n".join(", ".join(row) for row in reader)
    await file.seek(0)
    return text


async def _extract_text(file: UploadFile) -> str:
    """Dispatch to the correct parser based on file extension."""
    name = (file.filename or "").lower()
    if name.endswith(".pdf"):
        return await _parse_pdf(file)
    if name.endswith(".csv"):
        return await _parse_csv(file)
    raise ValueError(f"Unsupported file type: {file.filename}")


# ── Main assessment endpoint ───────────────────────────────────


@app.post("/assess", response_model=AssessmentResponse)
async def assess_productivity(
    files: List[UploadFile] = File(...),
    company_name: str = Form(default="Unknown"),
    sector: str = Form(...),
) -> JSONResponse:
    """
    POST /assess — run the full productivity assessment pipeline.

    Form fields:
      - files:        one or more PDF/CSV uploads
      - company_name: optional company name string
      - sector:       required — "Retail" | "Services" | "Manufacturing"
    """
    run_id: Optional[str] = None
    pipeline_stages: dict = {}

    try:
        # ── Create ingestion run ───────────────────────────────
        run_id = await db_service.create_ingestion_run(
            sector=sector,
            company_name=company_name,
            document_type="MIXED"
            if len(files) > 1
            else ("PDF" if (files[0].filename or "").endswith(".pdf") else "CSV"),
        )

        # ── Stage 1: Parsing ───────────────────────────────────
        pipeline_stages["parsing"] = "running"
        all_text_parts: List[str] = []
        for f in files:
            try:
                text = await _extract_text(f)
                if text and len(text.strip()) >= 20:
                    all_text_parts.append(text)
            except ValueError as exc:
                await db_service.update_run_status(run_id, "failed", error_message=str(exc))
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": str(exc)},
                )

        if not all_text_parts:
            await db_service.update_run_status(
                run_id,
                "failed",
                error_message="All uploaded documents appear empty or unreadable",
            )
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Documents appear empty or unreadable"},
            )

        raw_text = "\n\n".join(all_text_parts)
        pipeline_stages["parsing"] = "complete"

        # ── Stage 2 + 3: Chunking & Embedding ─────────────────
        pipeline_stages["embedding"] = "running"
        chunks = await rag_service.chunk_text(raw_text)
        embeddings = await rag_service.embed_chunks(chunks)

        # Store with source filename (first file if multiple)
        source_filename = files[0].filename if files else ""
        await rag_service.store_embeddings(run_id, chunks, embeddings, source_filename)
        pipeline_stages["embedding"] = "complete"

        # ── Stage 4 + 5: Per-metric RAG retrieval + Extraction ─
        pipeline_stages["retrieving"] = "running"
        pipeline_stages["extracting"] = "running"
        extraction_service = get_extraction_service()
        (
            metrics,
            conflict_warnings,
            extraction_errors,
            source_passages,
        ) = await extraction_service.extract_all_metrics(run_id, rag_service)
        pipeline_stages["retrieving"] = "complete"
        pipeline_stages["extracting"] = "complete"

        # Store extracted metrics in DB
        metrics_dict = {
            name: {
                "value": getattr(metrics, name, None),
                "unit": "£",
                "confidence": metrics.confidence,
            }
            for name in [
                "revenue",
                "headcount",
                "payroll",
                "gross_margin",
                "operating_margin",
                "current_assets",
                "current_liabilities",
                "inventory",
            ]
            if getattr(metrics, name, None) is not None
        }
        await db_service.store_extracted_metrics(run_id, metrics_dict)

        # ── Stage 6: Scoring ───────────────────────────────────
        pipeline_stages["scoring"] = "running"
        (
            labour_pillar,
            financial_pillar,
            composite_index,
            digital_maturity,
        ) = await ScoringService.calculate_productivity_index(metrics, sector, source_passages)

        recommendations = ScoringService.generate_recommendations(
            labour_pillar, financial_pillar, composite_index, sector, source_passages
        )
        pipeline_stages["scoring"] = "complete"

        # ── Store result ───────────────────────────────────────
        result_id = str(uuid4())
        await db_service.store_assessment_result(
            {
                "result_id": result_id,
                "run_id": run_id,
                "labour_efficiency_score": labour_pillar.score,
                "financial_health_score": financial_pillar.score,
                "productivity_index": composite_index,
                "digital_maturity_score": digital_maturity.score,
                "confidence_overall": metrics.confidence * 100,
                "recommendations": "; ".join(r.text for r in recommendations),
            }
        )
        await db_service.update_run_status(run_id, "complete", metrics.confidence * 100)

        # ── Build response ─────────────────────────────────────
        output = AssessmentOutput(
            result_id=result_id,
            run_id=run_id,
            company_name=company_name,
            sector=sector,
            created_at=datetime.now(timezone.utc),
            productivity_index=composite_index,
            labour_efficiency=labour_pillar,
            financial_health=financial_pillar,
            digital_maturity=digital_maturity,
            conflict_warnings=conflict_warnings,
            extraction_errors=extraction_errors,
            recommendations=recommendations,
            pipeline_stages=pipeline_stages,
        )

        result = JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Assessment completed successfully",
                "result": output.model_dump(mode="json"),
            },
        )
        # Free FastEmbed model from RAM after each request (Render 512 MB limit)
        rag_service.unload_fastembed()
        return result

    except Exception as exc:
        import traceback

        traceback.print_exc()
        rag_service.unload_fastembed()   # free RAM even on failure
        if run_id:
            await db_service.update_run_status(run_id, "failed", error_message=str(exc))
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Assessment failed: {exc}"},
        )


# ── Health check ───────────────────────────────────────────────


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# ── Auth endpoints (out of spec scope — preserved) ────────────


@app.post("/signup")
async def signup(user: UserSignup):
    if user.password != user.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if len(user.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    hashed = pwd_context.hash(user.password)
    try:
        user_id = await db_service.create_user(user.email, hashed, user.company_name)
        return {"status": "success", "message": "User created", "user_id": user_id}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/login")
async def login(user: UserLogin):
    user_data = await db_service.get_user_by_email(user.email)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not pwd_context.verify(user.password, user_data["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    token = jwt.encode(
        {"sub": str(user_data["user_id"]), "email": user.email, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return {"status": "success", "token": token, "user_id": user_data["user_id"]}


@app.post("/assessments/{result_id}/save")
async def save_assessment(result_id: str, user_id: str = Form(...)):
    await db_service.save_assessment_to_user(result_id, user_id)
    return {"status": "success", "message": "Assessment saved"}


@app.get("/reports/{run_id}/pdf")
async def get_pdf_report(run_id: str):
    if db_service.enabled:
        res = (
            db_service.client.table("assessment_results").select("*").eq("run_id", run_id).execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Report not found")
        result_data = res.data[0]
        ing = db_service.client.table("ingestion_runs").select("*").eq("id", run_id).execute()
        if ing.data:
            result_data["company_name"] = ing.data[0].get("company_name")
            result_data["sector"] = ing.data[0].get("sector")
    else:
        result_data = next(
            (r for r in db_service.mock_results.values() if r.get("run_id") == run_id),
            None,
        )
        if not result_data:
            raise HTTPException(status_code=404, detail="Report not found")

    file_path = generate_assessment_report(result_data)
    return FileResponse(
        file_path, filename=f"Assessment_{run_id}.pdf", media_type="application/pdf"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
