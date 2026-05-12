import os
import shutil
import pytest
from rag.loader import load_documents
from rag.index import build_or_load_index
from rag.retriever import get_query_engine, rag_query

DATA_DIR = "./data"
PERSIST_DIR = "./.chroma_db_test"

@pytest.fixture(scope="module")
def setup_teardown():
    # Setup: ensure data dir exists and has some data
    assert os.path.exists(DATA_DIR), "Data directory not found"
    
    # Teardown
    yield
    if os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR, ignore_errors=True)

def test_documents_load(setup_teardown):
    docs = load_documents(DATA_DIR)
    assert len(docs) > 0, "No documents loaded"

def test_index_builds(setup_teardown):
    index = build_or_load_index(DATA_DIR, PERSIST_DIR)
    assert index is not None

def test_query_returns_string_with_sources(setup_teardown):
    index = build_or_load_index(DATA_DIR, PERSIST_DIR)
    mock_llm = MockLLM(max_tokens=256)
    engine = get_query_engine(index, top_k=2, llm=mock_llm)
    
    answer, sources = rag_query("What is parvovirus?", engine)
    
    assert isinstance(answer, str)
    assert len(answer) > 0
    assert "parvovirus" in answer.lower()
    
    assert len(sources) > 0
    assert any("pet_health_guide.txt" in s for s in sources)
    
    assert "📚 Sources:" in answer
