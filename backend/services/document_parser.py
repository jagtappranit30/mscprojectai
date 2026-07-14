import csv
import io
from typing import List, Optional
# pyrefly: ignore [missing-import]
import filetype
# pyrefly: ignore [missing-import]
import fitz  # PyMuPDF
import pdfplumber
from pydantic import BaseModel

class ParsedDocument(BaseModel):
    raw_text: str          # Clean text ready for LLM prompt
    source_type: str        # "csv" or "pdf"
    page_count: int          # 1 for CSV, N for PDF
    row_count: Optional[int] = None  # For CSV only, None for PDF
    warnings: List[str]      # e.g., ["Encoding fallback used", "3 rows skipped due to malformed data"]
    confidence: float        # 0-100, how confident we are the extraction is clean
    success: bool
    error_message: Optional[str] = None


def detect_file_type(file_bytes: bytes) -> str:
    """
    Check actual file content/magic bytes, not just filename extension.
    Returns 'pdf', 'csv', or 'unknown'.
    """
    # 1. Use filetype library for MIME type detection
    kind = filetype.guess(file_bytes)
    if kind:
        if kind.mime == "application/pdf":
            return "pdf"
        elif kind.mime == "text/csv":
            return "csv"

    # 2. PDF magic bytes fallback check
    if file_bytes.startswith(b"%PDF-"):
        return "pdf"

    # 3. CSV/text check: attempt decode and check for delimiter patterns
    sample = file_bytes[:10240]
    decoded_sample = None
    for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            decoded_sample = sample.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if decoded_sample:
        # Check for typical delimiters in the first line
        lines = [line.strip() for line in decoded_sample.splitlines() if line.strip()]
        if lines:
            first_line = lines[0]
            for delim in [",", ";", "\t"]:
                if delim in first_line:
                    return "csv"

    return "unknown"


def parse_csv(file_bytes: bytes) -> ParsedDocument:
    """
    Parse CSV bytes with auto-delimiter detection, encoding fallback, Excel BOM stripping,
    and row validation.
    """
    warnings = []
    decoded_text = None
    encoding_used = "utf-8"

    # Handle common encoding issues (Excel exports)
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            decoded_text = file_bytes.decode(enc)
            encoding_used = enc
            if enc != "utf-8-sig" and enc != "utf-8":
                warnings.append(f"Encoding fallback used: {enc}")
            break
        except UnicodeDecodeError:
            continue

    if decoded_text is None:
        return ParsedDocument(
            raw_text="",
            source_type="csv",
            page_count=0,
            warnings=warnings,
            confidence=0.0,
            success=False,
            error_message="CSV file encoding is unsupported. Please save the CSV file as UTF-8."
        )

    # Clean leading whitespace and strip BOM manually if it somehow persisted
    decoded_text = decoded_text.lstrip("\ufeff")

    if not decoded_text.strip():
        return ParsedDocument(
            raw_text="",
            source_type="csv",
            page_count=0,
            warnings=warnings,
            confidence=0.0,
            success=False,
            error_message="CSV file is empty."
        )

    # Delimiter detection
    delimiter = ","
    lines = [line.strip() for line in decoded_text.splitlines() if line.strip()]
    sample_text = "\n".join(lines[:5])
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=[",", ";", "\t"])
        delimiter = dialect.delimiter
    except Exception:
        # Manual count-based fallback
        first_line = lines[0] if lines else ""
        counts = {",": first_line.count(","), ";": first_line.count(";"), "\t": first_line.count("\t")}
        best_delim = max(counts, key=counts.get)
        if counts[best_delim] > 0:
            delimiter = best_delim

    # Parse rows
    try:
        reader = csv.reader(io.StringIO(decoded_text), delimiter=delimiter)
        raw_rows = []
        for i, row in enumerate(reader):
            if any(cell.strip() for cell in row):
                raw_rows.append(row)
    except Exception as exc:
        return ParsedDocument(
            raw_text="",
            source_type="csv",
            page_count=0,
            warnings=warnings,
            confidence=0.0,
            success=False,
            error_message=f"Failed to parse CSV rows: {exc}"
        )

    if not raw_rows:
        return ParsedDocument(
            raw_text="",
            source_type="csv",
            page_count=0,
            warnings=warnings,
            confidence=0.0,
            success=False,
            error_message="CSV file contains no data rows."
        )

    # Detect header presence
    has_header = False
    try:
        has_header = csv.Sniffer().has_header(sample_text)
    except Exception:
        # Basic heuristic: if first row is non-numeric strings and length > 1
        first_row = raw_rows[0]
        if len(first_row) > 1 and all(not val.replace(".", "", 1).isdigit() for val in first_row):
            has_header = True

    if has_header:
        headers = [h.strip() for h in raw_rows[0]]
        data_rows = raw_rows[1:]
        if not data_rows:
            return ParsedDocument(
                raw_text="",
                source_type="csv",
                page_count=1,
                row_count=0,
                warnings=warnings,
                confidence=0.0,
                success=False,
                error_message="CSV file is empty or contains only headers with no data rows."
            )
    else:
        headers = [f"Column {i+1}" for i in range(len(raw_rows[0]))]
        data_rows = raw_rows

    # Build clean key-value text lines
    lines_output = []
    malformed_rows = 0
    
    for idx, row in enumerate(data_rows):
        cells = [c.strip() for c in row]
        # Handle inconsistent column counts
        if len(cells) < len(headers):
            cells += [""] * (len(headers) - len(cells))
            malformed_rows += 1
        elif len(cells) > len(headers):
            cells = cells[:len(headers)]
            malformed_rows += 1
            
        row_text = ", ".join(f"{headers[i]}: {cells[i]}" for i in range(len(headers)))
        lines_output.append(row_text)

    if malformed_rows > 0:
        warnings.append(f"{malformed_rows} rows had inconsistent column counts and were auto-aligned.")

    # Multi-section warnings
    row_lengths = [len(r) for r in data_rows]
    if len(set(row_lengths)) > 1:
        warnings.append("Inconsistent column counts across sections detected; check file formatting.")

    raw_text = "\n".join(lines_output)
    
    # Calculate confidence based on encoding fallbacks and malformed rows
    confidence = 100.0
    if encoding_used != "utf-8" and encoding_used != "utf-8-sig":
        confidence -= 10.0
    if malformed_rows > 0:
        confidence -= min(15.0, (malformed_rows / len(data_rows)) * 30.0)

    return ParsedDocument(
        raw_text=raw_text,
        source_type="csv",
        page_count=1,
        row_count=len(data_rows),
        warnings=warnings,
        confidence=confidence,
        success=True
    )


