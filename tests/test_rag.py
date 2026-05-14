"""Tests for the RAG module: document loading, index building, and querying."""
import os
import shutil
import pytest
from llama_index.core.llms.mock import MockLLM
from rag.loader import load_documents
from rag.index import build_or_load_index
from rag.retriever import get_query_engine, rag_query

DATA_DIR = "./data"
PERSIST_DIR = "./.chroma_db_test"


@pytest.fixture(scope="module")
def setup_teardown():
    """Ensure data directory exists before tests and clean up after."""
    assert os.path.exists(DATA_DIR), "Data directory not found"
    yield
    if os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR, ignore_errors=True)


def test_documents_load(setup_teardown):
    """Documents should load from the data directory."""
    docs = load_documents(DATA_DIR)
    assert len(docs) > 0, "No documents loaded"


def test_index_builds(setup_teardown):
    """Index should build without error."""
    index = build_or_load_index(DATA_DIR, PERSIST_DIR)
    assert index is not None


def test_query_returns_string_with_sources(setup_teardown):
    """Query engine should return a non-empty answer with sources."""
    index = build_or_load_index(DATA_DIR, PERSIST_DIR)
    mock_llm = MockLLM(max_tokens=256)
    engine = get_query_engine(index, top_k=2, llm=mock_llm)

    answer, sources = rag_query("What is parvovirus?", engine)

    # Answer must be a non-empty string
    assert isinstance(answer, str)
    assert len(answer) > 0

    # Sources must be returned (files were loaded)
    assert len(sources) > 0

    # The formatted answer must include the sources citation
    assert "📚 Sources:" in answer
