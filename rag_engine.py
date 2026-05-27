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
import stat
import shutil
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

logger = logging.getLogger(__name__)

CHROMA_PATH     = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = "petcare_docs"
CHUNK_SIZE      = 500
CHUNK_OVERLAP   = 50
TOP_K           = 3
# ONNX MiniLM with L2 distance on normalized vectors → distance ∈ [0, 2].
# similarity = 1 - distance.  Empirically: relevant chunks land >= 0.15-0.20,
# random/irrelevant queries score < 0.10.  Set the floor accordingly so
# the assistant can retrieve relevant documents while filtering truly irrelevant ones.
MIN_SIMILARITY  = 0.15


def _ensure_writable(path: str) -> bool:
    """Ensure directory exists and is writable. Returns True if successful."""
    try:
        os.makedirs(path, exist_ok=True)
        # On Windows, remove read-only attribute recursively
        for root, dirs, files in os.walk(path):
            for d in dirs:
                dir_path = os.path.join(root, d)
                try:
                    os.chmod(dir_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
                except Exception:
                    pass
            for f in files:
                file_path = os.path.join(root, f)
                try:
                    os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
                except Exception:
                    pass
        # Test write capability
        test_file = os.path.join(path, ".write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except Exception as e:
        logger.error("Failed to ensure writable path %s: %s", path, e)
        return False


class RAGEngine:
    """
    Retrieval-Augmented Generation engine.

    Flow:
      ingest_bytes(file) → chunk → embed (ONNX MiniLM) → store (ChromaDB)
      retrieve(query)    → embed query → similarity search → return chunks
    """

    def __init__(self):
        logger.info("Initializing RAG Engine (ONNX embeddings)...")
        self._ef = DefaultEmbeddingFunction()
        self._is_healthy = False
        self.chroma = None
        self.collection = None

        # Ensure the path is writable before initializing ChromaDB
        if not _ensure_writable(CHROMA_PATH):
            logger.error("Cannot create writable ChromaDB path at %s. RAG will be disabled.", CHROMA_PATH)
            return

        try:
            self.chroma = chromadb.PersistentClient(path=CHROMA_PATH)
            self._is_healthy = True
        except Exception as e:
            logger.warning("ChromaDB init error, attempting reset: %s", e)
            try:
                # Remove read-only attributes before deletion
                if os.path.exists(CHROMA_PATH):
                    _ensure_writable(CHROMA_PATH)
                    shutil.rmtree(CHROMA_PATH)
                os.makedirs(CHROMA_PATH, exist_ok=True)
                self.chroma = chromadb.PersistentClient(path=CHROMA_PATH)
                self._is_healthy = True
            except Exception as e2:
                logger.error("ChromaDB reset failed: %s. RAG will be disabled.", e2)
                return

        try:
            self.collection = self._get_or_create_collection()
            logger.info("RAG Engine ready. %d chunks in store.", self.collection.count())
        except Exception as e:
            logger.error("Failed to initialize collection: %s. RAG will be disabled.", e)
            self.chroma = None
            self.collection = None

    # ── Collection management ──────────────────────────────────────────────────

    def _get_or_create_collection(self):
        """Get/create collection, clearing it if stored embeddings have wrong dim."""
        if not self.chroma:
            logger.error("ChromaDB client not initialized")
            return None
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
            try:
                return self.chroma.create_collection(
                    name=COLLECTION_NAME,
                    embedding_function=self._ef,
                )
            except Exception as e2:
                logger.error("Failed to create collection: %s", e2)
                return None

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
        if not self.collection:
            logger.warning("RAG collection not available. Documents cannot be ingested.")
            return 0
        chunks = self._chunk_text(text, source)
        if not chunks:
            return 0
        logger.info("Embedding %d chunks for '%s'...", len(chunks), source)
        try:
            # Upsert without pre-computed embeddings — collection EF handles them
            self.collection.upsert(
                ids=[c["id"] for c in chunks],
                documents=[c["text"] for c in chunks],
                metadatas=[{"source": c["source"], "chunk_index": c["chunk_index"]} for c in chunks],
            )
            logger.info("Ingested %d chunks from '%s'. Total: %d", len(chunks), source, self.collection.count())
            return len(chunks)
        except Exception as e:
            if "readonly" in str(e).lower() or "permission" in str(e).lower():
                logger.error("Database is read-only, attempting recovery: %s", e)
                # Try to fix permissions and reinitialize
                try:
                    _ensure_writable(CHROMA_PATH)
                    # Reinitialize the collection
                    self.collection = self._get_or_create_collection()
                    if not self.collection:
                        logger.error("Could not reinitialize collection after permission fix")
                        return 0
                    # Retry the upsert
                    self.collection.upsert(
                        ids=[c["id"] for c in chunks],
                        documents=[c["text"] for c in chunks],
                        metadatas=[{"source": c["source"], "chunk_index": c["chunk_index"]} for c in chunks],
                    )
                    logger.info("Recovery successful. Ingested %d chunks from '%s'.", len(chunks), source)
                    return len(chunks)
                except Exception as e2:
                    logger.error("Recovery failed: %s", e2)
                    return 0
            else:
                logger.error("Ingestion error: %s", e)
                return 0

    # ── Retrieval ──────────────────────────────────────────────────────────────

    def retrieve(self, query: str, k: int = TOP_K, min_similarity: float = MIN_SIMILARITY) -> list:
        """Return chunks for the query, filtered by similarity threshold.

        Chunks below ``min_similarity`` are dropped so off-topic questions
        (e.g. asking to recall a name) don't get cat.pdf appended as a
        "source".  Pass ``min_similarity=0`` to disable filtering.
        """
        if not self.collection:
            logger.warning("RAG collection not available")
            return []
        if self.collection.count() == 0:
            return []
        try:
            n = min(k, self.collection.count())
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
                if similarity < min_similarity:
                    continue
                chunks.append({
                    "content": doc,
                    "source": meta.get("source", ""),
                    "similarity": similarity,
                })
            return chunks
        except Exception as e:
            if "readonly" in str(e).lower() or "permission" in str(e).lower():
                logger.error("Database read-only during retrieval, attempting recovery: %s", e)
                try:
                    _ensure_writable(CHROMA_PATH)
                    # Retry the query
                    n = min(k, self.collection.count())
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
                        if similarity < min_similarity:
                            continue
                        chunks.append({
                            "content": doc,
                            "source": meta.get("source", ""),
                            "similarity": similarity,
                        })
                    return chunks
                except Exception as e2:
                    logger.error("Retrieval recovery failed: %s", e2)
                    return []
            else:
                logger.error("Retrieval error: %s", e)
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

    def is_healthy(self) -> bool:
        """Check if the RAG engine is healthy and can perform operations."""
        if not self.collection or not self.chroma:
            return False
        try:
            # Test a simple read operation
            count = self.collection.count()
            return True
        except Exception as e:
            logger.warning("RAG health check failed: %s", e)
            return False

    def clear(self):
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
        except Exception as e:
            logger.error("Clear error: %s", e)