from ..utils.logger import logger
import re

def _clean_financial_text(text: str) -> str:
    """Cleans financial number formatting and currency symbols in raw text."""
    if not text:
        return ""
    # Rejoin currency symbol with adjacent number if separated by whitespace
    text = re.sub(r'£\s+(\d)', r'£\1', text)
    # Normalize multiple spaces to single space
    text = re.sub(r' {2,}', ' ', text)
    # Preserve but flag negative numbers in parentheses format
    text = re.sub(r'\((\d[\d,]*\.?\d*)\)', r'-\1', text)
    return text


def is_multi_column(page) -> bool:
    """Detects if a page likely contains a multi-column text layout."""
    width = page.width
    words = page.extract_words()
    if len(words) < 20:
        return False
    
    # Check if there's a vertical gap in the middle 20% of the page
    center_min = width * 0.4
    center_max = width * 0.6
    
    words_in_center = [w for w in words if w["x0"] > center_min and w["x1"] < center_max]
    left_words = [w for w in words if w["x1"] < center_min]
    right_words = [w for w in words if w["x0"] > center_max]
    
    # If the middle section has very few words, and both columns have substantial text
    if len(words_in_center) < len(words) * 0.05 and len(left_words) > len(words) * 0.2 and len(right_words) > len(words) * 0.2:
        return True
    return False


def format_table_as_markdown(table: List[List[Optional[str]]]) -> str:
    """Converts a parsed pdfplumber table list into a clean Markdown table grid."""
    if not table or not any(table):
        return ""
    
    # Clean cells, remove newlines, apply financial cleaning, and filter out entirely empty rows
    valid_rows = []
    for row in table:
        if row and any(cell is not None and str(cell).strip() != "" for cell in row):
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_row.append("")
                else:
                    # Replace newlines with spaces to avoid breaking table layout structure,
                    # collapse multiple spaces, and clean financial formatting.
                    cell_clean = " ".join(str(cell).split())
                    cleaned_row.append(_clean_financial_text(cell_clean).strip())
            valid_rows.append(cleaned_row)
            
    if not valid_rows:
        return ""
        
    cols_count = max(len(row) for row in valid_rows)
    for row in valid_rows:
        if len(row) < cols_count:
            row.extend([""] * (cols_count - len(row)))
            
    headers = valid_rows[0]
    separator = ["---"] * cols_count
    
    markdown_rows = []
    markdown_rows.append("| " + " | ".join(headers) + " |")
    markdown_rows.append("| " + " | ".join(separator) + " |")
    
    for row in valid_rows[1:]:
        markdown_rows.append("| " + " | ".join(row) + " |")
        
    return "\n\n" + "\n".join(markdown_rows) + "\n\n"


