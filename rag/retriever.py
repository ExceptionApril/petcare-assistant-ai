from llama_index.core import VectorStoreIndex, Settings


def get_query_engine(index: VectorStoreIndex, top_k: int = 3, llm=None):
    """
    Build a query engine.
    If `llm` is given, use it explicitly.
    Otherwise use whatever is in Settings.llm (which app.py sets via _configure_global_llm).
    """
    if llm is not None:
        return index.as_query_engine(similarity_top_k=top_k, llm=llm)
    return index.as_query_engine(similarity_top_k=top_k)


def rag_query(query: str, query_engine) -> tuple[str, list[str]]:
    """
    Run a RAG query.
    Returns (answer_str, list_of_source_filenames).
    Appends '📚 Sources: ...' to the answer if sources are found.
    """
    try:
        response = query_engine.query(query)
        answer = str(response).strip()

        sources = []
        if hasattr(response, "source_nodes") and response.source_nodes:
            for node in response.source_nodes:
                fname = node.metadata.get("file_name") or node.metadata.get("filename", "")
                if fname and fname not in sources:
                    sources.append(fname)

        if sources:
            answer += "\n\n📚 Sources: " + ", ".join(sources)

        return answer, sources
    except Exception as e:
        return f"I couldn't retrieve information from the knowledge base: {e}", []
