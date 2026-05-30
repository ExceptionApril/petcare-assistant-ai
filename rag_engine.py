"""
RAG Engine — ChromaDB + built-in ONNX embeddings (no Ollama required).
Works locally and on Streamlit Cloud without external embedding services.
"""

import os
import logging
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

import rag_common

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
CHUNK_SIZE      = rag_common.CHUNK_SIZE
CHUNK_OVERLAP   = rag_common.CHUNK_OVERLAP
TOP_K           = rag_common.TOP_K


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
        
        # In-memory backup storage (for Streamlit Cloud reliability)
        self._memory_store = {}  # format: {chunk_id: {"text": ..., "source": ..., "embedding": ...}}
        self._sources = set()

        try:
            self.chroma = chromadb.PersistentClient(path=CHROMA_PATH)
        except Exception as e:
            logger.warning("ChromaDB init error, resetting store: %s", e)
            import shutil
            if os.path.exists(CHROMA_PATH):
                shutil.rmtree(CHROMA_PATH)
            self.chroma = chromadb.PersistentClient(path=CHROMA_PATH)

        self.collection = self._get_or_create_collection()
        logger.info("RAG Engine ready. ChromaDB: %d chunks in store.", self.collection.count())

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
        text = rag_common.extract_text(file_bytes, filename)
        if not text.strip():
            logger.warning("No text extracted from '%s'", filename)
            return 0
        return self._ingest_text(text, source=filename)

    def _ingest_text(self, text: str, source: str) -> int:
        chunks = rag_common.chunk_text(text, source)
        if not chunks:
            return 0
        logger.info("Embedding %d chunks for '%s'...", len(chunks), source)
        
        # Store in ChromaDB (primary)
        try:
            self.collection.upsert(
                ids=[c["id"] for c in chunks],
                documents=[c["text"] for c in chunks],
                metadatas=[{"source": c["source"], "chunk_index": c["chunk_index"]} for c in chunks],
            )
        except Exception as e:
            logger.warning(f"ChromaDB upsert failed: {e} — falling back to memory-only")
        
        # ALSO store in memory (backup for Streamlit Cloud)
        for chunk in chunks:
            try:
                # Pre-compute embedding for memory storage
                embedding = self._ef([chunk["text"]])[0]
                self._memory_store[chunk["id"]] = {
                    "text": chunk["text"],
                    "source": chunk["source"],
                    "embedding": embedding,
                    "chunk_index": chunk["chunk_index"]
                }
                self._sources.add(chunk["source"])
            except Exception as e:
                logger.warning(f"Failed to embed chunk for memory: {e}")
        
        logger.info(f"Ingested {len(chunks)} chunks from '{source}'. Total: ChromaDB={self.collection.count()}, Memory={len(self._memory_store)}")
        return len(chunks)

    # ── Retrieval ──────────────────────────────────────────────────────────────

    def retrieve(self, query: str, k: int = TOP_K) -> list:
        """Return the k most relevant chunks. Try ChromaDB first, fall back to memory."""
        doc_count = self.collection.count()
        memory_count = len(self._memory_store)
        total_docs = max(doc_count, memory_count)
        
        if total_docs == 0:
            logger.debug("No documents in collection or memory")
            return []
        
        logger.info(f"Retrieve: '{query[:80]}...' (k={k}, ChromaDB={doc_count}, Memory={memory_count})")
        
        # Try ChromaDB first
        if doc_count > 0:
            try:
                n = min(k, doc_count)
                results = self.collection.query(
                    query_texts=[query],
                    n_results=n,
                    include=["documents", "metadatas", "distances"],
                )
                
                if results["documents"] and results["documents"][0]:
                    doc_results = results["documents"][0]
                    meta_results = results["metadatas"][0]
                    dist_results = results["distances"][0]
                    
                    chunks = []
                    for doc, meta, dist in zip(doc_results, meta_results, dist_results):
                        if doc and doc.strip():
                            chunk = {
                                "content": doc,
                                "source": meta.get("source", "unknown") if meta else "unknown",
                                "similarity": round(1 - dist, 3),
                            }
                            chunks.append(chunk)
                    
                    if chunks:
                        logger.info(f"ChromaDB returned {len(chunks)} chunks")
                        return chunks
                    else:
                        logger.debug("ChromaDB returned empty results")
                else:
                    logger.warning(f"ChromaDB query returned 0 results despite {doc_count} docs")
            except Exception as e:
                logger.warning(f"ChromaDB query failed: {e} — trying memory fallback")
        
        # Fallback: use in-memory search
        if memory_count > 0:
            logger.info(f"Falling back to in-memory search ({memory_count} chunks)")
            try:
                # Embed the query
                query_embedding = self._ef([query])[0]
                
                # Compute similarity to all stored chunks
                similarities = []
                for chunk_id, chunk_data in self._memory_store.items():
                    # Simple cosine similarity
                    embedding = chunk_data["embedding"]
                    if embedding:
                        # Dot product
                        dot_product = sum(a * b for a, b in zip(query_embedding, embedding))
                        # Norms
                        norm_q = sum(x ** 2 for x in query_embedding) ** 0.5
                        norm_e = sum(x ** 2 for x in embedding) ** 0.5
                        if norm_q > 0 and norm_e > 0:
                            sim = dot_product / (norm_q * norm_e)
                        else:
                            sim = 0
                        similarities.append((chunk_id, sim))
                
                # Sort by similarity and take top-k
                similarities.sort(key=lambda x: x[1], reverse=True)
                top_k = similarities[:k]
                
                chunks = []
                for chunk_id, sim in top_k:
                    chunk_data = self._memory_store[chunk_id]
                    chunks.append({
                        "content": chunk_data["text"],
                        "source": chunk_data["source"],
                        "similarity": round((sim + 1) / 2, 3),  # cosine [-1,1] → [0,1]
                    })
                
                logger.info(f"Memory search returned {len(chunks)} chunks with similarities: {[c['similarity'] for c in chunks]}")
                return chunks
            except Exception as e:
                logger.error(f"Memory search failed: {e}", exc_info=True)
        
        logger.warning(f"No results from ChromaDB or memory despite {total_docs} docs")
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
        """Return total document count from ChromaDB + memory."""
        try:
            chroma_count = self.collection.count()
        except Exception:
            chroma_count = 0
        
        memory_count = len(self._memory_store)
        total = max(chroma_count, memory_count)  # Use max (same docs in both)
        return total

    def get_sources(self) -> list:
        """Return sorted list of sources from both ChromaDB and memory."""
        sources = set()
        
        # From ChromaDB
        try:
            if self.collection.count() > 0:
                results = self.collection.get(include=["metadatas"])
                sources.update({m["source"] for m in results["metadatas"]})
        except Exception:
            pass
        
        # From memory
        sources.update(self._sources)
        
        return sorted(list(sources))

    def get_debug_info(self) -> dict:
        """Return diagnostic info about what's stored (ChromaDB + Memory)."""
        chroma_info = {"count": 0, "chunks": [], "status": "empty"}
        try:
            count = self.collection.count()
            if count > 0:
                results = self.collection.get(limit=3, include=["documents", "metadatas"])
                chunks_info = []
                for doc, meta in zip(results["documents"], results["metadatas"]):
                    chunks_info.append({
                        "source": meta.get("source", "unknown"),
                        "content_len": len(doc) if doc else 0,
                        "content_preview": (doc[:100] if doc else "")
                    })
                chroma_info = {
                    "count": count,
                    "chunks": chunks_info,
                    "sources": sorted({m["source"] for m in results["metadatas"]}),
                    "status": "ok"
                }
        except Exception as e:
            chroma_info = {"status": "error", "error": str(e)}
        
        memory_info = {
            "count": len(self._memory_store),
            "sources": sorted(list(self._sources)),
            "status": "ok" if self._memory_store else "empty"
        }
        
        return {
            "chromadb": chroma_info,
            "memory": memory_info,
            "total_count": max(chroma_info.get("count", 0), memory_info.get("count", 0))
        }

    def delete_source(self, source: str) -> None:
        """Remove every chunk belonging to a single uploaded file."""
        try:
            self.collection.delete(where={"source": source})
        except Exception as e:
            logger.warning("Chroma delete_source failed: %s", e)
        # also drop from the in-memory backup
        for cid in [cid for cid, c in self._memory_store.items() if c.get("source") == source]:
            self._memory_store.pop(cid, None)
        self._sources.discard(source)
        logger.info("Deleted source '%s'.", source)

    def clear(self):
        try:
            self.chroma.delete_collection(COLLECTION_NAME)
            self.collection = self.chroma.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=self._ef,
            )
            # Also clear memory
            self._memory_store.clear()
            self._sources.clear()
            logger.info("Vector store and memory cache cleared.")
        except Exception as e:
            logger.error("Clear error: %s", e)


# ── Backend factory ─────────────────────────────────────────────────────────

def get_rag_engine():
    """
    Return the active RAG backend.

    Prefers Supabase pgvector (persistent across Streamlit Cloud restarts) when
    SUPABASE_URL / SUPABASE_KEY are configured; otherwise falls back to the
    local ChromaDB engine. Both expose the same method surface, so callers are
    backend-agnostic.
    """
    try:
        from supabase_store import is_supabase_configured, SupabaseVectorStore
        if is_supabase_configured():
            logger.info("RAG backend: Supabase (pgvector)")
            return SupabaseVectorStore()
    except Exception as e:
        logger.warning("Supabase backend unavailable (%s) — falling back to local ChromaDB.", e)

    logger.info("RAG backend: local ChromaDB")
    return RAGEngine()