def parse_pdf(file_bytes: bytes, debug: bool = False) -> ParsedDocument:
    """
    Parse PDF using PyMuPDF (fitz) and pdfplumber for table extraction, with max 20 pages limit,
    page markers, and scanned image detection. Converts tables to clean Markdown format.
    Supports multi-column reading order and duplicate content removal.
    """
    import os
    if os.getenv("PDF_DEBUG_MODE") == "true":
        debug = True

    warnings = []
    logger.info("PDF parsing started.")

    # Open the document
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        logger.error(f"Failed to open PDF document: {exc}")
        return ParsedDocument(
            raw_text="",
            source_type="pdf",
            page_count=0,
            warnings=warnings,
            confidence=0.0,
            success=False,
            error_message=f"PDF file is corrupted or could not be opened: {exc}"
        )

    page_count = len(doc)
    logger.debug(f"PDF page count: {page_count}")
    
    # Max page limit
    if page_count > 20:
        doc.close()
        logger.warning(f"PDF exceeds page limit: {page_count} pages")
        return ParsedDocument(
            raw_text="",
            source_type="pdf",
            page_count=page_count,
            warnings=warnings,
            confidence=0.0,
            success=False,
            error_message=f"File exceeds maximum size of 20 pages (detected {page_count} pages). Please upload a smaller document."
        )

    # 1. Parse text and tables using pdfplumber (primary for structured metrics & tables)
    pages_text = []
    pdf_plumber_failed = False
    
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                # ── A. Table Strategy Selection ──
                table_settings = {
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                    "intersection_tolerance": 3,
                }
                
                # Compare default strategy vs. text-aligned strategy
                tables_default = page.extract_tables() or []
                tables_text = page.extract_tables(table_settings=table_settings) or []
                
                def count_cells(tbl_list):
                    if not tbl_list:
                        return 0
                    return sum(
                        sum(1 for cell in row if cell is not None and str(cell).strip() != "")
                        for row in tbl_list if row
                    )
                
                if count_cells(tables_text) > count_cells(tables_default):
                    tables = tables_text
                    used_strategy = "text-based"
                    logger.debug(f"Page {i + 1}: Using text-aligned table strategy.")
                else:
                    tables = tables_default
                    used_strategy = "default"
                    logger.debug(f"Page {i + 1}: Using default border-based table strategy.")
                
                # ── B. Duplicate Content Filtering (filter characters inside tables) ──
                tables_objs = page.find_tables(table_settings=table_settings if used_strategy == "text-based" else None)
                if tables_objs:
                    def filter_chars(obj):
                        if obj.get("object_type") == "char":
                            x0 = obj.get("x0", 0)
                            x1 = obj.get("x1", 0)
                            top = obj.get("top", 0)
                            bottom = obj.get("bottom", 0)
                            for t in tables_objs:
                                tx0, ttop, tx1, tbottom = t.bbox
                                if (x0 >= tx0 - 2 and x1 <= tx1 + 2 and
                                    top >= ttop - 2 and bottom <= tbottom + 2):
                                    return False
                        return True
                    text_extraction_page = page.filter(filter_chars)
                else:
                    text_extraction_page = page

                # ── C. Multi-Column Reading Order Layout ──
                if is_multi_column(text_extraction_page):
                    logger.info(f"Page {i + 1}: Multi-column layout detected. Splitting reading flow.")
                    width = text_extraction_page.width
                    height = text_extraction_page.height
                    left_bbox = (0, 0, width * 0.5, height)
                    right_bbox = (width * 0.5, 0, width, height)
                    left_text = text_extraction_page.within_bbox(left_bbox).extract_text() or ""
                    right_text = text_extraction_page.within_bbox(right_bbox).extract_text() or ""
                    page_text = left_text + "\n\n" + right_text
                else:
                    page_text = text_extraction_page.extract_text() or ""
                
                page_text = _clean_financial_text(page_text)

                # ── D. Append Markdown Formatted Tables ──
                if tables:
                    logger.debug(f"Page {i + 1}: Found {len(tables)} tables.")
                    table_strings = []
                    table_strings.append("\n--- Extracted Tables ---")
                    for t in tables:
                        table_md = format_table_as_markdown(t)
                        if table_md:
                            table_strings.append(table_md)
                    page_text += "\n" + "\n".join(table_strings)
                pages_text.append(f"--- Page {i + 1} ---\n{page_text}")
        raw_text = "\n\n".join(pages_text)
    except Exception as exc:
        logger.warning(f"pdfplumber table extraction failed: {exc}. Falling back to PyMuPDF.")
        warnings.append(f"pdfplumber failed to extract tables: {exc}. Falling back to PyMuPDF.")
        pdf_plumber_failed = True

    # 2. Fallback to PyMuPDF (fitz) text block extraction if pdfplumber failed
    if pdf_plumber_failed:
        pages_text = []
        for i in range(page_count):
            page = doc[i]
            blocks = page.get_text("blocks")
            # Sort blocks top-to-bottom, left-to-right
            sorted_blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
            page_text = "\n".join(b[4].strip() for b in sorted_blocks if b[4].strip())
            page_text = _clean_financial_text(page_text)
            pages_text.append(f"--- Page {i + 1} ---\n{page_text}")
        raw_text = "\n\n".join(pages_text)

    doc.close()

    # ── E. Optional Debug File Output ──
    if debug:
        try:
            with open("/tmp/pdf_debug_raw.txt", "w") as f:
                f.write(raw_text)
            logger.info("Saved raw PDF extraction content to /tmp/pdf_debug_raw.txt")
        except Exception as err:
            logger.warning(f"Failed to write PDF debug file: {err}")

    # Scanned PDF check: calculate character count without page headers/markers
    clean_text = raw_text
    for i in range(page_count):
        clean_text = clean_text.replace(f"--- Page {i + 1} ---", "")
    clean_text = clean_text.replace("--- Extracted Tables ---", "")
    char_count = len(clean_text.replace("\n", "").replace("\r", "").replace(" ", "").strip())
    logger.debug(f"Clean character count extracted: {char_count}")

    if char_count < 20:
        logger.warning("Scanned PDF detected - character count below threshold.")
        return ParsedDocument(
            raw_text="",
            source_type="pdf",
            page_count=page_count,
            warnings=warnings,
            confidence=0.0,
            success=False,
            error_message="PDF appears to be a scanned image with no extractable text. Please upload a text-based PDF or CSV instead."
        )

    logger.info("PDF parsing completed successfully.")
    return ParsedDocument(
        raw_text=raw_text,
        source_type="pdf",
        page_count=page_count,
        warnings=warnings,
        confidence=95.0 if not pdf_plumber_failed else 80.0,
        success=True
    )


