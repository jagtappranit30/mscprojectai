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
