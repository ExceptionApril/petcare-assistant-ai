"""
Shared RAG helpers — text extraction and chunking.

Used by BOTH the local ChromaDB engine (rag_engine.py) and the
Supabase pgvector store (supabase_store.py) so the chunking/embedding
contract stays identical no matter which backend is active.
"""

import io
import re
import hashlib
import logging

logger = logging.getLogger(__name__)

# Chunking parameters — kept here so both backends produce identical chunk IDs.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 3

# Embedding dimension for chromadb's DefaultEmbeddingFunction (all-MiniLM-L6-v2).
# The Supabase `documents.embedding` column and `match_documents()` RPC MUST use
# this same dimension.
EMBED_DIM = 384


def extract_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF, normalising the word-per-line spacing that
    many PDFs produce so chunks read as prose."""
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages = []
        for i, p in enumerate(reader.pages):
            text = p.extract_text() or ""
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            text = re.sub(r"[ \t]+", " ", text)   # collapse horizontal whitespace
            text = re.sub(r"\n+", " ", text)       # all newlines → space
            text = re.sub(r" {2,}", " ", text)     # collapse double spaces
            text = text.strip()
            if text:
                pages.append(f"[Page {i + 1}] {text}")
        return "\n\n".join(pages)
    except Exception as e:
        logger.error("PDF extraction error: %s", e)
        return file_bytes.decode("utf-8", errors="ignore")


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract text from an uploaded PDF or TXT file."""
    if filename.lower().endswith(".pdf"):
        return extract_pdf(file_bytes)
    return file_bytes.decode("utf-8", errors="ignore")


def chunk_text(text: str, source: str,
               chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Split text into overlapping chunks with stable, content-derived IDs."""
    chunks: list[dict] = []
    start, idx = 0, 0
    while start < len(text):
        body = text[start: start + chunk_size].strip()
        if body:
            chunk_id = hashlib.md5(
                f"{source}_{idx}_{body[:50]}".encode()
            ).hexdigest()
            chunks.append({
                "id": chunk_id,
                "text": body,
                "source": source,
                "chunk_index": idx,
            })
            idx += 1
        start += chunk_size - overlap
    return chunks
