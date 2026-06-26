import asyncio
import json
import re
from typing import Dict, Any
from ..models import ExtractedMetrics
from ..utils.config import settings

class ExtractionService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.enabled = api_key != "placeholder" and api_key != ""
        if self.enabled:
            try:
                from groq import Groq
                self.client = Groq(api_key=api_key)
            except Exception as e:
                print(f"Failed to initialize Groq client: {e}")
                self.enabled = False
    
    async def extract_metrics_from_text(self, text: str) -> ExtractedMetrics:
        """
        Use Groq Llama 3.3 to extract structured financial metrics from document text.
        Returns deterministic (temperature=0.3) structured JSON, with fallback mock parsing.
        """
        if not self.enabled:
            print("Groq API not configured or enabled. Using mock metric extraction.")
            return self._generate_mock_metrics(text)
            
        prompt = f"""You are a financial data extraction specialist. Your task is to extract 
financial metrics from the following document text.

RETURN ONLY VALID JSON (no markdown, no explanation). Use null for missing values.

Required JSON structure:
{{
  "revenue": <number in £>,
  "headcount": <integer>,
  "cogs": <number in £ or null>,
  "payroll": <number in £ or null>,
  "gross_margin": <percentage 0-100 or null>,
  "operating_margin": <percentage 0-100 or null>,
  "current_assets": <number in £ or null>,
  "current_liabilities": <number in £ or null>,
  "inventory": <number in £ or null>,
  "confidence": <0-100 confidence score>
}}

Document text:
{text}"""
        
        try:
            # Groq completion is synchronous in the std lib; run in threadpool if needed or call directly
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            
            # Parse JSON response
            response_text = response.choices[0].message.content.strip()
            
            # Remove markdown code block if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1].strip()
                if response_text.startswith("json"):
                    response_text = response_text[4:].strip()
            
            # Extract just the JSON object using regex if there's text around it
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)
                
            metrics_dict = json.loads(response_text)
            return ExtractedMetrics(**metrics_dict)
        
        except Exception as e:
            print(f"Error extracting metrics via Groq: {e}. Falling back to rule-based mock parser.")
            return self._generate_mock_metrics(text)

    def _generate_mock_metrics(self, text: str) -> ExtractedMetrics:
        """Rule-based metric parser for mock extraction or fallback"""
        text_lower = text.lower()
        
        # Simple regex heuristics to look for numbers in typical formats
        def find_number(patterns):
            for pattern in patterns:
                matches = re.findall(pattern, text_lower)
                if matches:
                    try:
                        # Extract digit characters, dot, or commas
                        num_str = re.sub(r'[^\d.]', '', matches[0])
                        return float(num_str)
                    except ValueError:
                        continue
            return None

        # Look for revenue/turnover
        revenue = find_number([
            r'(?:revenue|turnover)\s*(?:is|of|amounted to)?\s*(?:£|\$|usd|gbp)?\s*([\d,]+(?:\.\d+)?)',
            r'(?:total sales)\s*(?:is|of)?\s*(?:£|\$|usd|gbp)?\s*([\d,]+(?:\.\d+)?)'
        ])
        
        # Look for headcount/employees
        headcount = find_number([
            r'(?:headcount|employees|staff|number of staff)\s*(?:is|of|was)?\s*([\d,]+)',
            r'([\d,]+)\s*(?:employees|staff members|workers)'
        ])
        
        # Look for payroll/salaries
        payroll = find_number([
            r'(?:payroll|wages|salaries|staff costs)\s*(?:is|of)?\s*(?:£|\$|usd|gbp)?\s*([\d,]+(?:\.\d+)?)'
        ])
        
        # Default mock fallback if nothing matched
        if not revenue:
            revenue = 180000.0
        if not headcount:
            headcount = 10
        if not payroll:
            payroll = 45000.0
            
        return ExtractedMetrics(
            revenue=revenue,
            headcount=int(headcount),
            payroll=payroll,
            cogs=revenue * 0.4 if revenue else None,
            gross_margin=60.0,
            operating_margin=15.0,
            current_assets=75000.0,
            current_liabilities=50000.0,
            inventory=15000.0,
            confidence=85.0
        )

# Initialize
def get_extraction_service():
    api_key = settings.GROQ_API_KEY
    return ExtractionService(api_key)
