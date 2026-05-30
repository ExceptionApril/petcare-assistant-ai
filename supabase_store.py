"""
Supabase (Postgres + pgvector) vector store.

A drop-in replacement for the local ChromaDB `RAGEngine` that gives the app
TRUE persistence on Streamlit Cloud — uploaded documents survive restarts
because the vectors live in Postgres, not an ephemeral /tmp directory.

Embeddings are computed locally with chromadb's bundled ONNX MiniLM model
(384-dim, no external embedding service needed), then stored/queried in
Supabase. The public method surface matches `RAGEngine` exactly so the rest
of the app is backend-agnostic.

Requires (see supabase_schema.sql):
  - the `vector` extension
  - a `documents` table with a vector(384) column
  - the `match_documents()` RPC
And env/secrets:  SUPABASE_URL, SUPABASE_KEY
"""

import os
import logging

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

import rag_common

logger = logging.getLogger(__name__)

TABLE_NAME = "documents"
MATCH_RPC = "match_documents"


def is_supabase_configured() -> bool:
    """True only when both Supabase credentials are present."""
    url = os.getenv("SUPABASE_URL", "").strip().strip('"').strip("'")
    key = os.getenv("SUPABASE_KEY", "").strip().strip('"').strip("'")
    return bool(url) and bool(key) and "REPLACE_ME" not in url and "REPLACE_ME" not in key


class SupabaseVectorStore:
    """pgvector-backed RAG store with the same interface as RAGEngine."""

    def __init__(self):
        from supabase import create_client  # imported lazily so local Chroma users don't need it

        url = os.getenv("SUPABASE_URL", "").strip().strip('"').strip("'")
        key = os.getenv("SUPABASE_KEY", "").strip().strip('"').strip("'")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL / SUPABASE_KEY are not configured.")

        logger.info("Initializing Supabase vector store...")
        self.client = create_client(url, key)
        self._ef = DefaultEmbeddingFunction()

        # Fail fast with a clear message if the schema migration hasn't been run.
        try:
            self.client.table(TABLE_NAME).select("id").limit(1).execute()
        except Exception as e:
            raise RuntimeError(
                f"Supabase table '{TABLE_NAME}' is not reachable. "
                f"Run supabase_schema.sql in the Supabase SQL editor first. ({e})"
            ) from e

        logger.info("Supabase vector store ready. %d chunks stored.", self.get_document_count())

    # ── Embedding ───────────────────────────────────────────────────────────
    def _embed(self, texts: list[str]) -> list[list[float]]:
        # DefaultEmbeddingFunction returns numpy arrays — convert to plain lists
        # so the Supabase JSON client can serialise them.
        return [list(map(float, vec)) for vec in self._ef(texts)]

    # ── Ingestion ───────────────────────────────────────────────────────────
    def ingest_bytes(self, file_bytes: bytes, filename: str) -> int:
        """Ingest a PDF/TXT file. Returns the number of chunks added."""
        logger.info("Ingesting '%s' into Supabase...", filename)
        text = rag_common.extract_text(file_bytes, filename)
        if not text.strip():
            logger.warning("No text extracted from '%s'", filename)
            return 0

        chunks = rag_common.chunk_text(text, source=filename)
        if not chunks:
            return 0

        embeddings = self._embed([c["text"] for c in chunks])
        rows = [
            {
                "id": c["id"],
                "content": c["text"],
                "source": c["source"],
                "chunk_index": c["chunk_index"],
                "embedding": emb,
            }
            for c, emb in zip(chunks, embeddings)
        ]

        # upsert so re-uploading the same file doesn't create duplicates
        self.client.table(TABLE_NAME).upsert(rows).execute()
        logger.info("Ingested %d chunks from '%s' into Supabase.", len(rows), filename)
        return len(rows)

    # ── Retrieval ───────────────────────────────────────────────────────────
    def retrieve(self, query: str, k: int = rag_common.TOP_K) -> list[dict]:
        """Return the k most relevant chunks via the match_documents RPC."""
        if self.get_document_count() == 0:
            return []
        try:
            query_embedding = self._embed([query])[0]
            resp = self.client.rpc(
                MATCH_RPC,
                {"query_embedding": query_embedding, "match_count": k},
            ).execute()
            rows = resp.data or []
            chunks = [
                {
                    "content": r.get("content", ""),
                    "source": r.get("source", "unknown") or "unknown",
                    "similarity": round(float(r.get("similarity", 0.0)), 3),
                }
                for r in rows
                if r.get("content")
            ]
            logger.info("Supabase returned %d chunks for query.", len(chunks))
            return chunks
        except Exception as e:
            logger.error("Supabase retrieve failed: %s", e, exc_info=True)
            return []

    def get_context_string(self, query: str, k: int = rag_common.TOP_K) -> str:
        chunks = self.retrieve(query, k)
        if not chunks:
            return ""
        parts = [
            f"[Document {i} — Source: {c['source']} (relevance: {c['similarity']})]:\n{c['content']}"
            for i, c in enumerate(chunks, 1)
        ]
        return "\n\n---\n\n".join(parts)

    # ── Stats / Management ──────────────────────────────────────────────────
    def get_document_count(self) -> int:
        try:
            resp = self.client.table(TABLE_NAME).select("id", count="exact").execute()
            return resp.count or 0
        except Exception as e:
            logger.warning("Supabase count failed: %s", e)
            return 0

    def get_sources(self) -> list[str]:
        try:
            resp = self.client.table(TABLE_NAME).select("source").execute()
            return sorted({r["source"] for r in (resp.data or []) if r.get("source")})
        except Exception as e:
            logger.warning("Supabase get_sources failed: %s", e)
            return []

    def delete_source(self, source: str) -> None:
        """Remove every chunk belonging to a single uploaded file."""
        try:
            self.client.table(TABLE_NAME).delete().eq("source", source).execute()
            logger.info("Deleted source '%s' from Supabase.", source)
        except Exception as e:
            logger.error("Supabase delete_source failed: %s", e)

    def get_debug_info(self) -> dict:
        count = self.get_document_count()
        info = {
            "backend": "supabase",
            "count": count,
            "sources": self.get_sources(),
            "status": "ok" if count else "empty",
        }
        return {"supabase": info, "total_count": count}

    def clear(self) -> None:
        try:
            # delete all rows (neq on a never-empty column matches everything)
            self.client.table(TABLE_NAME).delete().neq("id", "").execute()
            logger.info("Supabase vector store cleared.")
        except Exception as e:
            logger.error("Supabase clear failed: %s", e)
