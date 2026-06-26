import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import asyncio
from uuid import uuid4

# Load environment
load_dotenv()

from .models import AssessmentRequest, AssessmentResponse, AssessmentResult
from .services.extraction import get_extraction_service
from .services.scoring import ScoringService
from .services.rag import rag_service
from .utils.database import db_service

# Initialize FastAPI
app = FastAPI(
    title="SME Productivity Assessment API",
    description="AI-powered productivity assessment for SMEs",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for development and flexible container setup
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Document processing
async def extract_text_from_pdf(file: UploadFile) -> str:
    """Extract text from PDF using PyMuPDF (fitz)"""
    import fitz  # PyMuPDF
    
    content = await file.read()
    pdf_doc = fitz.open(stream=content, filetype="pdf")
    
    text = ""
    for page_num in range(len(pdf_doc)):
        page = pdf_doc[page_num]
        text += page.get_text()
        
    # Reset read pointer
    await file.seek(0)
    return text

async def extract_text_from_csv(file: UploadFile) -> str:
    """Extract text from CSV"""
    import csv
    import io
    
    content = await file.read()
    text_file = io.StringIO(content.decode("utf-8", errors="ignore"))
    reader = csv.reader(text_file)
    
    text = ""
    for row in reader:
        text += ", ".join(row) + "\n"
        
    # Reset read pointer
    await file.seek(0)
    return text

@app.post("/assess")
async def assess_productivity(
    file: UploadFile = File(...),
    company_name: str = Form("Unknown"),
    sector: str = Form(...),
    document_type: str = Form(...)
) -> JSONResponse:
    """
    Main assessment endpoint.
    
    1. Extract text from uploaded file
    2. Run RAG service chunking & embedding storage
    3. Use Groq LLM to extract structured metrics
    4. Calculate productivity scores
    5. Store results in database
    6. Return assessment results
    """
    
    run_id = None
    
    try:
        # Step 1: Create ingestion run
        run_id = await db_service.create_ingestion_run(
            sector=sector,
            company_name=company_name,
            document_type=document_type
        )
        
        # Step 2: Extract text from document
        if document_type.upper() == "PDF" or file.filename.endswith(".pdf"):
            raw_text = await extract_text_from_pdf(file)
        else:
            raw_text = await extract_text_from_csv(file)
        
        if not raw_text or len(raw_text.strip()) < 20:
            await db_service.update_run_status(run_id, "failed", error_message="Document appears empty or unreadable")
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "Document appears empty or unreadable"
                }
            )
        
        # Step 3: Run RAG indexing (Chunking and embedding storage)
        chunks = await rag_service.chunk_text(raw_text)
        embeddings = await rag_service.embed_chunks(chunks)
        await rag_service.store_embeddings(run_id, chunks, embeddings)
        
        # Step 4: Extract metrics using Groq LLM (or fallback parser)
        extraction_service = get_extraction_service()
        metrics = await extraction_service.extract_metrics_from_text(raw_text)
        
        # Step 5: Store extracted metrics
        metrics_dict = {
            "revenue": {"value": metrics.revenue, "unit": "£", "confidence": metrics.confidence},
            "headcount": {"value": metrics.headcount, "unit": "count", "confidence": metrics.confidence},
            "payroll": {"value": metrics.payroll, "unit": "£", "confidence": metrics.confidence},
            "gross_margin": {"value": metrics.gross_margin, "unit": "%", "confidence": metrics.confidence},
            "operating_margin": {"value": metrics.operating_margin, "unit": "%", "confidence": metrics.confidence},
        }
        await db_service.store_extracted_metrics(run_id, metrics_dict)
        
        # Step 6: Calculate productivity scores
        labour_score, financial_score, prod_index, digital_score = \
            await ScoringService.calculate_productivity_index(
                metrics.model_dump(),
                sector
            )
        
        # Step 7: Generate recommendations
        recommendations = ScoringService.generate_recommendations(
            labour_score, financial_score, prod_index, sector
        )
        
        # Look for sector benchmarks for the final response
        rev_emp_bench = await db_service.get_benchmark(sector, "revenue_per_employee")
        gross_marg_bench = await db_service.get_benchmark(sector, "gross_margin")
        op_marg_bench = await db_service.get_benchmark(sector, "operating_margin")
        payroll_bench = await db_service.get_benchmark(sector, "output_per_payroll")
        
        # Prepare digital tools diagnosis
        digital_tools = []
        lower_text = raw_text.lower()
        tools_list = ["xero", "quickbooks", "sage", "sap", "excel", "salesforce", "hubspot", "monday.com", "slack", "trello", "jira"]
        for tool in tools_list:
            if tool in lower_text:
                digital_tools.append(tool.capitalize())
        digital_tools_str = ", ".join(digital_tools) if digital_tools else "None specifically identified"
        
        # Step 8: Store assessment result
        result_id = str(uuid4())
        await db_service.store_assessment_result({
            "result_id": result_id,
            "run_id": str(run_id),
            "labour_efficiency_score": labour_score,
            "financial_health_score": financial_score,
            "productivity_index": prod_index,
            "digital_maturity_score": digital_score,
            "confidence_overall": metrics.confidence,
            "recommendations": "\n".join(recommendations)
        })
        
        # Step 9: Update run status
        await db_service.update_run_status(
            run_id, "complete", metrics.confidence
        )
        
        # Prepare response result payload
        result_payload = {
            "result_id": result_id,
            "run_id": str(run_id),
            "company_name": company_name,
            "sector": sector,
            "labour_efficiency_score": float(labour_score),
            "financial_health_score": float(financial_score),
            "productivity_index": float(prod_index),
            "digital_maturity_score": float(digital_score),
            "confidence_overall": float(metrics.confidence),
            "revenue_per_employee": float(metrics.revenue / metrics.headcount if metrics.headcount else 0.0),
            "output_per_payroll": float(metrics.revenue / metrics.payroll if metrics.payroll else 0.0),
            "gross_margin": float(metrics.gross_margin) if metrics.gross_margin is not None else 0.0,
            "operating_margin": float(metrics.operating_margin) if metrics.operating_margin is not None else 0.0,
            "current_ratio": float(metrics.current_assets / metrics.current_liabilities if metrics.current_liabilities else 1.5),
            "sector_benchmark_revenue_per_emp": float(rev_emp_bench.get("p50", 150000)),
            "sector_benchmark_output_per_payroll": float(payroll_bench.get("p50", 3.8)),
            "sector_benchmark_gross_margin": float(gross_marg_bench.get("p50", 35.0)),
            "sector_benchmark_operating_margin": float(op_marg_bench.get("p50", 12.0)),
            "recommendations": recommendations,
            "digital_maturity_level": "Medium" if len(digital_tools) >= 2 else "Low",
            "digital_tools_identified": digital_tools_str,
            "created_at": str(uuid4()) # Placeholder for timestamp mapping or datetime serialization
        }
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Assessment completed successfully",
                "result": result_payload
            }
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        if run_id:
            await db_service.update_run_status(run_id, "failed", error_message=str(e))
        
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Assessment failed: {str(e)}"
            }
        )

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
