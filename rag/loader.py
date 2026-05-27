import streamlit as st
from llama_index.core import SimpleDirectoryReader, Settings

# Handle import compatibility for different LlamaIndex versions
try:
    from llama_index_embeddings_huggingface import HuggingFaceEmbedding
except ImportError:
    try:
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    except ImportError:
        from llama_index.legacy.embeddings.huggingface import HuggingFaceEmbedding

def load_documents(data_dir: str) -> list:
    """
    Use LlamaIndex SimpleDirectoryReader.
    Supported extensions: .txt, .pdf, .md
    Chunk settings: chunk_size=512, chunk_overlap=64
    Returns list of LlamaIndex Document objects.
    """
    reader = SimpleDirectoryReader(
        input_dir=data_dir,
        required_exts=[".txt", ".pdf", ".md"],
        recursive=True
    )
    # The chunking is typically handled by the Settings or parsing nodes, but the prompt says
    # or just return the raw documents. We will set it in the global LlamaIndex settings.
    
    Settings.chunk_size = 512
    Settings.chunk_overlap = 64
    
    return reader.load_data()

def get_embed_model():
    """
    Return HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
    Cache the model in st.session_state to avoid re-loading on every rerun.
    """
    if "embed_model" not in st.session_state:
        st.session_state["embed_model"] = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
        
    return st.session_state["embed_model"]
