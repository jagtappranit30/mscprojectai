import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from backend.services.document_parser import format_table_as_markdown, parse_pdf
from backend.services.rag import RAGService
from backend.services.extraction import ExtractionService
from backend.models import LLMMetricResponse, ExtractedMetrics

def test_format_table_as_markdown():
    table = [
        ["Revenue", "Payroll", "Year"],
        ["1000", "300", "2024"],
        [None, "", None]  # Should be skipped
    ]
    markdown = format_table_as_markdown(table)
    assert "| Revenue | Payroll | Year |" in markdown
    assert "| --- | --- | --- |" in markdown
    assert "| 1000 | 300 | 2024 |" in markdown


@pytest.mark.asyncio
async def test_page_chunking():
    rag = RAGService()
    text = "Preamble\n--- Page 1 ---\nContent of page 1\n--- Page 2 ---\nContent of page 2"
    chunks = await rag.chunk_text(text)
    assert len(chunks) == 3
    assert "[Section: Document Header" in chunks[0]
    assert "[Page: 1" in chunks[1]
    assert "Content of page 1" in chunks[1]
    assert "[Page: 2" in chunks[2]


@pytest.mark.asyncio
async def test_adjacent_chunk_merging():
    rag = RAGService()
    run_id = "test_run"
    rag.mock_chunks[run_id] = [
        ("Chunk index 0 text", [0]*384),
        ("Chunk index 1 text", [0]*384),
        ("Chunk index 2 text", [0]*384)
    ]
    
    # Mock retrieval returning index 0 and index 1 (adjacent)
    with patch("backend.services.rag.db_service") as mock_db:
        mock_db.enabled = False  # Falls back to local list search
        
        # Mock embed_chunks to return mock query vector
        with patch.object(rag, "embed_chunks", return_value=[[0]*384]):
            merged = await rag.retrieve_context(query="query", run_id=run_id, top_k=2)
            assert len(merged) == 1
            assert "Chunk index 0 text" in merged[0]
            assert "Chunk index 1 text" in merged[0]


@pytest.mark.asyncio
async def test_extraction_repair_loop_success():
    with patch.dict("os.environ", {"GROQ_MOCK_MODE": "false"}):
        service = ExtractionService()
        service.client = AsyncMock()

        # First attempt returns invalid response missing page_number/unit, second is valid
        invalid_dict = {"metric_name": "revenue", "value": 1000}
        valid_dict = {"metric_name": "revenue", "value": 1000, "unit": "£", "confidence": 0.9, "source_quote": "1000", "page_number": "1"}

        service.client.extract.side_effect = [invalid_dict, valid_dict]

        # Test the internal _extract_one by mocking retrieved context
        rag_service = MagicMock()
        rag_service.retrieve_context = AsyncMock(return_value=["mock chunk text"])
        with patch("backend.services.extraction.EXTRACTION_QUERIES", [("revenue", "query", "£")]):
            metrics, conflict_warnings, errors, source_passages = await service.extract_all_metrics(
                run_id="run_id", rag_service=rag_service
            )
            
            # Verify it was successfully repaired and doesn't contain validation errors
            assert len(errors) == 0
            assert metrics.revenue == 1000


def test_clean_financial_text():
    from backend.services.document_parser import _clean_financial_text
    
    # Test currency rejoining
    assert _clean_financial_text("revenue £ 2,500,000") == "revenue £2,500,000"
    
    # Test whitespace collapse
    assert _clean_financial_text("gross   margin   40%") == "gross margin 40%"
    
    # Test negative parentheses conversion
    assert _clean_financial_text("net loss (45,000)") == "net loss -45,000"
    assert _clean_financial_text("loss (123.45)") == "loss -123.45"


def test_is_multi_column():
    from backend.services.document_parser import is_multi_column
    
    # Mock a page object with 2 columns of words
    page = MagicMock()
    page.width = 600
    
    # Create words for left column (x-coordinates < 240)
    left_words = [
        {"x0": 10, "x1": 50, "text": "left"},
        {"x0": 20, "x1": 80, "text": "column"},
        {"x0": 15, "x1": 90, "text": "text"},
        {"x0": 10, "x1": 70, "text": "here"},
        {"x0": 20, "x1": 80, "text": "content"},
    ]
    # Create words for right column (x-coordinates > 360)
    right_words = [
        {"x0": 370, "x1": 410, "text": "right"},
        {"x0": 380, "x1": 440, "text": "column"},
        {"x0": 375, "x1": 450, "text": "text"},
        {"x0": 370, "x1": 430, "text": "here"},
        {"x0": 380, "x1": 440, "text": "content"},
    ]
    
    # Combined words list
    page.extract_words.return_value = left_words * 4 + right_words * 4
    
    assert is_multi_column(page) is True


def test_extract_text_in_reading_order():
    from backend.services.document_parser import extract_text_in_reading_order
    
    # Mock page with scrambled drawing order words
    page = MagicMock()
    # Scrambled drawing stream order:
    # 2nd line first, then 1st line, with scrambled words in 1st line
    page.extract_words.return_value = [
        {"top": 50, "x0": 200, "text": "line"},
        {"top": 10, "x0": 150, "text": "is"},
        {"top": 10, "x0": 200, "text": "first"},
        {"top": 50, "x0": 100, "text": "second"},
        {"top": 10, "x0": 100, "text": "this"},
    ]
    
    extracted = extract_text_in_reading_order(page)
    # Expected visual order:
    # Line 1: this is first
    # Line 2: second line
    assert extracted == "this is first\nsecond line"


