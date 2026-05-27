import logging
import time
from typing import Optional, Tuple, List
from llama_index.core import VectorStoreIndex, Settings

logger = logging.getLogger(__name__)

def get_query_engine(index: VectorStoreIndex, top_k: int = 3, llm=None):
    """
    Build a query engine.
    If `llm` is given, use it explicitly.
    Otherwise use whatever is in Settings.llm (which app.py sets via _configure_global_llm).
    """
    if llm is not None:
        return index.as_query_engine(similarity_top_k=top_k, llm=llm)
    return index.as_query_engine(similarity_top_k=top_k)


def rag_query(query: str, query_engine, tracer=None, trace_id: str = "") -> tuple[str, list[str]]:
    """
    Run a RAG query with optional Langfuse tracing.
    Returns (answer_str, list_of_source_filenames).
    Appends '📚 Sources: ...' to the answer if sources are found.
    
    Best Practice Tracing:
    - Logs query and retrieval results
    - Tracks sources for reproducibility
    - Captures latency for performance monitoring
    - Records retrieval context for debugging
    """
    start_time = time.time()
    sources = []
    
    try:
        response = query_engine.query(query)
        answer = str(response).strip()
        latency_ms = int((time.time() - start_time) * 1000)

        if hasattr(response, "source_nodes") and response.source_nodes:
            for node in response.source_nodes:
                fname = node.metadata.get("file_name") or node.metadata.get("filename", "")
                if fname and fname not in sources:
                    sources.append(fname)
        
        # ✅ Log RAG retrieval to Langfuse with comprehensive metadata
        if tracer and tracer.is_enabled() and trace_id:
            tracer.log_rag_retrieval(
                trace_id=trace_id,
                query=query,
                results=answer,
                sources=sources
            )
            tracer.log_event(
                trace_id=trace_id,
                event_name="rag-retrieval-success",
                event_type="success",
                metadata={
                    "query_length": len(query),
                    "source_count": len(sources),
                    "answer_length": len(answer),
                    "latency_ms": latency_ms,
                    "sources": sources
                }
            )
            logger.debug(f"✅ RAG retrieval logged: {len(sources)} sources in {latency_ms}ms")
        
        if sources:
            answer += "\n\n📚 Sources: " + ", ".join(sources)

        return answer, sources
        
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        error_msg = f"I couldn't retrieve information from the knowledge base: {e}"
        
        # ✅ Log RAG retrieval error to Langfuse
        if tracer and tracer.is_enabled() and trace_id:
            tracer.log_event(
                trace_id=trace_id,
                event_name="rag-retrieval-error",
                event_type="error",
                metadata={
                    "error": str(e),
                    "latency_ms": latency_ms,
                    "query_length": len(query)
                }
            )
            logger.debug(f"❌ RAG retrieval error logged: {str(e)[:100]}")
        
        return error_msg, []
