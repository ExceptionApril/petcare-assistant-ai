"""Langfuse integration for observability and tracing (v3/v4 OTel API)."""
import logging
from contextlib import contextmanager
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

    @contextmanager
    def trace_turn(self, user_input: str, session_id: str | None = None):
        """Open a root span for one chat turn.

        Everything traced inside this context (RAG retrieval, agent steps, the
        LLM generation) nests under a single Langfuse trace instead of showing
        up as disconnected top-level observations. Session id groups turns of
        one chat together in the Langfuse Sessions view (v4 API, v3 fallback).
        """
        if not self.enabled or not self.langfuse:
            yield None
            return
        from contextlib import ExitStack
        stack = ExitStack()
        try:
            # v4: session/user/trace-name propagate via OTel baggage
            try:
                from langfuse import propagate_attributes
                stack.enter_context(propagate_attributes(
                    session_id=session_id, trace_name="petlio-chat-turn"))
            except Exception:
                pass
            opener = getattr(self.langfuse, "start_as_current_observation", None)
            if opener is not None:
                span = stack.enter_context(opener(
                    name="petlio-turn", as_type="span",
                    input={"question": user_input}))
            else:  # older v3 SDKs
                span = stack.enter_context(self.langfuse.start_as_current_span(
                    name="petlio-turn", input={"question": user_input}))
            self._set_trace_io(span, input=user_input, session_id=session_id)
        except Exception as e:
            logger.warning("Langfuse turn start error: %s", e)
            with stack:  # unwind anything partially opened
                yield None
            return
        with stack:  # body exceptions propagate normally; span still closes
            yield span

    def _set_trace_io(self, span, session_id=None, **io) -> None:
        """Set trace-level input/output across SDK versions (best-effort)."""
        try:
            if hasattr(span, "set_trace_io"):  # v4
                span.set_trace_io(**io)
            elif hasattr(self.langfuse, "update_current_trace"):  # v3
                self.langfuse.update_current_trace(
                    name="petlio-chat-turn", session_id=session_id, **io)
        except Exception as e:
            logger.debug("Langfuse trace io error: %s", e)

    def end_turn(self, span, output: str) -> None:
        """Attach the final answer to the turn span and its trace."""
        if not span:
            return
        try:
            span.update(output=output)
            self._set_trace_io(span, output=output)
        except Exception as e:
            logger.warning("Langfuse turn end error: %s", e)

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
