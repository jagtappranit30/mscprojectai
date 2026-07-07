import sys
from pathlib import Path
import pytest
from fpdf import FPDF

# Ensure project root is on path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.document_parser import (
    detect_file_type,
    parse_csv,
    parse_pdf,
    parse_document,
)

# Helpers to generate PDF bytes
def create_mock_pdf(pages: int = 1, text_per_page: str = "This is a clean page text.") -> bytes:
    pdf = FPDF()
    for i in range(pages):
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(200, 10, txt=f"{text_per_page} (page {i+1})", ln=1)
    return bytes(pdf.output())


def create_scanned_mock_pdf() -> bytes:
    # PDF with no text layer at all (just empty pages)
    pdf = FPDF()
    pdf.add_page()
    return bytes(pdf.output())


def test_detect_file_type():
    # 1. PDF
    pdf_bytes = b"%PDF-1.4\n..."
    assert detect_file_type(pdf_bytes) == "pdf"

    # 2. Comma CSV
    csv_bytes = b"Revenue,Profit,Sector\n100,50,Retail\n200,100,Retail"
    assert detect_file_type(csv_bytes) == "csv"

    # 3. Semicolon CSV
    csv_semi = b"Revenue;Profit;Sector\n100;50;Retail"
    assert detect_file_type(csv_semi) == "csv"

    # 4. Unknown
    unknown_bytes = b"\x00\x01\x02\x03\x04\x05"
    assert detect_file_type(unknown_bytes) == "unknown"


def test_parse_csv_clean_comma():
    csv_content = b"Sector,Revenue,Profit\nRetail,120000,50000\nServices,150000,60000"
    parsed = parse_csv(csv_content)
    assert parsed.success
    assert parsed.source_type == "csv"
    assert parsed.page_count == 1
    assert parsed.row_count == 2
    assert "Sector: Retail, Revenue: 120000, Profit: 50000" in parsed.raw_text
    assert "Sector: Services, Revenue: 150000, Profit: 60000" in parsed.raw_text
    assert len(parsed.warnings) == 0


def test_parse_csv_semicolon():
    csv_content = b"Sector;Revenue;Profit\nManufacturing;300000;45000"
    parsed = parse_csv(csv_content)
    assert parsed.success
    assert parsed.source_type == "csv"
    assert "Sector: Manufacturing, Revenue: 300000, Profit: 45000" in parsed.raw_text


def test_parse_csv_excel_bom():
    # Prepend UTF-8 BOM bytes \xef\xbb\xbf
    csv_content = b"\xef\xbb\xbfSector,Revenue,Profit\nRetail,500000,85000"
    parsed = parse_csv(csv_content)
    assert parsed.success
    assert parsed.source_type == "csv"
    assert "Sector: Retail, Revenue: 500000, Profit: 85000" in parsed.raw_text


def test_parse_csv_inconsistent_columns():
    csv_content = b"Sector,Revenue,Profit\nRetail,120000\nServices,150000,60000,ExtraValue"
    parsed = parse_csv(csv_content)
    assert parsed.success
    assert len(parsed.warnings) > 0
    # Row 1 should be padded with empty string
    assert "Sector: Retail, Revenue: 120000, Profit: " in parsed.raw_text
    # Row 2 should be truncated
    assert "Sector: Services, Revenue: 150000, Profit: 60000" in parsed.raw_text
    assert "ExtraValue" not in parsed.raw_text


def test_parse_pdf_clean():
    pdf_bytes = create_mock_pdf(pages=3, text_per_page="Financial summary for Vantly corporation.")
    parsed = parse_pdf(pdf_bytes)
    assert parsed.success
    assert parsed.source_type == "pdf"
    assert parsed.page_count == 3
    assert "--- Page 1 ---" in parsed.raw_text
    assert "--- Page 2 ---" in parsed.raw_text
    assert "--- Page 3 ---" in parsed.raw_text
    assert "Financial summary for Vantly corporation. (page 1)" in parsed.raw_text
    assert "Financial summary for Vantly corporation. (page 3)" in parsed.raw_text


def test_parse_pdf_scanned():
    pdf_bytes = create_scanned_mock_pdf()
    parsed = parse_pdf(pdf_bytes)
    assert not parsed.success
    assert "scanned image" in parsed.error_message.lower()


def test_parse_pdf_large():
    # 21 pages
    pdf_bytes = create_mock_pdf(pages=21)
    parsed = parse_pdf(pdf_bytes)
    assert not parsed.success
    assert "exceeds maximum size of 20 pages" in parsed.error_message.lower()


def test_parse_mislabeled_file():
    # PDF content but file is named mislabeled.csv
    pdf_bytes = create_mock_pdf(pages=1, text_per_page="This is a PDF masquerading as a CSV file.")
    parsed = parse_document(pdf_bytes, "mislabeled.csv")
    assert parsed.success
    assert parsed.source_type == "pdf"
    assert "This is a PDF masquerading as a CSV file." in parsed.raw_text


def test_parse_empty_file():
    parsed = parse_document(b"", "empty.pdf")
    assert not parsed.success
    assert "empty" in parsed.error_message.lower()


def test_parse_corrupted_pdf():
    # Junk bytes starting with PDF magic bytes
    junk_bytes = b"%PDF-1.4\n" + b"\x00\x01\x02" * 10
    parsed = parse_document(junk_bytes, "corrupted.pdf")
    assert not parsed.success
    assert "corrupted" in parsed.error_message.lower() or "scanned" in parsed.error_message.lower()
