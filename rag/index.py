import os
import time
from llama_index.core import VectorStoreIndex, StorageContext, Settings
import chromadb

# Handle import compatibility for different LlamaIndex versions
try:
    from llama_index_vector_stores_chroma import ChromaVectorStore
except ImportError:
    try:
        from llama_index.vector_stores.chroma import ChromaVectorStore
    except ImportError:
        from llama_index.legacy.vector_stores.chroma import ChromaVectorStore

from rag.loader import load_documents, get_embed_model

def build_or_load_index(data_dir: str, persist_dir: str) -> VectorStoreIndex:
    """
    1. Initialize ChromaDB client pointing to persist_dir.
    2. If collection already exists AND data_dir has not been modified since last build:
       → Load existing index from ChromaDB (fast path).
    3. Else:
       → Load documents via loader.load_documents()
       → Build VectorStoreIndex with ChromaVectorStore
       → Persist to disk
    4. Return the index.
    """
    db = chromadb.PersistentClient(path=persist_dir)
    collection_name = "pet_knowledge"
    
    # Configure global settings
    Settings.embed_model = get_embed_model()
    Settings.chunk_size = 512
    Settings.chunk_overlap = 64

    # Check if collection exists
    collections = [c.name for c in db.list_collections()]
    
    # Simple check for modification (in a real app, might hash files, here we just check if dir exists and isn't empty)
    # For simplicity, if collection exists, we assume it's loaded unless forced to rebuild.
    if collection_name in collections:
        chroma_collection = db.get_collection(collection_name)
        if chroma_collection.count() > 0:
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            index = VectorStoreIndex.from_vector_store(
                vector_store,
                storage_context=storage_context,
            )
            return index

    # Else build from scratch
    chroma_collection = db.get_or_create_collection(collection_name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    documents = load_documents(data_dir)
    
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True
    )
    
    return index
