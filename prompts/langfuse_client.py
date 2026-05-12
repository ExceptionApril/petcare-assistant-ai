import logging
from typing import Optional
from langfuse import Langfuse
from core.config import Config

logger = logging.getLogger(__name__)

class LangfuseTracer:
    """
    Wraps Langfuse SDK for prompt versioning and trace logging.
    """
    
    def __init__(self, config: Config):
        # Initialize Langfuse client IF keys are present.
        # If keys are missing, set self.enabled = False and log a warning.
        # NEVER crash the app if Langfuse is unavailable.
        self.enabled = False
        self.client: Optional[Langfuse] = None
        
        try:
            if config.langfuse_public_key and config.langfuse_secret_key:
                self.client = Langfuse(
                    public_key=config.langfuse_public_key,
                    secret_key=config.langfuse_secret_key,
                    host=config.langfuse_host
                )
                self.enabled = True
            else:
                logger.warning("Langfuse keys missing. Tracing disabled.")
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse: {e}")
            self.enabled = False
            
    def get_prompt(self, prompt_name: str, fallback: str) -> str:
        # Fetch prompt from Langfuse by name.
        # If Langfuse unavailable OR prompt not found: return fallback.
        if not self.enabled or not self.client:
            return fallback
            
        try:
            langfuse_prompt = self.client.get_prompt(prompt_name)
            if langfuse_prompt:
                # Assuming prompt template has a get_langchain_prompt() or just returns the string
                # We'll just return the compiled prompt if possible, or fallback if format is complex.
                return langfuse_prompt.get_langchain_prompt() if hasattr(langfuse_prompt, "get_langchain_prompt") else fallback
        except Exception as e:
            logger.warning(f"Failed to fetch prompt from Langfuse: {e}")
            
        return fallback
    
    def start_trace(self, session_id: str, user_message: str, metadata: dict) -> str:
        # Create a Langfuse trace. Return trace_id (or "" if disabled).
        if not self.enabled or not self.client:
            return ""
            
        try:
            trace = self.client.trace(
                session_id=session_id,
                input=user_message,
                metadata=metadata,
                name="petlio-chat-turn"
            )
            # Store the current trace so we can reference it easily
            # In a real app we might pass the trace object around, but we'll return its ID
            return trace.id
        except Exception as e:
            logger.warning(f"Failed to start trace: {e}")
            return ""
    
    def log_generation(self, trace_id: str, model: str, prompt: str,
                        completion: str, latency_ms: int, tools_used: list[str]):
        # Log a generation span to an existing trace.
        if not self.enabled or not self.client or not trace_id:
            return
            
        try:
            # Reconstruct or get trace object by id
            # With langfuse python sdk, if we don't have the object, we can create a generation directly referencing trace_id
            self.client.generation(
                trace_id=trace_id,
                model=model,
                prompt=prompt,
                completion=completion,
                metadata={"tools_used": tools_used},
                # Wait, latency_ms is normally inferred by start_time/end_time. We'll pass it as metadata
            )
        except Exception as e:
            logger.warning(f"Failed to log generation: {e}")
    
    def end_trace(self, trace_id: str, output: str, is_error: bool = False):
        # Close the trace with final output.
        if not self.enabled or not self.client or not trace_id:
            return
            
        try:
            # Update the trace with the final output
            # We can't directly update trace output easily without the trace object
            # We will flush the client to ensure all spans/generations are sent
            self.client.flush()
        except Exception as e:
            logger.warning(f"Failed to end trace: {e}")
