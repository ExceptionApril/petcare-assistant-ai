"""
RAG Engine — ChromaDB + built-in ONNX embeddings (no Ollama required).
Works locally and on Streamlit Cloud without external embedding services.
"""

import os
import io
import re
import hashlib
import logging
import shutil

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

logger = logging.getLogger(__name__)


def _resolve_chroma_path() -> str:
    """Pick a writable path for ChromaDB storage.

    On Streamlit Cloud the repo is mounted read-only under /mount/src/…,
    so we MUST use /tmp which is the only writable location.
    Locally, ./chroma_db (or CHROMA_DB_PATH env var) works fine.
    """
    explicit = os.getenv("CHROMA_DB_PATH", "").strip()
    if explicit:
        return explicit

    # Detect Streamlit Cloud: the app runs from /mount/src/<repo>
    if os.path.exists("/mount/src"):
        path = "/tmp/chroma_db"
        logger.info("Streamlit Cloud detected — using writable path: %s", path)
        return path

    return "./chroma_db"


CHROMA_PATH     = _resolve_chroma_path()
COLLECTION_NAME = "petcare_docs"
CHUNK_SIZE      = 500
CHUNK_OVERLAP   = 50
TOP_K           = 3
MIN_SIMILARITY  = 0.10   # lowered so more relevant chunks pass through