def parse_document(file_bytes: bytes, filename: str) -> ParsedDocument:
    """
    Main entry point — validates size, detects type, parses, and validates output length.
    """
    # 1. Validation of empty file
    if not file_bytes or len(file_bytes) == 0:
        return ParsedDocument(
            raw_text="",
            source_type="unknown",
            page_count=0,
            warnings=[],
            confidence=0.0,
            success=False,
            error_message="File is empty or contains no content. Please upload a valid document."
        )

    # 2. File size limit checks
    file_size_mb = len(file_bytes) / (1024 * 1024)
    file_type = detect_file_type(file_bytes)

    if file_type == "pdf" and file_size_mb > 10.0:
        return ParsedDocument(
            raw_text="",
            source_type="pdf",
            page_count=0,
            warnings=[],
            confidence=0.0,
            success=False,
            error_message=f"File exceeds maximum size of 10MB (PDF size: {file_size_mb:.1f}MB)."
        )
    elif file_type == "csv" and file_size_mb > 5.0:
        return ParsedDocument(
            raw_text="",
            source_type="csv",
            page_count=0,
            warnings=[],
            confidence=0.0,
            success=False,
            error_message=f"File exceeds maximum size of 5MB (CSV size: {file_size_mb:.1f}MB)."
        )

    # 3. Route to parser
    if file_type == "pdf":
        parsed = parse_pdf(file_bytes)
    elif file_type == "csv":
        parsed = parse_csv(file_bytes)
    else:
        return ParsedDocument(
            raw_text="",
            source_type="unknown",
            page_count=0,
            warnings=[],
            confidence=0.0,
            success=False,
            error_message=f"File could not be read as CSV or PDF. Detected type: {file_type}. Please upload a valid CSV or PDF file."
        )

    # 4. Post-parsing validation: text length check to prevent empty/garbage extraction
    if parsed.success:
        clean_text = parsed.raw_text.strip()
        if len(clean_text) < 50:
            parsed.success = False
            parsed.error_message = "Document contains insufficient text content (minimum 50 characters required). Please upload a more complete document."

    return parsed
