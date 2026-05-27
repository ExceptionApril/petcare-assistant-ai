"""Langfuse integration for observability and tracing (v3/v4 OTel API)."""
import logging
from core.config import Config

logger = logging.getLogger(__name__)

try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    logger.warning("Langfuse not installed. Tracing disabled.")


class LangfuseTracer:
    """Wrapper for Langfuse tracing (v3/v4 OTel-based SDK)."""

    def __init__(self, config: Config):
        self.config = config
        self.enabled = False
        self.langfuse = None

        if not LANGFUSE_AVAILABLE:
            return

        if config.is_langfuse_enabled():
            try:
                self.langfuse = Langfuse(
                    secret_key=config.langfuse_secret_key,
                    public_key=config.langfuse_public_key,
                    host=config.langfuse_base_url,
                )
                self.langfuse.auth_check()
                self.enabled = True
                logger.info("Langfuse connected.")
            except Exception as e:
                logger.warning("Langfuse connection failed: %s", e)
                self.enabled = False

    def is_enabled(self) -> bool:
        return self.enabled

    def trace_llm_call(self, model: str, messages: list, response_text: str, tokens_used: int = 0):
        """Trace an LLM call as a Langfuse generation."""
        if not self.enabled or not self.langfuse:
            return
        try:
            obs = self.langfuse.start_observation(
                name="petlio-llm-call",
                as_type="generation",
                model=model,
                input=messages,
                output=response_text,
                metadata={"provider": "openrouter"},
                usage_details={"total_tokens": tokens_used},
            )
            obs.end()
        except Exception as e:
            logger.warning("Langfuse LLM trace error: %s", e)

    def trace_rag_retrieval(self, query: str, results: list):
        if not self.enabled or not self.langfuse:
            return
        try:
            obs = self.langfuse.start_observation(
                name="petlio-rag-retrieval",
                as_type="retriever",
                input={"query": query},
                output={
                    "chunks_retrieved": len(results),
                    "preview": [r.get("content", r.get("text", ""))[:100] for r in results],
                },
                metadata={"top_k": len(results)},
            )
            obs.end()
        except Exception as e:
            logger.warning("Langfuse RAG trace error: %s", e)

    def trace_agent_step(self, thought: str, action: str, observation: str):
        if not self.enabled or not self.langfuse:
            return
        try:
            obs = self.langfuse.start_observation(
                name="petlio-agent-step",
                as_type="span",
                input={"thought": thought, "action": action},
                output=observation,
                metadata={"step_type": "agent_reasoning"},
            )
            obs.end()
        except Exception as e:
            logger.warning("Langfuse agent trace error: %s", e)

    def flush(self) -> None:
        if self.enabled and self.langfuse:
            try:
                self.langfuse.flush()
            except Exception as e:
                logger.warning("Langfuse flush error: %s", e)

    def get_managed_prompt(self, name: str, fallback: str = "") -> str:
        """Fetch a prompt from Langfuse Prompt Management with graceful fallback."""
        if not self.enabled or not self.langfuse:
            return fallback
        try:
            prompt = self.langfuse.get_prompt(name)
            if hasattr(prompt, "compile"):
                return prompt.compile()
            if hasattr(prompt, "prompt"):
                return prompt.prompt
            return fallback
        except Exception as e:
            logger.warning("Langfuse prompt '%s' unavailable: %s", name, e)
            return fallback
