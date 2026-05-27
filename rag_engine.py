"""
RAG Engine — ChromaDB + built-in ONNX embeddings (no Ollama required).
Works locally and on Streamlit Cloud without external embedding services.
"""

import os
import io
import re
import hashlib
import logging
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

logger = logging.getLogger(__name__)

# Auto-detect path: use writable location for the environment
def _get_chroma_path():
    """Get appropriate ChromaDB path for local or Streamlit Cloud."""
    explicit = os.getenv("CHROMA_DB_PATH", "").strip()
    if explicit:
        return explicit
    
    # Streamlit Cloud detection - use /tmp which is writable during session
    if os.path.exists("/mount/src"):
        return "/tmp/chroma_db"
    
    # Local development: use ./chroma_db
    return "./chroma_db"

CHROMA_PATH     = _get_chroma_path()
COLLECTION_NAME = "petcare_docs"
CHUNK_SIZE      = 500
CHUNK_OVERLAP   = 50
TOP_K           = 3


class RAGEngine:
    """
    Retrieval-Augmented Generation engine.

    Flow:
      ingest_bytes(file) → chunk → embed (ONNX MiniLM) → store (ChromaDB)
      retrieve(query)    → embed query → similarity search → return chunks
    """

    def __init__(self):
        logger.info(f"Initializing RAG Engine (ONNX embeddings)... [path: {CHROMA_PATH}]")
        self._ef = DefaultEmbeddingFunction()

        try:
            self.chroma = chromadb.PersistentClient(path=CHROMA_PATH)
        except Exception as e:
            logger.warning("ChromaDB init error, resetting store: %s", e)
            import shutil
            if os.path.exists(CHROMA_PATH):
                shutil.rmtree(CHROMA_PATH)
            self.chroma = chromadb.PersistentClient(path=CHROMA_PATH)

        self.collection = self._get_or_create_collection()
        logger.info("RAG Engine ready. %d chunks in store.", self.collection.count())

    # ── Collection management ──────────────────────────────────────────────────

    def _get_or_create_collection(self):
        """Get/create collection, clearing it if stored embeddings have wrong dim."""
        try:
            col = self.chroma.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=self._ef,
            )
            # Detect dim mismatch with existing data (e.g. old Ollama 768-dim vectors)
            if col.count() > 0:
                sample = col.get(limit=1, include=["embeddings"])
                raw_embeds = sample.get("embeddings")
                stored_dim = int(len(raw_embeds[0])) if raw_embeds is not None and len(raw_embeds) > 0 else 0
                expected_dim = len(self._ef(["probe"])[0])
                if stored_dim and stored_dim != expected_dim:
                    logger.warning(
                        "Embedding dim mismatch (%d vs %d) — clearing collection.",
                        stored_dim, expected_dim,
                    )
                    self.chroma.delete_collection(COLLECTION_NAME)
                    col = self.chroma.create_collection(
                        name=COLLECTION_NAME,
                        embedding_function=self._ef,
                    )
            return col
        except Exception as e:
            logger.warning("Collection error (%s) — recreating.", e)
            try:
                self.chroma.delete_collection(COLLECTION_NAME)
            except Exception:
                pass
            return self.chroma.create_collection(
                name=COLLECTION_NAME,
                embedding_function=self._ef,
            )

    # ── Ingestion ──────────────────────────────────────────────────────────────

    def ingest_bytes(self, file_bytes: bytes, filename: str) -> int:
        """Ingest a PDF or TXT file. Returns the number of chunks added."""
        logger.info("Ingesting '%s'...", filename)
        text = (
            self._extract_pdf(file_bytes)
            if filename.lower().endswith(".pdf")
            else file_bytes.decode("utf-8", errors="ignore")
        )
        if not text.strip():
            logger.warning("No text extracted from '%s'", filename)
            return 0
        return self._ingest_text(text, source=filename)

    def _extract_pdf(self, file_bytes: bytes) -> str:
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            pages = []
            for i, p in enumerate(reader.pages):
                text = p.extract_text() or ""
                text = text.replace("\r\n", "\n").replace("\r", "\n")
                text = re.sub(r"[ \t]+", " ", text)   # collapse horizontal whitespace
                text = re.sub(r"\n+", " ", text)       # all newlines → space (fix word-per-line PDFs)
                text = re.sub(r" {2,}", " ", text)     # collapse double spaces
                text = text.strip()
                if text:
                    pages.append(f"[Page {i+1}] {text}")
            return "\n\n".join(pages)
        except Exception as e:
            logger.error("PDF extraction error: %s", e)
            return file_bytes.decode("utf-8", errors="ignore")

    def _chunk_text(self, text: str, source: str) -> list:
        chunks = []
        start, idx = 0, 0
        while start < len(text):
            chunk_text = text[start : start + CHUNK_SIZE].strip()
            if chunk_text:
                chunk_id = hashlib.md5(
                    f"{source}_{idx}_{chunk_text[:50]}".encode()
                ).hexdigest()
                chunks.append({"id": chunk_id, "text": chunk_text, "source": source, "chunk_index": idx})
                idx += 1
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    def _ingest_text(self, text: str, source: str) -> int:
        chunks = self._chunk_text(text, source)
        if not chunks:
            return 0
        logger.info("Embedding %d chunks for '%s'...", len(chunks), source)
        # Upsert without pre-computed embeddings — collection EF handles them
        self.collection.upsert(
            ids=[c["id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=[{"source": c["source"], "chunk_index": c["chunk_index"]} for c in chunks],
        )
        logger.info("Ingested %d chunks from '%s'. Total: %d", len(chunks), source, self.collection.count())
        return len(chunks)

    # ── Retrieval ──────────────────────────────────────────────────────────────

    def retrieve(self, query: str, k: int = TOP_K) -> list:
        """Return the k most relevant chunks for the query."""
        doc_count = self.collection.count()
        if doc_count == 0:
            logger.debug("No documents in collection")
            return []
        
        try:
            n = min(k, doc_count)
            logger.info(f"Querying: '{query[:80]}...' (k={n}, docs={doc_count})")
            
            results = self.collection.query(
                query_texts=[query],
                n_results=n,
                include=["documents", "metadatas", "distances"],
            )
            
            # Detailed logging of what we got back
            logger.debug(f"Query response structure: documents={bool(results['documents'])}, "
                        f"metadatas={bool(results['metadatas'])}, distances={bool(results['distances'])}")
            
            # Check if we got results
            if not results["documents"] or not results["documents"][0]:
                logger.warning(f"Query returned 0 results despite {doc_count} docs stored")
                logger.debug(f"Full response: {results}")
                return []
            
            doc_results = results["documents"][0]
            meta_results = results["metadatas"][0]
            dist_results = results["distances"][0]
            
            logger.info(f"Query got {len(doc_results)} results")
            
            chunks = []
            for i, (doc, meta, dist) in enumerate(zip(doc_results, meta_results, dist_results)):
                if not doc or not doc.strip():
                    logger.warning(f"Result {i}: empty document")
                    continue
                chunk = {
                    "content": doc,
                    "source": meta.get("source", "unknown") if meta else "unknown",
                    "similarity": round(1 - dist, 3),
                }
                chunks.append(chunk)
                if i < 3:  # Log first 3
                    logger.debug(f"  Result {i}: source={chunk['source']}, similarity={chunk['similarity']}, len={len(doc)}")
            
            logger.info(f"Retrieved {len(chunks)} valid chunks with similarities: {[c['similarity'] for c in chunks]}")
            return chunks
        except Exception as e:
            logger.error(f"Retrieval error for query '{query[:50]}...': {e}", exc_info=True)
            return []

    def get_context_string(self, query: str, k: int = TOP_K) -> str:
        """Retrieve chunks and format them as a context string for the LLM."""
        chunks = self.retrieve(query, k)
        if not chunks:
            return ""
        parts = [
            f"[Document {i} — Source: {c['source']} (relevance: {c['similarity']})]:\n{c['content']}"
            for i, c in enumerate(chunks, 1)
        ]
        return "\n\n---\n\n".join(parts)

    # ── Stats / Management ─────────────────────────────────────────────────────

    def get_document_count(self) -> int:
        try:
            return self.collection.count()
        except Exception:
            return 0

    def get_sources(self) -> list:
        try:
            if self.collection.count() == 0:
                return []
            results = self.collection.get(include=["metadatas"])
            return sorted({m["source"] for m in results["metadatas"]})
        except Exception:
            return []

    def get_debug_info(self) -> dict:
        """Return diagnostic info about what's stored in the collection."""
        try:
            count = self.collection.count()
            if count == 0:
                return {"count": 0, "chunks": [], "status": "empty"}
            
            # Get first 3 chunks to inspect
            results = self.collection.get(limit=3, include=["documents", "metadatas"])
            chunks_info = []
            for doc, meta in zip(results["documents"], results["metadatas"]):
                chunks_info.append({
                    "source": meta.get("source", "unknown"),
                    "content_len": len(doc) if doc else 0,
                    "content_preview": (doc[:100] if doc else "")
                })
            
            return {
                "count": count,
                "chunks": chunks_info,
                "sources": sorted({m["source"] for m in results["metadatas"]}),
                "status": "ok"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def clear(self):
        try:
            self.chroma.delete_collection(COLLECTION_NAME)
            self.collection = self.chroma.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=self._ef,
            )
            logger.info("Vector store cleared.")
        except Exception as e:
            logger.error("Clear error: %s", e)
