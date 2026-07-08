"""
RAG (Retrieval-Augmented Generation) service for the SME Productivity Assessment Platform.

Design principles (MSc spec):
- Pure Python — no LangChain, no LlamaIndex.
- Embeddings: bge-small-en-v1.5 via FastEmbed (ONNX runtime, ~35 MB model).
- Vector store: Supabase pgvector via the match_documents RPC function.
- 500-token chunk window, 50-token overlap (word-count approximation).
- Fallback: if Supabase is unavailable, cosine similarity computed locally with NumPy.
- ragas dependency removed — it pulls PyTorch and violates the 512 MB memory ceiling.
- FastEmbed is lazy-loaded (first use only) to keep startup RAM below Render free-tier limit.
"""

from __future__ import annotations

import gc
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..utils.database import db_service

# FastEmbed model identifier
_FASTEMBED_MODEL = "BAAI/bge-small-en-v1.5"
_EMBEDDING_DIM = 384


from ..utils.logger import logger

class RAGService:
    """
    Custom Retrieval-Augmented Generation implementation.
    Pure Python, no LangChain dependency.

    FastEmbed is intentionally NOT loaded at __init__ time.
    It is loaded on the first call to embed_chunks() to keep the
    Render free-tier startup footprint below 512 MB.
    """

    def __init__(self):
        # _embedding_model is None until first use (lazy init)
        self._embedding_model: Optional[object] = None
        self._embed_tried: bool = False   # avoid retrying after a failed load
        # In-process fallback cache: {run_id: [(chunk_text, embedding_list), ...]}
        self.mock_chunks: Dict[str, List[Tuple[str, List[float]]]] = {}

    # ──────────────────────────────────────────────────────────
    @property
    def enabled(self) -> bool:
        """True once FastEmbed has been successfully loaded."""
        return self._embedding_model is not None

    def _load_fastembed(self) -> None:
        """
        Load the FastEmbed model on first use.
        Called lazily from embed_chunks() — never at startup.
        """
        if self._embed_tried:
            return   # already attempted (success or failure)
        self._embed_tried = True
        try:
            from fastembed import TextEmbedding  # type: ignore

            self._embedding_model = TextEmbedding(
                model_name=_FASTEMBED_MODEL,
                cache_dir=os.getenv("FASTEMBED_CACHE_PATH", "/tmp/fastembed_cache"),
            )
            logger.info(f"FastEmbed initialised (lazy): {_FASTEMBED_MODEL}")
        except Exception as exc:
            logger.error(
                f"FastEmbed lazy-init failed: {exc}. "
                "RAG running in local-cosine fallback mode."
            )

    def unload_fastembed(self) -> None:
        """
        Release the FastEmbed model from memory and run GC.
        Call after a request completes to reclaim RAM on the free tier.
        """
        if self._embedding_model is not None:
            self._embedding_model = None
            self._embed_tried = False   # allow reload on next request
            gc.collect()
            logger.info("FastEmbed unloaded from memory (GC triggered).")

    # ──────────────────────────────────────────────────────────
    async def chunk_text(
        self,
        text: str,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> List[str]:
        """
        Chunk text based on document structure (page markers if present),
        otherwise fall back to word-count sliding window.
        """
        logger.info("Chunking text started.")
        
        # Check if structured page markers exist
        if "--- Page " in text:
            logger.info("Structure-based page markers detected. Chunking page-by-page.")
            pages = text.split("--- Page ")
            chunks = []
            
            # The first split part might be empty or preamble text
            preamble = pages[0].strip()
            if preamble:
                chunks.append(f"[Section: Document Header, Chunk ID: header_chunk]\n\n{preamble}")
                
            for p in pages[1:]:
                p = p.strip()
                if not p:
                    continue
                # Parse page number (e.g., "1 ---\n...")
                parts = p.split(" ---\n", 1)
                if len(parts) == 2:
                    page_num = parts[0].strip()
                    page_content = parts[1].strip()
                else:
                    page_num = "Unknown"
                    page_content = p
                
                # Guess section headings from first line of page content
                first_line = page_content.split("\n")[0].strip()
                section_heading = first_line[:50] if len(first_line) > 5 else "Financial Statement"
                
                chunk_meta = f"[Page: {page_num}, Section: {section_heading}, Chunk ID: page{page_num}_chunk]"
                chunks.append(f"{chunk_meta}\n\n{page_content}")
                
            logger.info(f"Structure-based chunking completed. Created {len(chunks)} chunks.")
            return chunks

        # Fallback to word-count chunking
        logger.info("Falling back to word-count sliding window chunking.")
        words = text.split()
        chunks: List[str] = []
        start = 0

        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_content = " ".join(words[start:end])
            chunk_meta = f"[Chunk Index: {len(chunks)}, Chunk ID: word_chunk_{len(chunks)}]"
            chunks.append(f"{chunk_meta}\n\n{chunk_content}")
            if end >= len(words):
                break
            start = end - overlap
            if start < 0:
                break

        logger.info(f"Word-count chunking completed. Created {len(chunks)} chunks.")
        return chunks

    # ──────────────────────────────────────────────────────────
    async def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        """
        Generate 384-dimensional embeddings for a list of text chunks.
        Triggers lazy FastEmbed load on first call.
        Falls back to zero-vectors if FastEmbed is unavailable.
        """
        logger.info(f"Embedding {len(chunks)} chunks.")
        if not self.enabled:
            self._load_fastembed()

        if not self.enabled:
            logger.warning("Embedding model disabled. Returning zero-vectors.")
            return [[0.0] * _EMBEDDING_DIM for _ in chunks]

        try:
            embeddings = list(self._embedding_model.embed(chunks))  # type: ignore[union-attr]
            logger.info("Embeddings generation complete.")
            return [emb.tolist() for emb in embeddings]
        except Exception as exc:
            logger.error(f"Embedding error: {exc} — returning zero-vectors")
            return [[0.0] * _EMBEDDING_DIM for _ in chunks]

    # ──────────────────────────────────────────────────────────
    async def store_embeddings(
        self,
        run_id: str,
        chunks: List[str],
        embeddings: List[List[float]],
        source_filename: str = "",
    ) -> None:
        """
        Store text chunks and their embeddings.
        Primary: Supabase pgvector (document_chunks table).
        Fallback: in-process dict for mock/local mode.
        """
        logger.info(f"Storing embeddings for run_id: {run_id}")
        if db_service.enabled:
            try:
                rows = [
                    {
                        "run_id": run_id,
                        "chunk_index": i,
                        "chunk_text": chunk,
                        "embedding": emb,
                    }
                    for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
                ]
                db_service.client.table("document_chunks").insert(rows).execute()
                logger.info("Stored embeddings in Supabase.")
                return
            except Exception as exc:
                logger.error(f"Supabase store_embeddings error: {exc} — using local cache")

        # Local fallback cache
        existing = self.mock_chunks.get(run_id, [])
        existing.extend(zip(chunks, embeddings))
        self.mock_chunks[run_id] = existing
        logger.info("Stored embeddings in local memory cache.")

    # ──────────────────────────────────────────────────────────
    async def retrieve_context(
        self,
        query: str,
        run_id: str,
        top_k: int = 5,
    ) -> List[str]:
        """
        Retrieve the top-k most relevant text chunks for a query string.
        Merges adjacent/contiguous chunks to preserve contextual flow.
        """
        logger.info(f"Retrieving context for query: '{query}'")
        query_emb = (await self.embed_chunks([query]))[0]
        matched_chunks = []

        if db_service.enabled:
            try:
                response = db_service.client.rpc(
                    "match_documents",
                    {
                        "query_embedding": query_emb,
                        "match_count": top_k,
                        "p_run_id": run_id,
                    },
                ).execute()
                if response.data:
                    matched_chunks = response.data
            except Exception as exc:
                logger.error(f"Supabase retrieve_context error: {exc} — falling back to local search")

        # Fallback local search if Supabase is disabled or failed
        if not matched_chunks:
            run_data = self.mock_chunks.get(run_id, [])
            if run_data:
                q_vec = np.array(query_emb)
                scores = []
                for idx, (chunk, emb) in enumerate(run_data):
                    c_vec = np.array(emb)
                    denom = np.linalg.norm(q_vec) * np.linalg.norm(c_vec)
                    sim = float(np.dot(q_vec, c_vec) / denom) if denom > 0 else 0.0
                    scores.append({"chunk_index": idx, "chunk_text": chunk, "similarity": sim})
                scores.sort(key=lambda x: x["similarity"], reverse=True)
                matched_chunks = scores[:top_k]

        if not matched_chunks:
            logger.info("No matching context chunks found.")
            return []

        # ── Group and merge adjacent chunks ──
        try:
            # 1. Fetch all chunks in order for this run to know their indices
            all_chunks_ordered = []
            if db_service.enabled:
                db_res = db_service.client.table("document_chunks")\
                    .select("chunk_index, chunk_text")\
                    .eq("run_id", run_id)\
                    .order("chunk_index")\
                    .execute()
                if db_res.data:
                    all_chunks_ordered = db_res.data
            else:
                run_data = self.mock_chunks.get(run_id, [])
                all_chunks_ordered = [{"chunk_index": idx, "chunk_text": chunk} for idx, (chunk, _) in enumerate(run_data)]

            # Map chunk text to index
            text_to_index = {item["chunk_text"].strip(): item["chunk_index"] for item in all_chunks_ordered}
            
            # Find the indices of matched chunks
            matched_indices = []
            for item in matched_chunks:
                txt = item["chunk_text"].strip()
                if txt in text_to_index:
                    matched_indices.append(text_to_index[txt])

            matched_indices = sorted(list(set(matched_indices)))
            logger.debug(f"Retrieved matched indices: {matched_indices}")

            # Group adjacent indices (e.g. [1, 2, 5] -> [[1, 2], [5]])
            groups = []
            if matched_indices:
                current_group = [matched_indices[0]]
                for idx in matched_indices[1:]:
                    if idx == current_group[-1] + 1:
                        current_group.append(idx)
                    else:
                        groups.append(current_group)
                        current_group = [idx]
                groups.append(current_group)

            # Build merged text chunks
            merged_results = []
            for g in groups:
                # Fetch text of each chunk in the adjacent group
                group_texts = []
                for idx in g:
                    # Find matching chunk text
                    chunk_item = next((item for item in all_chunks_ordered if item["chunk_index"] == idx), None)
                    if chunk_item:
                        group_texts.append(chunk_item["chunk_text"])
                
                if len(g) > 1:
                    logger.info(f"Merging {len(g)} adjacent chunks (indices: {g}) into a single contiguous context.")
                merged_results.append("\n\n--- Continued Context ---\n\n".join(group_texts))
                
            return merged_results

        except Exception as exc:
            logger.error(f"Error merging adjacent chunks: {exc} — returning original match list")
            return [item["chunk_text"] for item in matched_chunks]


# Module-level singleton
rag_service = RAGService()
