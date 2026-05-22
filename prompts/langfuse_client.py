"""✅ FIX 2: Langfuse tracer with Python 3.14 + pydantic compatibility."""
import logging
import time
import uuid
import os
import warnings
from typing import Optional, Dict, Any
from core.config import Config

# ✅ FIX 2: Filter pydantic warnings for Python 3.14
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", category=UserWarning, module="langfuse")

logger = logging.getLogger(__name__)

# ✅ FIX 2: Proper Langfuse initialization with environment variables
LANGFUSE_ENABLED = False
_langfuse = None

try:
    # Set defaults if not present
    os.environ.setdefault("LANGFUSE_SECRET_KEY", "")
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "")
    os.environ.setdefault("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    
    from langfuse import Langfuse
    
    _langfuse = Langfuse(
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        host=os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"),
    )
    
    # Check if keys are valid (not placeholder/empty)
    secret = os.getenv("LANGFUSE_SECRET_KEY", "")
    public = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    
    LANGFUSE_ENABLED = bool(
        secret and public and
        secret.startswith("sk-lf-") and
        public.startswith("pk-lf-") and
        len(secret) > 10 and
        len(public) > 10
    )
    
    if LANGFUSE_ENABLED:
        print("✅ Langfuse tracing enabled")
    else:
        print("⚠️ Langfuse keys not set — add real keys to .env to enable tracing")
        
except Exception as e:
    LANGFUSE_ENABLED = False
    _langfuse = None
    print(f"⚠️ Langfuse disabled: {e}")


class LangfuseTracer:
    """
    ✅ FIX 2: Enhanced Langfuse tracer with Python 3.14 compatibility.
    
    Features:
    - Complete trace lifecycle management (start → spans → end)
    - Tool execution tracing with timing and results
    - Error tracking and reporting
    - Rich metadata for filtering and analysis
    - User identification and session tracking
    - Automatic flushing and cleanup
    - Graceful degradation if Langfuse unavailable
    
    Best Practices:
    - Always call start_trace() at request start
    - Log generations, spans, and tool calls mid-request
    - Call end_trace() at request end
    - Safe to use without Langfuse credentials (graceful degradation)
    """
    
    def __init__(self, config: Config):
        """✅ FIX 2: Initialize tracer with safe fallback."""
        self.enabled = LANGFUSE_ENABLED and _langfuse is not None
        self.client = _langfuse if self.enabled else None
        self.current_trace: Optional[Any] = None
        self.current_trace_id: Optional[str] = None
        self.config = config
        
        if self.enabled:
            logger.info("✅ Langfuse tracing initialized")
        else:
            logger.warning("⚠️ Langfuse tracing disabled (add valid keys to .env)")
    
    def is_enabled(self) -> bool:
        """Check if Langfuse tracing is active."""
        return self.enabled and self.client is not None
    
    def start_trace(self, session_id: str, user_message: str, metadata: Dict[str, Any] = None) -> str:
        """
        ✅ FIX 2: Create a Langfuse trace. Return trace_id (or "" if disabled).
        Stores trace object for later reference.
        """
        if not self.enabled or not self.client:
            return ""
        
        if metadata is None:
            metadata = {}
            
        try:
            self.current_trace = self.client.trace(
                session_id=session_id,
                input=user_message,
                metadata=metadata,
                name="petlio-chat-turn"
            )
            self.current_trace_id = self.current_trace.id
            logger.debug(f"Started trace: {self.current_trace_id}")
            return self.current_trace_id
        except Exception as e:
            logger.warning(f"Failed to start trace: {e}")
            self.current_trace_id = ""
            return ""
    
    def log_generation(self, trace_id: str, model: str, prompt: str,
                       completion: str, latency_ms: int = 0, tools_used: list = None):
        """
        ✅ FIX 2: Log a generation span to an existing trace with timing and tool metadata.
        """
        if not self.enabled or not self.client or not trace_id:
            return
        
        if tools_used is None:
            tools_used = []
            
        try:
            # Log generation with proper timing
            self.client.generation(
                trace_id=trace_id,
                name="petlio-generation",
                model=model,
                input=prompt,
                output=completion,
                metadata={
                    "tools_used": tools_used,
                    "latency_ms": latency_ms,
                    "tool_count": len(tools_used)
                },
                usage={
                    "input": len(prompt.split()),
                    "output": len(completion.split())
                }
            )
            logger.debug(f"Logged generation to trace {trace_id} with {len(tools_used)} tools")
        except Exception as e:
            logger.warning(f"Failed to log generation: {e}")
    
    def log_rag_retrieval(self, trace_id: str, query: str, results: str, sources: list = None):
        """Log RAG retrieval operation as a span within the trace."""
        if not self.enabled or not self.client or not trace_id:
            return
        
        if sources is None:
            sources = []
        
        try:
            self.client.span(
                trace_id=trace_id,
                name="rag-retrieval",
                input=query,
                output=results,
                metadata={
                    "source_count": len(sources),
                    "sources": sources
                }
            )
            logger.debug(f"Logged RAG retrieval with {len(sources)} sources")
        except Exception as e:
            logger.warning(f"Failed to log RAG retrieval: {e}")
    
    def end_trace(self, trace_id: str, output: str = "", is_error: bool = False, error_msg: str = ""):
        """Close the trace with final output and error status."""
        if not self.enabled or not self.client or not trace_id:
            return
        
        try:
            # Update trace output
            if self.current_trace and self.current_trace.id == trace_id:
                metadata = {
                    "is_error": is_error,
                    "output_length": len(output) if output else 0
                }
                if error_msg:
                    metadata["error_message"] = error_msg
                    
                self.current_trace.end(
                    output=output,
                    metadata=metadata
                )
                logger.debug(f"Ended trace {trace_id}")
            
            # Ensure data is flushed to Langfuse
            self.client.flush()
            self.current_trace = None
            self.current_trace_id = None
        except Exception as e:
            logger.warning(f"Failed to end trace: {e}")
    
    def flush(self):
        """✅ FIX 2: Flush pending traces to Langfuse."""
        if not self.enabled or not self.client:
            return
        
        try:
            self.client.flush()
            logger.debug("Langfuse traces flushed")
        except Exception as e:
            logger.warning(f"Failed to flush Langfuse: {e}")
    
    def log_event(self, trace_id: str, event_name: str, event_type: str, 
                  metadata: dict = None, score: float = None):
        """
        Log event to trace.
        
        Args:
            trace_id: Parent trace ID
            event_name: Event identifier
            event_type: Type (info, warning, error, success)
            metadata: Additional event metadata
            score: Optional score (0-1) for user feedback
        """
        if not self.enabled or not self.client or not trace_id:
            return
        
        try:
            event_metadata = metadata or {}
            event_metadata["event_type"] = event_type
            
            self.client.event(
                trace_id=trace_id,
                name=event_name,
                metadata=event_metadata,
                input=str(event_metadata)
            )
            
            # If score provided, add it as feedback
            if score is not None:
                self.add_observation_score(trace_id, event_name, score)
                
            logger.debug(f"Logged event: {event_name} ({event_type})")
            
        except Exception as e:
            logger.debug(f"Failed to log event: {e}")
    
    def add_observation_score(self, trace_id: str, observation_id: str, score: float, 
                             comment: str = "", data_type: str = "NUMERIC"):
        """
        Add a score to an observation for evaluation/user feedback.
        
        Best practice usage:
        - Collect user feedback (thumbs up/down) and convert to 0-1 score
        - Add model-generated scores for quality, relevance, etc.
        - Batch multiple scores for comprehensive evaluation
        
        Args:
            trace_id: Parent trace ID
            observation_id: Event or span ID to score
            score: Score value (typically 0-1, but can be numeric)
            comment: Optional comment (e.g., user feedback text)
            data_type: NUMERIC, CATEGORICAL, or BOOLEAN
        """
        if not self.enabled or not self.client:
            return
        
        try:
            score_data = {
                "trace_id": trace_id,
                "observation_id": observation_id,
                "value": score,
                "comment": comment,
                "data_type": data_type
            }
            
            # Note: Langfuse 2.30+ supports direct score logging
            self.client.score(trace_id=trace_id, name=observation_id, value=score, 
                            comment=comment)
            
            logger.debug(f"Added score {score} to {observation_id}")
        except Exception as e:
            logger.debug(f"Failed to add observation score: {e}")
    
    def get_trace_link(self, trace_id: str) -> str:
        """
        Get the direct URL link to view a trace in Langfuse UI.
        
        Useful for:
        - Embedding in UI for quick access
        - Logging in debug output
        - Sharing trace URLs with team
        """
        if not self.enabled or not trace_id:
            return ""
        
        # Langfuse URL format: {host}/project/{project_id}/traces/{trace_id}
        # Since we don't have project_id easily available, use the generic format
        base_url = self.config.langfuse_host.rstrip("/")
        # Use "last" to go to the project's latest traces
        return f"{base_url}/project/last/traces/{trace_id}"
    
    def is_enabled(self) -> bool:
        """Check if Langfuse tracing is enabled."""
        return self.enabled
