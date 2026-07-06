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
            print(f"FastEmbed initialised (lazy): {_FASTEMBED_MODEL}")
        except Exception as exc:
            print(
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
            print("FastEmbed unloaded from memory (GC triggered).")

    # ──────────────────────────────────────────────────────────
    async def chunk_text(
        self,
        text: str,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> List[str]:
        """
        Split text into word-count chunks with overlap.

        Parameters
        ----------
        text:       Raw document text.
        chunk_size: Approximate number of words per chunk (≈ tokens for English).
        overlap:    Number of words shared between consecutive chunks.
        """
        words = text.split()
        chunks: List[str] = []
        start = 0

        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunks.append(" ".join(words[start:end]))
            if end >= len(words):
                break
            start = end - overlap
            if start < 0:
                break

        return chunks

    # ──────────────────────────────────────────────────────────
    async def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        """
        Generate 384-dimensional embeddings for a list of text chunks.
        Triggers lazy FastEmbed load on first call.
        Falls back to zero-vectors if FastEmbed is unavailable.
        """
        # Lazy-load model on first actual embedding request
        if not self.enabled:
            self._load_fastembed()

        if not self.enabled:
            # Zero-vector fallback — preserves pipeline flow without crashing
            return [[0.0] * _EMBEDDING_DIM for _ in chunks]

        try:
            embeddings = list(self._embedding_model.embed(chunks))  # type: ignore[union-attr]
            return [emb.tolist() for emb in embeddings]
        except Exception as exc:
            print(f"Embedding error: {exc} — returning zero-vectors")
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
        if db_service.enabled:
            try:
                rows = [
                    {
                        "run_id": run_id,
                        "chunk_index": i,
                        "content": chunk,
                        "embedding": emb,
                        "source_filename": source_filename,
                    }
                    for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
                ]
                db_service.client.table("document_chunks").insert(rows).execute()
                return
            except Exception as exc:
                print(f"Supabase store_embeddings error: {exc} — using local cache")

        # Local fallback cache
        existing = self.mock_chunks.get(run_id, [])
        existing.extend(zip(chunks, embeddings))
        self.mock_chunks[run_id] = existing

    # ──────────────────────────────────────────────────────────
    async def retrieve_context(
        self,
        query: str,
        run_id: str,
        top_k: int = 5,
    ) -> List[str]:
        """
        Retrieve the top-k most relevant text chunks for a query string.

        Primary path: Supabase pgvector cosine similarity via match_documents RPC.
        Fallback:     NumPy cosine similarity over the in-process cache.
        """
        # Embed the query
        query_emb = (await self.embed_chunks([query]))[0]

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
                    return [item["chunk_text"] for item in response.data]
            except Exception as exc:
                print(f"Supabase retrieve_context error: {exc} — falling back to local search")

        # NumPy cosine similarity fallback
        run_data = self.mock_chunks.get(run_id, [])
        if not run_data:
            return []

        q_vec = np.array(query_emb)
        scores: List[Tuple[str, float]] = []

        for chunk, emb in run_data:
            c_vec = np.array(emb)
            denom = np.linalg.norm(q_vec) * np.linalg.norm(c_vec)
            sim = float(np.dot(q_vec, c_vec) / denom) if denom > 0 else 0.0
            scores.append((chunk, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [chunk for chunk, _ in scores[:top_k]]


# Module-level singleton
rag_service = RAGService()
