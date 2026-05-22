"""Langfuse integration for observability and tracing."""
import logging
from core.config import Config

logger = logging.getLogger(__name__)

try:
    from langfuse import Langfuse
    from langfuse.decorators import observe, langfuse_context
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    logger.warning("Langfuse not installed. Tracing disabled.")


class LangfuseTracer:
    """Wrapper for Langfuse tracing."""
    
    def __init__(self, config: Config):
        """Initialize Langfuse client if credentials provided."""
        self.config = config
        self.enabled = False
        self.langfuse = None
        
        if not LANGFUSE_AVAILABLE:
            logger.info("Langfuse module not available. Tracing disabled.")
            return
        
        if config.is_langfuse_enabled():
            try:
                self.langfuse = Langfuse(
                    secret_key=config.langfuse_secret_key,
                    public_key=config.langfuse_public_key,
                    baseurl=config.langfuse_base_url
                )
                
                # Test connection
                self.langfuse.auth_check()
                self.enabled = True
                logger.info("✅ Langfuse connected and ready for tracing")
            except Exception as e:
                logger.warning(f"⚠️ Langfuse connection failed: {e}")
                self.enabled = False
    
    def is_enabled(self) -> bool:
        """Check if tracing is enabled."""
        return self.enabled
    
    def trace_llm_call(self, model: str, messages: list, response_text: str, tokens_used: int = 0):
        """Trace an LLM call to Langfuse."""
        if not self.enabled or not self.langfuse:
            return
        
        try:
            self.langfuse.generation(
                name="llm-call",
                model=model,
                input={"messages": messages},
                output=response_text,
                metadata={
                    "provider": "openrouter",
                    "tokens_used": tokens_used
                }
            )
        except Exception as e:
            logger.debug(f"Langfuse trace error: {e}")
    
    def trace_rag_retrieval(self, query: str, results: list):
        """Trace RAG retrieval."""
        if not self.enabled or not self.langfuse:
            return
        
        try:
            self.langfuse.generation(
                name="rag-retrieval",
                model="RAG",
                input={"query": query},
                output={
                    "chunks_retrieved": len(results),
                    "preview": [r.get("text", "")[:100] for r in results]
                },
                metadata={
                    "retrieval_type": "chromadb",
                    "top_k": len(results)
                }
            )
        except Exception as e:
            logger.debug(f"Langfuse RAG trace error: {e}")
    
    def trace_agent_step(self, thought: str, action: str, observation: str):
        """Trace an agent reasoning step."""
        if not self.enabled or not self.langfuse:
            return
        
        try:
            self.langfuse.generation(
                name="agent-step",
                model="ReActAgent",
                input={
                    "thought": thought,
                    "action": action
                },
                output=observation,
                metadata={"step_type": "agent_reasoning"}
            )
        except Exception as e:
            logger.debug(f"Langfuse agent trace error: {e}")
    
    def flush(self):
        """Flush pending traces."""
        if self.enabled and self.langfuse:
            try:
                self.langfuse.flush()
            except Exception as e:
                logger.debug(f"Langfuse flush error: {e}")
