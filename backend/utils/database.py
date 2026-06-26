import os
from supabase import create_client, Client
from typing import List, Dict, Any, Optional
from uuid import UUID
import json
from .config import settings

class DatabaseService:
    def __init__(self):
        self.url = settings.SUPABASE_URL
        self.key = settings.SUPABASE_KEY
        self.enabled = self.url != "https://placeholder.supabase.co" and self.key != "placeholder"
        if self.enabled:
            try:
                self.client: Client = create_client(self.url, self.key)
            except Exception as e:
                print(f"Failed to initialize Supabase client: {e}")
                self.enabled = False
        
        if not self.enabled:
            print("Supabase config not provided or failed. Running in mock database mode.")
            self.client = None
            self.mock_runs = {}
            self.mock_metrics = {}
            self.mock_results = {}
            # Prepopulate mock benchmarks
            self.mock_benchmarks = {
                ('Manufacturing', 'revenue_per_employee'): {"p25": 120000, "p50": 175000, "p75": 240000},
                ('Manufacturing', 'output_per_payroll'): {"p25": 3.5, "p50": 4.2, "p75": 5.1},
                ('Manufacturing', 'gross_margin'): {"p25": 25, "p50": 35, "p75": 45},
                ('Manufacturing', 'operating_margin'): {"p25": 5, "p50": 12, "p75": 20},
                
                ('Services', 'revenue_per_employee'): {"p25": 100000, "p50": 145000, "p75": 210000},
                ('Services', 'output_per_payroll'): {"p25": 2.8, "p50": 3.8, "p75": 4.9},
                ('Services', 'gross_margin'): {"p25": 40, "p50": 55, "p75": 70},
                ('Services', 'operating_margin'): {"p25": 8, "p50": 18, "p75": 28},
                
                ('Retail', 'revenue_per_employee'): {"p25": 150000, "p50": 190000, "p75": 250000},
                ('Retail', 'output_per_payroll'): {"p25": 4.2, "p50": 5.3, "p75": 6.5},
                ('Retail', 'gross_margin'): {"p25": 20, "p50": 28, "p75": 38},
                ('Retail', 'operating_margin'): {"p25": 2, "p50": 6, "p75": 12}
            }

    # Ingestion runs
    async def create_ingestion_run(self, sector: str, company_name: str, 
                                    document_type: str) -> str:
        """Create new ingestion run, return run_id"""
        import uuid
        run_id = str(uuid.uuid4())
        
        if self.enabled:
            try:
                response = self.client.table("ingestion_runs").insert({
                    "run_id": run_id,
                    "sector": sector,
                    "company_name": company_name,
                    "document_type": document_type,
                    "status": "processing"
                }).execute()
                return response.data[0]["run_id"]
            except Exception as e:
                print(f"Supabase create_ingestion_run error: {e}, falling back to mock")
        
        self.mock_runs[run_id] = {
            "run_id": run_id,
            "sector": sector,
            "company_name": company_name,
            "document_type": document_type,
            "status": "processing"
        }
        return run_id
    
    async def update_run_status(self, run_id: str, status: str, 
                                 confidence: float = None, error_message: str = None):
        """Update ingestion run status"""
        data = {"status": status}
        if confidence is not None:
            data["confidence_score"] = confidence
        if error_message is not None:
            data["error_message"] = error_message
            
        if self.enabled:
            try:
                self.client.table("ingestion_runs").update(data).eq(
                    "run_id", run_id
                ).execute()
                return
            except Exception as e:
                print(f"Supabase update_run_status error: {e}")
                
        if run_id in self.mock_runs:
            self.mock_runs[run_id].update(data)
    
    # Extracted metrics
    async def store_extracted_metrics(self, run_id: str, metrics: Dict[str, Any]):
        """Store extracted metrics"""
        rows = []
        for metric_name, metric_val in metrics.items():
            if metric_val is None:
                continue
            rows.append({
                "run_id": run_id,
                "metric_name": metric_name,
                "metric_value": metric_val.get("value") if isinstance(metric_val, dict) else metric_val,
                "metric_unit": metric_val.get("unit") if isinstance(metric_val, dict) else None,
                "confidence": metric_val.get("confidence", 0) if isinstance(metric_val, dict) else 0,
                "source_text": metric_val.get("source", "") if isinstance(metric_val, dict) else ""
            })
        
        if self.enabled:
            try:
                self.client.table("extracted_metrics").insert(rows).execute()
                return
            except Exception as e:
                print(f"Supabase store_extracted_metrics error: {e}")
                
        self.mock_metrics[run_id] = rows
    
    # Benchmark lookup
    async def get_benchmark(self, sector: str, metric_name: str) -> Dict:
        """Get benchmark data for sector and metric"""
        if self.enabled:
            try:
                response = self.client.table("benchmark_metrics").select(
                    "p25, p50, p75"
                ).eq("sector", sector).eq("metric_name", metric_name).execute()
                
                if response.data:
                    return response.data[0]
            except Exception as e:
                print(f"Supabase get_benchmark error: {e}")
                
        # Default mock fallback values if not found or Supabase disabled
        # Sector matching support (Retail, Services, Manufacturing, or others mapped to Services)
        normalized_sector = sector if sector in ["Manufacturing", "Services", "Retail"] else "Services"
        return self.mock_benchmarks.get((normalized_sector, metric_name), {"p25": 0, "p50": 0, "p75": 0})
    
    # Results storage
    async def store_assessment_result(self, result_data: Dict) -> str:
        """Store assessment result, return result_id"""
        if self.enabled:
            try:
                response = self.client.table("assessment_results").insert(
                    result_data
                ).execute()
                return response.data[0]["result_id"]
            except Exception as e:
                print(f"Supabase store_assessment_result error: {e}")
                
        res_id = result_data.get("result_id")
        self.mock_results[res_id] = result_data
        return res_id

# Initialize
db_service = DatabaseService()
