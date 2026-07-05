import os
from fpdf import FPDF
from typing import Dict, Any

class PDFGenerator(FPDF):
    def header(self):
        # Arial bold 15
        self.set_font('Arial', 'B', 15)
        # Title
        self.cell(0, 10, 'SME Productivity Assessment Report', 0, 1, 'C')
        # Line break
        self.ln(5)

    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        # Arial italic 8
        self.set_font('Arial', 'I', 8)
        # Page number
        self.cell(0, 10, f'Page {self.page_no()} - Confidential & Proprietary', 0, 0, 'C')

def generate_assessment_report(result_data: Dict[str, Any]) -> str:
    """Generate a PDF report from assessment results and return the file path."""
    pdf = PDFGenerator()
    pdf.add_page()
    
    # Header Info
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"Company: {result_data.get('company_name', 'Unknown')}", 0, 1)
    pdf.cell(0, 10, f"Sector: {result_data.get('sector', 'Unknown')}", 0, 1)
    pdf.cell(0, 10, f"Confidence: {result_data.get('confidence_overall', 0)}%", 0, 1)
    pdf.ln(5)
    
    # Section 1: Productivity Index
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(0, 102, 204) # Primary Blue
    pdf.cell(0, 10, f"Productivity Index: {result_data.get('productivity_index', 0):.1f}/100", 0, 1)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)
    
    # Section 2 & 3 & 4: Sub-scores
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Component Scores', 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f"- Labour Efficiency: {result_data.get('labour_efficiency_score', 0):.1f}/50", 0, 1)
    pdf.cell(0, 8, f"- Financial Health: {result_data.get('financial_health_score', 0):.1f}/50", 0, 1)
    pdf.cell(0, 8, f"- Digital Maturity: {result_data.get('digital_maturity_score', 0):.1f}/100", 0, 1)
    pdf.ln(5)
    
    # Section 5: Recommendations
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Recommendations', 0, 1)
    pdf.set_font('Arial', '', 11)
    
    recommendations = result_data.get('recommendations', [])
    for rec in recommendations:
        # MultiCell handles text wrapping
        pdf.multi_cell(0, 8, f"* {rec}")
        pdf.ln(2)
        
    pdf.ln(10)
    
    # Section 6: Methodology
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Methodology', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 6, "Scores are calculated deterministically by comparing extracted financial metrics (Revenue per Employee, Margins, Liquidity) against sector-specific benchmarks using an AI-driven text extraction pipeline.")
    
    # Save to temp file
    import tempfile
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, f"Assessment_Report_{result_data.get('run_id')}.pdf")
    pdf.output(file_path)
    
    return file_path