class RAGEngine:
    """
    Retrieval-Augmented Generation engine.

    Flow:
      ingest_bytes(file) → chunk → embed (ONNX MiniLM) → store (ChromaDB)
      retrieve(query)    → embed query → similarity search → return chunks
    """

    def __init__(self):
        logger.info("Initializing RAG Engine (ONNX embeddings) at %s ...", CHROMA_PATH)
        self._ef = DefaultEmbeddingFunction()
        self.chroma = None
        self.collection = None

        # Ensure directory exists
        try:
            os.makedirs(CHROMA_PATH, exist_ok=True)
        except Exception as exc:
            logger.error("Cannot create ChromaDB directory %s: %s", CHROMA_PATH, exc)
            return

        # Write test — if this fails, ChromaDB will also fail
        try:
            test_file = os.path.join(CHROMA_PATH, ".write_test")
            with open(test_file, "w") as fh:
                fh.write("ok")
            os.remove(test_file)
        except Exception as exc:
            logger.error("ChromaDB path %s is NOT writable: %s — RAG disabled.", CHROMA_PATH, exc)
            return

        # Initialise ChromaDB PersistentClient
        try:
            self.chroma = chromadb.PersistentClient(path=CHROMA_PATH)
        except Exception as exc:
            logger.warning("ChromaDB init error (%s), nuking directory and retrying…", exc)
            try:
                shutil.rmtree(CHROMA_PATH, ignore_errors=True)
                os.makedirs(CHROMA_PATH, exist_ok=True)
                self.chroma = chromadb.PersistentClient(path=CHROMA_PATH)
            except Exception as exc2:
                logger.error("ChromaDB reset also failed: %s — RAG disabled.", exc2)
                return

        # Get or create the collection
        try:
            self.collection = self._get_or_create_collection()
            count = self.collection.count() if self.collection else 0
            logger.info("RAG Engine ready. %d chunks in store.", count)
        except Exception as exc:
            logger.error("Collection init failed: %s — RAG disabled.", exc)
            self.chroma = None
            self.collection = None

    # ── Collection management ──────────────────────────────────────────────────

    def _get_or_create_collection(self):
        """Get/create collection, clearing it if stored embeddings have wrong dim."""
        if not self.chroma:
            return None
        try:
            col = self.chroma.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=self._ef,
            )
            # Detect dim mismatch (e.g. old Ollama 768-dim vs ONNX 384-dim)
            if col.count() > 0:
                sample = col.get(limit=1, include=["embeddings"])
                raw = sample.get("embeddings")
                stored_dim = len(raw[0]) if raw and len(raw) > 0 else 0
                expected_dim = len(self._ef(["probe"])[0])
                if stored_dim and stored_dim != expected_dim:
                    logger.warning("Dim mismatch (%d vs %d) — clearing.", stored_dim, expected_dim)
                    self.chroma.delete_collection(COLLECTION_NAME)
                    col = self.chroma.create_collection(name=COLLECTION_NAME, embedding_function=self._ef)
            return col
        except Exception as exc:
            logger.warning("Collection error (%s) — recreating.", exc)
            try:
                self.chroma.delete_collection(COLLECTION_NAME)
            except Exception:
                pass
            try:
                return self.chroma.create_collection(name=COLLECTION_NAME, embedding_function=self._ef)
            except Exception as exc2:
                logger.error("Failed to create collection: %s", exc2)
                return None

    # ── Ingestion ──────────────────────────────────────────────────────────────

    def ingest_bytes(self, file_bytes: bytes, filename: str) -> int:
        """Ingest a PDF or TXT file. Returns the number of chunks added."""
        logger.info("Ingesting '%s' (%d bytes)…", filename, len(file_bytes))
        text = (
            self._extract_pdf(file_bytes)
            if filename.lower().endswith(".pdf")
            else file_bytes.decode("utf-8", errors="ignore")
        )
        if not text.strip():
            logger.warning("No text extracted from '%s'", filename)
            return 0
        logger.info("Extracted %d characters from '%s'", len(text), filename)
        return self._ingest_text(text, source=filename)

    def _extract_pdf(self, file_bytes: bytes) -> str:
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            pages = []
            for i, p in enumerate(reader.pages):
                text = p.extract_text() or ""
                text = text.replace("\r\n", "\n").replace("\r", "\n")
                text = re.sub(r"[ \t]+", " ", text)
                text = re.sub(r"\n+", " ", text)
                text = re.sub(r" {2,}", " ", text)
                text = text.strip()
                if text:
                    pages.append(f"[Page {i+1}] {text}")
            return "\n\n".join(pages)
        except Exception as exc:
            logger.error("PDF extraction error: %s", exc)
            return file_bytes.decode("utf-8", errors="ignore")

    def _chunk_text(self, text: str, source: str) -> list:
        chunks = []
        start, idx = 0, 0
        while start < len(text):
            chunk_text = text[start : start + CHUNK_SIZE].strip()
            if chunk_text:
                chunk_id = hashlib.md5(f"{source}_{idx}_{chunk_text[:50]}".encode()).hexdigest()
                chunks.append({"id": chunk_id, "text": chunk_text, "source": source, "chunk_index": idx})
                idx += 1
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    def _ingest_text(self, text: str, source: str) -> int:
        if not self.collection:
            logger.warning("RAG collection not available — cannot ingest.")
            return 0
        chunks = self._chunk_text(text, source)
        if not chunks:
            return 0
        logger.info("Upserting %d chunks for '%s'…", len(chunks), source)
        try:
            self.collection.upsert(
                ids=[c["id"] for c in chunks],
                documents=[c["text"] for c in chunks],
                metadatas=[{"source": c["source"], "chunk_index": c["chunk_index"]} for c in chunks],
            )
            total = self.collection.count()
            logger.info("Ingested %d chunks from '%s'. Total in store: %d", len(chunks), source, total)
            return len(chunks)
        except Exception as exc:
            logger.error("Ingestion error for '%s': %s", source, exc, exc_info=True)
            return 0

    # ── Retrieval ──────────────────────────────────────────────────────────────

    def retrieve(self, query: str, k: int = TOP_K, min_similarity: float = MIN_SIMILARITY) -> list:
        """Return top-k chunks for the query, filtered by similarity threshold."""
        if not self.collection:
            logger.warning("RAG collection not available")
            return []
        count = self.collection.count()
        if count == 0:
            logger.info("RAG store is empty — nothing to retrieve.")
            return []
        try:
            n = min(k, count)
            results = self.collection.query(
                query_texts=[query],
                n_results=n,
                include=["documents", "metadatas", "distances"],
            )
            chunks = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                similarity = round(1 - dist, 3)
                logger.debug("Chunk from '%s' similarity=%.3f", meta.get("source", "?"), similarity)
                if similarity < min_similarity:
                    continue
                chunks.append({
                    "content": doc,
                    "source": meta.get("source", ""),
                    "similarity": similarity,
                })
            logger.info("Retrieved %d chunks (of %d candidates) for query '%s'", len(chunks), n, query[:80])
            return chunks
        except Exception as exc:
            logger.error("Retrieval error: %s", exc, exc_info=True)
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
        if not self.collection:
            return 0
        try:
            return self.collection.count()
        except Exception:
            return 0

    def get_sources(self) -> list:
        if not self.collection:
            return []
        try:
            if self.collection.count() == 0:
                return []
            results = self.collection.get(include=["metadatas"])
            return sorted({m["source"] for m in results["metadatas"]})
        except Exception:
            return []

    def verify_document(self, source: str) -> bool:
        """Verify that a document with the given source is in the database."""
        if not self.collection:
            return False
        try:
            results = self.collection.get(include=["metadatas"])
            sources = {m["source"] for m in results["metadatas"]}
            is_present = source in sources
            logger.info("Document '%s' present: %s. Sources: %s", source, is_present, sources)
            return is_present
        except Exception as exc:
            logger.error("Verification error: %s", exc)
            return False

    def is_healthy(self) -> bool:
        """Check if the RAG engine is healthy."""
        if not self.collection or not self.chroma:
            return False
        try:
            self.collection.count()
            return True
        except Exception as exc:
            logger.warning("RAG health check failed: %s", exc)
            return False

    def clear(self):
        """Delete all documents from the vector store."""
        if not self.chroma or not self.collection:
            logger.warning("RAG not initialized, cannot clear")
            return
        try:
            self.chroma.delete_collection(COLLECTION_NAME)
            self.collection = self.chroma.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=self._ef,
            )
            logger.info("Vector store cleared.")
        except Exception as exc:
            logger.error("Clear error: %s", exc)
