"""
RAG Engine — uses Ollama (local) for embeddings + ChromaDB for vector storage.
No API keys needed for embeddings. Completely free and runs offline.
"""

import os
import io
import shutil
import hashlib
import requests
import logging
import chromadb

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL     = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
CHROMA_PATH     = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = "petcare_docs"
CHUNK_SIZE      = 500   # characters per chunk
CHUNK_OVERLAP   = 50    # character overlap between chunks
TOP_K           = 3     # number of chunks to retrieve


class RAGEngine:
    """
    Retrieval-Augmented Generation engine.
    
    Flow:
      ingest_bytes(file) → chunk → embed (Ollama) → store (ChromaDB)
      retrieve(query)    → embed query → similarity search → return chunks
    """

    def __init__(self):
        logger.info("Initializing RAG Engine with Ollama + ChromaDB...")
        
        # 1. Check Ollama is reachable
        self._check_ollama()
        
        # 2. Initialize ChromaDB persistent store (no settings to avoid conflicts)
        try:
            self.chroma = chromadb.PersistentClient(path=CHROMA_PATH)
        except Exception as e:
            logger.warning(f"ChromaDB init error, attempting recovery: {e}")
            # Remove corrupted database and retry
            import shutil
            if os.path.exists(CHROMA_PATH):
                shutil.rmtree(CHROMA_PATH)
            self.chroma = chromadb.PersistentClient(path=CHROMA_PATH)
        
        # 3. Get or create the collection (no metadata to avoid conflicts)
        self.collection = self.chroma.get_or_create_collection(
            name=COLLECTION_NAME
        )
        
        count = self.collection.count()
        logger.info(f"RAG Engine ready. Vector store has {count} chunks.")

    # ── Internal: Ollama check ──────────────────────────────────
    def _check_ollama(self):
        try:
            r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            if not any(EMBED_MODEL in m for m in models):
                logger.warning(f"'{EMBED_MODEL}' not found in Ollama. Pulling...")
                import subprocess
                subprocess.run(["ollama", "pull", EMBED_MODEL], check=True)
                logger.info(f"'{EMBED_MODEL}' pulled.")
            else:
                logger.info(f"Ollama running. Embedding model '{EMBED_MODEL}' ready.")
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Ollama is not running!\n"
                "   1. Open a new terminal\n"
                "   2. Run: ollama serve\n"
                "   3. Run: ollama pull nomic-embed-text\n"
                "   4. Then restart this app"
            )

    # ── Internal: Get embedding from Ollama ─────────────────────
    def _embed(self, text: str) -> list:
        """Call Ollama's local embedding API."""
        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
                timeout=30
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            # Return zero vector as fallback (768 dims for nomic-embed-text)
            return [0.0] * 768

    # ── Internal: Chunk text ────────────────────────────────────
    def _chunk_text(self, text: str, source: str) -> list:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = start + CHUNK_SIZE
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                # Create a stable unique ID based on content hash
                chunk_id = hashlib.md5(
                    f"{source}_{chunk_index}_{chunk_text[:50]}".encode()
                ).hexdigest()
                
                chunks.append({
                    "id": chunk_id,
                    "text": chunk_text,
                    "source": source,
                    "chunk_index": chunk_index
                })
                chunk_index += 1
            
            start += CHUNK_SIZE - CHUNK_OVERLAP
        
        return chunks

    # ── Public: Ingest from raw bytes (PDF or TXT) ───────────────
    def ingest_bytes(self, file_bytes: bytes, filename: str) -> int:
        """
        Ingest a file into the vector store.
        Supports PDF and TXT files.
        Returns number of chunks added.
        """
        logger.info(f"Ingesting '{filename}'...")
        
        # Extract text
        if filename.lower().endswith(".pdf"):
            text = self._extract_pdf(file_bytes)
        else:
            text = file_bytes.decode("utf-8", errors="ignore")
        
        if not text.strip():
            logger.warning(f"No text extracted from '{filename}'")
            return 0
        
        return self._ingest_text(text, source=filename)

    def _extract_pdf(self, file_bytes: bytes) -> str:
        """Extract text from PDF bytes."""
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            pages = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                pages.append(f"[Page {i+1}]\n{page_text}")
            return "\n\n".join(pages)
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return file_bytes.decode("utf-8", errors="ignore")

    def _ingest_text(self, text: str, source: str) -> int:
        """Chunk, embed, and store text. Returns chunk count."""
        chunks = self._chunk_text(text, source)
        
        if not chunks:
            return 0
        
        logger.info(f"Embedding {len(chunks)} chunks... (this may take a moment)")
        
        ids        = []
        embeddings = []
        documents  = []
        metadatas  = []
        
        for i, chunk in enumerate(chunks):
            embedding = self._embed(chunk["text"])
            ids.append(chunk["id"])
            embeddings.append(embedding)
            documents.append(chunk["text"])
            metadatas.append({
                "source": chunk["source"],
                "chunk_index": chunk["chunk_index"]
            })
            
            # Progress every 10 chunks
            if (i + 1) % 10 == 0:
                logger.info(f"Embedded {i+1}/{len(chunks)} chunks...")
        
        # Upsert into ChromaDB (upsert = insert or update by ID)
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        
        total = self.collection.count()
        logger.info(f"Ingested {len(chunks)} chunks from '{source}'. Total in store: {total}")
        return len(chunks)

    # ── Public: Retrieve relevant chunks ─────────────────────────
    def retrieve(self, query: str, k: int = TOP_K) -> list:
        """
        Find the most relevant chunks for a query.
        Returns list of dicts with 'content' and 'source' keys.
        """
        if self.collection.count() == 0:
            return []
        
        try:
            query_embedding = self._embed(query)
            n = min(k, self.collection.count())
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n,
                include=["documents", "metadatas", "distances"]
            )
            
            chunks = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            ):
                # Convert cosine distance to similarity score (0-1)
                similarity = round(1 - dist, 3)
                chunks.append({
                    "content": doc,
                    "source": meta.get("source", "unknown"),
                    "similarity": similarity
                })
            
            # Filter out low-relevance chunks (similarity < 0.3)
            relevant = [c for c in chunks if c["similarity"] > 0.3]
            return relevant if relevant else chunks[:1]
            
        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            return []

    # ── Public: Get formatted context for prompt injection ────────
    def get_context_string(self, query: str, k: int = TOP_K) -> str:
        """
        Retrieve chunks and format them as a context string
        ready to inject into the LLM system prompt.
        """
        chunks = self.retrieve(query, k)
        
        if not chunks:
            return ""
        
        parts = []
        for i, chunk in enumerate(chunks, 1):
            parts.append(
                f"[Document {i} — Source: {chunk['source']} "
                f"(relevance: {chunk['similarity']})]:\n{chunk['content']}"
            )
        
        return "\n\n---\n\n".join(parts)

    # ── Public: Stats ─────────────────────────────────────────────
    def get_document_count(self) -> int:
        """Return total number of chunks in the vector store."""
        try:
            return self.collection.count()
        except:
            return 0

    def get_sources(self) -> list:
        """Return list of unique source document names."""
        try:
            if self.collection.count() == 0:
                return []
            results = self.collection.get(include=["metadatas"])
            sources = list({m["source"] for m in results["metadatas"]})
            return sorted(sources)
        except:
            return []

    def clear(self):
        """Delete all documents from the vector store."""
        try:
            self.chroma.delete_collection(COLLECTION_NAME)
            self.collection = self.chroma.get_or_create_collection(
                name=COLLECTION_NAME
            )
            logger.info("Vector store cleared.")
        except Exception as e:
            logger.error(f"Clear error: {e}")
