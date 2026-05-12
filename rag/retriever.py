from llama_index.core import VectorStoreIndex

def get_query_engine(index: VectorStoreIndex, top_k: int = 3, llm=None):
    """
    Return index.as_query_engine(similarity_top_k=top_k)
    """
    if llm:
        return index.as_query_engine(similarity_top_k=top_k, llm=llm)
    return index.as_query_engine(similarity_top_k=top_k)

def rag_query(query: str, query_engine) -> tuple[str, list[str]]:
    """
    Run query. Return (answer_text, list_of_source_filenames).
    Always append to response: '📚 Sources: {sources}' if sources exist.
    """
    response = query_engine.query(query)
    answer_text = str(response)
    
    sources = []
    if response.source_nodes:
        for node in response.source_nodes:
            file_name = node.metadata.get("file_name")
            if file_name and file_name not in sources:
                sources.append(file_name)
                
    if sources:
        sources_str = ", ".join(sources)
        answer_text += f"\n\n📚 Sources: {sources_str}"
        
    return answer_text, sources
