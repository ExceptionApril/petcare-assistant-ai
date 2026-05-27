"""Petlio AI - Unified Premium Chat Experience with Custom Collapsible Sidebar."""

from __future__ import annotations

import datetime as _dt
import logging
import os
import uuid
import base64
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

# Bridge Streamlit secrets → os.environ for Streamlit Cloud deployment.
# On local dev the .env file is used; on Cloud, secrets come from st.secrets.
try:
    for _sk, _sv in st.secrets.items():
        if isinstance(_sv, str) and _sk not in os.environ:
            os.environ[_sk] = _sv
except Exception:
    pass  # No secrets configured — rely on .env / existing env vars

_sidebar_init = "expanded"

# Set up page configurations
st.set_page_config(
    layout="wide",
    page_title="Petlio AI",
    page_icon="🐾",
    initial_sidebar_state=_sidebar_init,
)


def petlio_logo_svg() -> str | None:
    """Return the local Petlio logo as a data URL when available."""
    logo_path = Path(__file__).resolve().parent / "img" / "petlio_logo.png"
    if not logo_path.exists():
        return None
    try:
        data = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
        return f"data:image/png;base64,{data}"
    except Exception:
        return None


def _fmt_time() -> _dt.datetime:
    return _dt.datetime.now()


def _fmt_friendly_time(dt) -> str:
    if not dt:
        return "Just now"
    if isinstance(dt, str):
        return dt
    now = _dt.datetime.now()
    diff = now - dt
    diff_sec = diff.total_seconds()
    if diff_sec < 60:
        return "Just now"
    elif diff_sec < 3600:
        m = int(diff_sec / 60)
        return f"{m}m ago"
    elif diff_sec < 86400:
        h = int(diff_sec / 3600)
        return f"{h}h ago"
    elif diff_sec < 172800:
        return "Yesterday"
    else:
        d = int(diff_sec / 86400)
        return f"{d} days ago"


_MEMORY_TRIGGERS = (
    "recall",
    "remember",
    "what did i",
    "what was",
    "what's my",
    "whats my",
    "what is my",
    "do you remember",
    "did i tell you",
    "i told you",
    "my name is",
    "my cat's name",
    "my cats name",
    "my dog's name",
    "my dogs name",
    "name of my",
    "the name of my",
    "earlier i said",
    "you said earlier",
    "previous",
)


def _is_memory_question(message: str) -> bool:
    """True when the user is asking the assistant to recall something from
    the conversation itself, not a knowledge question about pet care.

    Used to bypass RAG so document chunks don't get injected and steer the
    LLM away from answering the actual recall question.
    """
    if not message:
        return False
    low = message.lower()
    return any(trigger in low for trigger in _MEMORY_TRIGGERS)


def _is_injection(message: str) -> bool:
    patterns = [
        "ignore previous instructions",
        "you are now",
        "act as",
        "jailbreak",
        "override",
        "system:",
        "forget your instructions",
        "new persona",
        "dan",
    ]
    lower = message.lower()
    return any(pattern in lower for pattern in patterns)


def _trace_rag(tracer, query: str, chunks: list[dict]) -> None:
    if tracer and tracer.is_enabled():
        tracer.trace_rag_retrieval(query=query, results=chunks)


def _trace_llm(tracer, user_input: str, response_text: str, tokens_used: int) -> None:
    if tracer and tracer.is_enabled():
        tracer.trace_llm_call(
            model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You are Petlio, a friendly pet care assistant."},
                {"role": "user", "content": user_input},
            ],
            response_text=response_text,
            tokens_used=tokens_used,
        )


def _trace_agent_steps(tracer, steps: list[dict]) -> None:
    if tracer and tracer.is_enabled() and steps:
        for step in steps:
            tracer.trace_agent_step(
                thought=step.get("thought", ""),
                action=step.get("action", ""),
                observation=step.get("observation", ""),
            )


def _summarize_text(text: str, limit: int = 72) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."


import re as _re

_BR_PATTERN = _re.compile(r"<br\s*/?>", _re.IGNORECASE)
_BR_PLACEHOLDER = "␂BRTAG␂"  # private-area sentinel that won't appear in LLM output


# Repair emphasis spans where the LLM inserted spaces or newlines adjacent to the
# delimiters (e.g. "** foo **" or "*foo\nbar*") — CommonMark needs delimiters flanked
# by non-whitespace inside, otherwise the asterisks render as literal text.
_BOLD_FIX = _re.compile(r"\*\*\s*([^*]+?)\s*\*\*", _re.DOTALL)
_ITALIC_FIX = _re.compile(r"(?<!\*)\*\s*([^*\n]{1,300}?)\s*\*(?!\*)")
_ITALIC_FIX_MULTILINE = _re.compile(r"(?<!\*)\*[ \t]*([^*]{2,400}?)[ \t]*\*(?!\*)", _re.DOTALL)


def _collapse_emphasis(text: str) -> str:
    """Trim whitespace inside ** ** and * * spans so markdown renders them."""
    def _bold(match: _re.Match) -> str:
        return f"**{match.group(1).strip()}**"

    def _italic(match: _re.Match) -> str:
        inner = match.group(1).strip()
        # Don't accidentally swallow conjunctions like "a * b" math notation
        if not inner or "*" in inner:
            return match.group(0)
        return f"*{inner}*"

    text = _BOLD_FIX.sub(_bold, text)
    text = _ITALIC_FIX.sub(_italic, text)
    text = _ITALIC_FIX_MULTILINE.sub(_italic, text)
    return text


def _sanitize_llm_output(text: str) -> str:
    """Strip free-model artifacts and repair common LLM markdown mistakes."""
    if not text:
        return ""
    cleaned = text.replace("[object Object]", "").replace(",[object Object],", "")
    cleaned = _collapse_emphasis(cleaned)
    # Drop lines that are just stray commas / orphan punctuation from broken JSON serialization
    cleaned_lines = [
        line for line in cleaned.splitlines()
        if line.strip() not in (",", ", ,", ",,", ", , ,")
    ]
    return "\n".join(cleaned_lines)


def _format_bubble_content(text: str) -> str:
    """Convert AI markdown text into safe HTML for the assistant bubble."""
    text = _sanitize_llm_output(text)
    # Preserve <br> tags (common in LLM-generated table cells) through markdown's HTML escape.
    text = _BR_PATTERN.sub(_BR_PLACEHOLDER, text)
    try:
        from markdown_it import MarkdownIt
        md = (
            MarkdownIt("commonmark", {"breaks": True})
            .enable("table")
            .enable("strikethrough")
        )
        rendered = md.render(text)
    except Exception:
        import html as _html
        rendered = f"<p>{_html.escape(text)}</p>"
    return rendered.replace(_BR_PLACEHOLDER, "<br>")


def _build_chat_snapshot(chat_id: str) -> dict:
    messages = [dict(message) for message in st.session_state.get("messages", [])]
    title = "New chat"
    preview = "Start a new conversation"

    for message in messages:
        if message.get("role") == "user" and message.get("content"):
            title = _summarize_text(message["content"], 28)
            preview = _summarize_text(message["content"], 72)
            break

    if title == "New chat" and messages:
        preview = _summarize_text(messages[-1].get("content", ""), 72)

    return {
        "id": chat_id,
        "title": title,
        "time": _fmt_time(),
        "preview": preview,
        "messages": messages,
        "token_count": st.session_state.get("token_count", 0),
    }


def _normalize_chat_sessions() -> None:
    normalized: list[dict] = []
    for index, session in enumerate(st.session_state.get("chat_sessions", [])):
        if not isinstance(session, dict):
            continue
        chat_id = session.get("id") or f"legacy-{index}"
        normalized.append(
            {
                "id": chat_id,
                "title": session.get("title") or "New chat",
                "time": session.get("time") or _fmt_time(),
                "preview": session.get("preview") or session.get("title") or "New chat",
                "messages": [dict(message) for message in session.get("messages", [])],
                "token_count": session.get("token_count", 0),
            }
        )
    st.session_state.chat_sessions = normalized


def _sync_active_chat() -> None:
    snapshot = _build_chat_snapshot(st.session_state.current_chat_id)
    remaining = [session for session in st.session_state.chat_sessions if session["id"] != snapshot["id"]]
    st.session_state.chat_sessions = [snapshot, *remaining]


def _load_chat_session(chat_id: str) -> None:
    for session in st.session_state.chat_sessions:
        if session["id"] == chat_id:
            st.session_state.current_chat_id = chat_id
            st.session_state.messages = [dict(message) for message in session.get("messages", [])]
            st.session_state.token_count = session.get("token_count", 0)
            return


def _start_new_chat() -> None:
    _sync_active_chat()  # flush the current chat before switching
    st.session_state.current_chat_id = uuid.uuid4().hex
    st.session_state.messages = []
    st.session_state.token_count = 0
    st.session_state.chat_input = ""
    st.session_state.show_upload_picker = False
    _sync_active_chat()  # register the new empty chat


def _handle_document_upload(uploaded_file) -> None:
    """Ingest a user-uploaded PDF/TXT into the RAG store."""
    if not uploaded_file or not st.session_state.get("rag"):
        if uploaded_file:
            st.warning("📄 RAG system is not available. Documents cannot be indexed at this time.")
        return
    try:
        with st.spinner("Indexing..."):
            file_bytes = uploaded_file.read()
            chunks_added = st.session_state.rag.ingest_bytes(file_bytes, uploaded_file.name)
            _trace_rag(
                st.session_state.langfuse_tracer,
                f"Document upload: {uploaded_file.name}",
                [{"text": f"Ingested {chunks_added} chunks", "source": uploaded_file.name}],
            )
            if chunks_added > 0:
                st.toast(f"{uploaded_file.name} indexed ({chunks_added} chunks)", icon="📄")
            else:
                st.warning(f"⚠️ No content extracted from {uploaded_file.name}")
    except Exception as exc:
        logger.error("Document upload error: %s", exc)
        st.error(f"❌ Failed to index document: {exc}")


def _submit_chat_prompt(prompt_text: str) -> None:
    """Stage 1: validate, rate-limit, add user message, then trigger streaming rerun."""
    if not prompt_text:
        return

    # Rate limiting — check before doing anything else
    from core.security import rate_limit_check
    if not rate_limit_check(st.session_state, st.session_state.session_id, limit_per_minute=20):
        st.toast("⚠️ You're sending messages too fast. Please wait a moment.", icon="⚠️")
        return

    if _is_injection(prompt_text):
        st.session_state.messages.append({"role": "user", "content": prompt_text})
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": "I'm sorry, I can't process that request.",
                "sources": None,
                "agent_steps": None,
                "rag_used": False,
            }
        )
        st.rerun()
        return

    # Add user message immediately and mark prompt as pending
    st.session_state.messages.append({"role": "user", "content": prompt_text})
    st.session_state.pending_chat_prompt = prompt_text
    st.rerun()


def _process_pending_prompt() -> None:
    """Stage 2: run inside message_feed to stream the agent response."""
    prompt_text = st.session_state.pending_chat_prompt
    st.session_state.pending_chat_prompt = ""  # clear before any yields

    if not st.session_state.agent:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "❌ Agent not initialized.",
            "sources": None, "agent_steps": None, "rag_used": False,
        })
        st.rerun()
        return

    # RAG retrieval — only when the prompt looks like a knowledge question.
    # Personal/memory prompts ("remember my cat's name?") get cat.pdf as a top
    # match purely on token overlap, which drags the LLM off-task. Skip RAG
    # for those, and apply a similarity threshold for everything else so
    # irrelevant chunks aren't surfaced as "sources".
    rag_context = ""
    sources_used: list[str] = []
    skip_rag = _is_memory_question(prompt_text)
    try:
        if (
            not skip_rag
            and st.session_state.rag
            and st.session_state.rag.get_document_count() > 0
        ):
            retrieved_chunks = st.session_state.rag.retrieve(prompt_text, k=3)
            sources_used = [
                c.get("source", "")
                for c in retrieved_chunks
                if c.get("source", "") not in ("", "unknown")
            ]
            if retrieved_chunks:
                parts = [
                    f"[Document {i} — Source: {c['source']} (relevance: {c['similarity']})]:\n{c['content']}"
                    for i, c in enumerate(retrieved_chunks, 1)
                ]
                rag_context = "\n\n---\n\n".join(parts)
            _trace_rag(st.session_state.langfuse_tracer, prompt_text, retrieved_chunks)
    except Exception as exc:
        logger.error("RAG error: %s", exc)
        # If RAG fails with readonly/permission issues, mark it as unhealthy
        if st.session_state.rag and ("readonly" in str(exc).lower() or "permission" in str(exc).lower()):
            logger.warning("RAG marked unhealthy due to permission issues")
            st.session_state.rag = None
        # Continue without RAG context rather than failing the entire response

    # Conversation history (exclude the user message just added).
    # 12 messages ≈ 6 turns — enough to recall "my cat is named Mochi" said
    # a few turns earlier without blowing the context budget on free models.
    history_msgs = st.session_state.messages[:-1][-12:]
    clean_history = [{"role": m["role"], "content": m["content"]} for m in history_msgs]

    # Stream the response using st.status for reasoning steps
    full_response = ""
    agent_steps: list[dict] = []
    web_searches: list[str] = []
    blocked = False
    step_num = 0

    # Pre-seed the reasoning trace with the RAG retrieval (it happens before the agent loop)
    rag_steps: list[dict] = []
    if rag_context:
        step_num += 1
        rag_steps.append({
            "iteration": step_num,
            "thought": "Retrieve relevant chunks from indexed documents",
            "action": "rag_retrieve(k=3)",
            "observation": f"{len(sources_used)} sources: {', '.join(s.rsplit('/', 1)[-1] for s in sources_used) or 'none'}",
        })

    # Live-streaming placeholder for the assistant bubble (renders chunks token-by-token)
    response_placeholder = st.empty()

    with st.status("Petlio is thinking...", expanded=True) as status_box:
        if rag_context:
            st.write(f"📚 **Step {step_num}** · Retrieved "
                     f"{len(sources_used)} document chunk(s) from RAG store")
        try:
            for event_type, payload in st.session_state.agent.generate_response_stream(
                user_message=prompt_text,
                conversation_history=clean_history,
                use_reasoning=True,
                rag_context=rag_context,
                temperature=st.session_state.temperature,
                max_tokens=st.session_state.max_tokens,
            ):
                if event_type == "decision":
                    step_num += 1
                    st.write(f"💭 **Step {step_num}** · {payload}")
                elif event_type == "thinking":
                    step_num += 1
                    st.write(f"🌐 **Step {step_num}** · Web search: *{payload}*")
                    web_searches.append(payload)
                elif event_type == "chunk":
                    full_response += payload
                    # Live render of the answer as tokens stream in
                    response_placeholder.markdown(
                        f'<div class="msg-row assistant">'
                        f'<div class="bubble-assistant">'
                        f'{_format_bubble_content(full_response)}'
                        f'<span style="opacity:0.5;">▌</span>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
                elif event_type == "done":
                    agent_steps = payload
        except Exception as exc:
            logger.exception("Streaming failed")
            full_response = f"❌ Error: {exc}"
            blocked = True

        status_box.update(
            label="Done!" if not blocked else "Error occurred",
            state="complete" if not blocked else "error",
            expanded=False,
        )

    # Combine RAG + agent steps so the saved reasoning trace shows the whole flow
    agent_steps = rag_steps + (agent_steps or [])

    # Clear the live placeholder — the message will re-render through the normal loop on rerun
    response_placeholder.empty()

    # If the response was blocked by safety checks, use fallback
    if not full_response.strip() or blocked:
        full_response = (
            "I'm sorry, I can only help with pet care-related questions. "
            "Please ask something about your pet's health, nutrition, training, or care."
        )

    _trace_llm(
        st.session_state.langfuse_tracer,
        user_input=prompt_text,
        response_text=full_response,
        tokens_used=len(prompt_text.split()) + len(full_response.split()),
    )
    _trace_agent_steps(st.session_state.langfuse_tracer, agent_steps)
    # Flush so Streamlit reruns don't drop buffered traces
    if st.session_state.langfuse_tracer:
        st.session_state.langfuse_tracer.flush()

    st.session_state.token_count += len(prompt_text.split()) + len(full_response.split())
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response,
        "sources": sources_used,
        "web_searches": web_searches,
        "agent_steps": agent_steps,
        "rag_used": bool(rag_context),
    })
    _sync_active_chat()
    st.rerun()


# Initialize sessions states
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = []
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = uuid.uuid4().hex
if "token_count" not in st.session_state:
    st.session_state.token_count = 0
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.7
if "max_tokens" not in st.session_state:
    st.session_state.max_tokens = 1000
if "pending_chat_prompt" not in st.session_state:
    st.session_state.pending_chat_prompt = ""
if "show_upload_picker" not in st.session_state:
    st.session_state.show_upload_picker = False
if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex

_normalize_chat_sessions()
if not st.session_state.chat_sessions:
    st.session_state.chat_sessions = [_build_chat_snapshot(st.session_state.current_chat_id)]
elif not any(session["id"] == st.session_state.current_chat_id for session in st.session_state.chat_sessions):
    st.session_state.chat_sessions.insert(0, _build_chat_snapshot(st.session_state.current_chat_id))

_sync_active_chat()

# Initialize core engines
if "langfuse_tracer" not in st.session_state:
    try:
        from core.config import Config
        from langfuse_tracer import LangfuseTracer

        tracer_config = st.session_state.get("agent_config") or Config()
        st.session_state.langfuse_tracer = LangfuseTracer(tracer_config)
    except Exception as exc:
        logger.warning("Langfuse initialization failed: %s", exc)
        st.session_state.langfuse_tracer = None

if not st.session_state.get("agent"):
    try:
        from core.config import Config
        from agent_engine import ReActAgent
        from llm_client import get_llm_client
        from prompts.system import build_system_prompt

        config = Config()
        st.session_state.agent_config = config

        # Show an immediate, actionable banner if the key is missing —
        # otherwise the user only sees the generic chat error.
        if not config.is_openrouter_configured():
            st.error(
                "🔑 **OPENROUTER_API_KEY is not configured.** "
                "On Streamlit Cloud: open *Manage app → Settings → Secrets* and paste a real key "
                "(get one free at https://openrouter.ai/keys). On local dev: set it in `.env`."
            )

        system_prompt = build_system_prompt(
            pet_type="Unknown",
            pet_age="Unknown",
            use_rag=True,
            use_agent=True,
            lf_client=st.session_state.get("langfuse_tracer")
        )
        st.session_state.agent = ReActAgent(
            get_llm_client(config),
            config.openrouter_model,
            system_prompt=system_prompt,
            tracer=st.session_state.get("langfuse_tracer"),
        )
    except Exception as exc:
        logger.exception("Agent initialization failed")
        st.error(f"❌ Failed to initialize agent: {exc}")
        st.session_state.agent = None
        st.session_state.agent_config = None

if not st.session_state.get("rag"):
    try:
        from rag_engine import RAGEngine
        st.session_state.rag = RAGEngine()
        # Verify RAG is healthy
        if not st.session_state.rag.is_healthy():
            logger.warning("RAG health check failed, disabling RAG")
            st.session_state.rag = None
    except Exception as exc:
        logger.exception("RAG initialization failed")
        st.error(f"❌ Failed to initialize RAG: {exc}")
        st.session_state.rag = None


LOGO_DATA = petlio_logo_svg()


def _logo_img(w: int, h: int, r: str = "9px") -> str:
    if LOGO_DATA:
        return (
            f'<img src="{LOGO_DATA}" style="width:{w}px;height:{h}px;'
            f'object-fit:contain;flex-shrink:0;border-radius:{r};" alt="Petlio" />'
        )
    return "🐾"


# =============================================================================
# CSS — matches the screenshot design spec exactly
# =============================================================================
CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&display=swap');

/* --- Design tokens -------------------------------------------------------- */
:root {
    --primary: #f59e0b;
    --primary-hover: #d97706;
    --primary-grad: linear-gradient(135deg, #f59e0b, #eab308);
    --app-bg: #fefcf6;
    --surface: #ffffff;
    --cream: #fef8f3;
    --cream-border: #f5e6d8;
    --border: #e7e5e4;
    --text-primary: #2c2418;
    --text-muted: #78716c;
    --text-body: #5a4a38;
    --source-bg: #fef3c7;
    --source-text: #92400e;
    --shadow-sm: 0 1px 3px rgba(44,36,24,0.06);
    --shadow-md: 0 4px 16px rgba(44,36,24,0.08);
    --font: 'Outfit', 'Inter', system-ui, sans-serif;
}

/* --- Hide Streamlit chrome ------------------------------------------------ */
#MainMenu, header[data-testid="stHeader"], footer { visibility: hidden; }
.stDeployButton { display: none !important; }

/* --- Base ----------------------------------------------------------------- */
html, body, .stApp {
    font-family: var(--font) !important;
    background: var(--app-bg) !important;
}
.block-container {
    padding-top: 0.75rem !important;
    padding-bottom: 0 !important;
    max-width: 860px !important;
}

/* --- Sidebar — always visible, never collapsible ------------------------- */
button[data-testid="collapseSidebarButton"],
button[data-testid="baseButton-headerNoPadding"],
[data-testid="stSidebarCollapsedControl"] {
    display: none !important;
}
section[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
    transform: none !important;
    display: block !important;
    min-width: 15rem !important;
    visibility: visible !important;
}
section[data-testid="stSidebar"] > div { padding-top: 0 !important; }

/* Brand header */
.petlio-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 18px 16px 14px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 12px;
}
.petlio-brand-name {
    font-size: 18px;
    font-weight: 800;
    color: var(--text-primary);
    font-family: 'Outfit', sans-serif;
}

/* New Chat button — amber gradient */
section[data-testid="stSidebar"] .stButton > button {
    background: var(--primary-grad) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 0.55rem 0.75rem !important;
    width: 100% !important;
    box-shadow: 0 2px 8px rgba(245,158,11,0.18) !important;
    transition: opacity 150ms ease !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    opacity: 0.88 !important;
}

/* Override: history-item overlay buttons must be invisible */
div[class*="st-key-ch_item_"] .stButton > button {
    background: transparent !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    color: transparent !important;
    font-size: 0 !important;
    border: none !important;
}

/* Sidebar search */
section[data-testid="stSidebar"] .stTextInput input {
    background: #fafaf9 !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    font-size: 13px !important;
    color: var(--text-primary) !important;
}
section[data-testid="stSidebar"] .stTextInput label { display: none !important; }

/* Chat history rows */
.chat-hist-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 12px;
    border-radius: 8px;
    pointer-events: none;
}
.chat-hist-icon {
    width: 30px; height: 30px; border-radius: 50%;
    background: var(--primary-grad); color: #fff;
    font-size: 12px; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.chat-hist-details { flex: 1; min-width: 0; }
.chat-hist-header {
    display: flex; justify-content: space-between; align-items: center; gap: 6px;
}
.chat-hist-title {
    font-size: 13px; font-weight: 600; color: var(--text-primary);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1;
}
.chat-hist-time { font-size: 11px; color: var(--text-muted); flex-shrink: 0; }
.chat-hist-preview {
    font-size: 12px; color: var(--text-body);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 1px;
}

/* Overlay container positioning */
div[class*="st-key-ch_item_"] {
    position: relative !important;
    margin: 2px 8px !important;
    border-radius: 8px !important;
    min-height: 52px !important;
}
div[class*="st-key-ch_item_active_"] {
    background: #fde68a !important;
    border-left: 3px solid var(--primary) !important;
}
div[class*="st-key-ch_item_inactive_"]:hover { background: #fffbeb !important; }
div[class*="st-key-ch_item_"] button {
    position: absolute !important;
    inset: 0 !important;
    opacity: 0 !important;
    z-index: 10 !important;
    border: none !important;
    background: transparent !important;
    cursor: pointer !important;
    width: 100% !important;
    height: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    box-shadow: none !important;
}

/* Sidebar section label */
.sidebar-section-label {
    font-size: 11px; font-weight: 700; color: var(--text-muted);
    letter-spacing: 0.08em; text-transform: uppercase;
    padding: 6px 16px 4px; margin-top: 4px;
}

/* --- Top header bar ------------------------------------------------------- */
.chat-top-bar {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 0 12px;
    border-bottom: 1px solid var(--border);
    background: var(--app-bg);
    position: sticky; top: 0; z-index: 50;
    margin-bottom: 4px;
}
.chat-top-logo {
    width: 40px; height: 40px; border-radius: 12px;
    overflow: hidden; display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.chat-top-title {
    font-size: 15px; font-weight: 800; color: var(--text-primary);
    font-family: 'Outfit', sans-serif;
}
.chat-top-sub { font-size: 12px; color: var(--text-muted); margin-top: 1px; }
.online-dot {
    width: 8px; height: 8px; border-radius: 50%; background: #22c55e;
    box-shadow: 0 0 0 2px rgba(34,197,94,0.2); flex-shrink: 0; margin-left: auto;
}

/* --- Message bubbles ------------------------------------------------------ */
.msg-row {
    display: flex; align-items: flex-start; gap: 10px;
    width: 100%; margin-bottom: 14px;
}
.msg-row.user { flex-direction: row-reverse; }

.bubble-user {
    background: var(--primary-grad); color: #fff;
    font-size: 14px; line-height: 1.6; padding: 12px 16px;
    border-radius: 18px 18px 4px 18px;
    max-width: 70%; word-break: break-word;
    box-shadow: var(--shadow-sm);
}
.bubble-assistant {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 18px 18px 18px 4px;
    padding: 14px 18px; font-size: 14px; line-height: 1.6;
    color: var(--text-primary); max-width: 78%;
    word-break: break-word; box-shadow: var(--shadow-sm);
}

.avatar-me {
    width: 32px; height: 32px; border-radius: 50%;
    background: var(--text-primary); color: #fff;
    font-size: 10px; font-weight: 700; letter-spacing: 0.5px;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.avatar-bot {
    width: 32px; height: 32px; border-radius: 10px;
    overflow: hidden; display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.avatar-bot img { width: 32px; height: 32px; object-fit: contain; }

/* --- Sources panel -------------------------------------------------------- */
.sources-panel {
    margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border);
}
.sources-label {
    font-size: 10px; font-weight: 700; color: var(--text-muted);
    letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px;
}
.sources-list { display: flex; flex-direction: column; gap: 6px; }
.source-card {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 8px 10px;
    background: rgba(255,255,255,0.7);
    border: 1px solid var(--cream-border);
    border-radius: 10px; font-size: 13px;
}
.source-index {
    flex-shrink: 0; width: 20px; height: 20px; border-radius: 6px;
    background: var(--source-bg); color: var(--source-text);
    font-size: 11px; font-weight: 700;
    display: flex; align-items: center; justify-content: center; margin-top: 1px;
}
.source-body { flex: 1; min-width: 0; }
.source-title { font-weight: 600; color: var(--text-primary); }
.source-domain { color: var(--text-muted); font-size: 11px; margin-left: 6px; }
.source-snippet { color: var(--text-muted); font-size: 12px; margin-top: 2px; line-height: 1.4; }

/* Meta pills */
.meta-pill {
    display: inline-flex; align-items: center; gap: 4px;
    background: var(--source-bg); border: 1px solid #fde68a;
    border-radius: 20px; padding: 2px 10px;
    font-size: 11px; color: var(--source-text); font-weight: 600;
}
.meta-row {
    display: flex; gap: 6px; margin-top: 10px;
    padding-top: 10px; border-top: 1px solid var(--border); flex-wrap: wrap;
}

/* --- Welcome state -------------------------------------------------------- */
.welcome-wrap { text-align: center; padding: 40px 24px 20px; }
.welcome-title {
    font-size: 26px; font-weight: 800; color: var(--text-primary);
    margin: 12px 0 8px; font-family: 'Outfit', sans-serif;
}
.welcome-sub { font-size: 14px; color: var(--text-muted); margin-bottom: 24px; }

/* Suggestion buttons */
.st-key-sug_wrap [data-testid="stButton"] > button {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-body) !important;
    border-radius: 20px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 8px 16px !important;
    box-shadow: none !important;
    transition: all 150ms ease !important;
}
.st-key-sug_wrap [data-testid="stButton"] > button:hover {
    border-color: var(--primary) !important;
    color: var(--primary-hover) !important;
    background: #fffbeb !important;
}

/* --- Floating input card -------------------------------------------------- */
.st-key-input_card {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 20px !important;
    padding: 12px 16px 10px !important;
    box-shadow: var(--shadow-md) !important;
    margin-top: 8px !important;
}

/* Topic chip row */
.st-key-input_card [data-testid="stHorizontalBlock"]:first-of-type {
    gap: 6px !important;
    flex-wrap: nowrap !important;
    overflow-x: auto !important;
    scrollbar-width: none !important;
    margin-bottom: 10px !important;
}
.st-key-input_card [data-testid="stHorizontalBlock"]:first-of-type::-webkit-scrollbar {
    display: none !important;
}
.st-key-input_card [data-testid="stHorizontalBlock"]:first-of-type > div[data-testid="stColumn"] {
    flex: 0 0 auto !important;
    min-width: fit-content !important;
    padding: 0 !important;
}
.st-key-input_card [data-testid="stHorizontalBlock"]:first-of-type [data-testid="stButton"] > button {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-muted) !important;
    border-radius: 20px !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    padding: 4px 14px !important;
    box-shadow: none !important;
    transition: all 150ms ease !important;
    white-space: nowrap !important;
}
.st-key-input_card [data-testid="stHorizontalBlock"]:first-of-type [data-testid="stButton"] > button:hover {
    border-color: var(--primary) !important;
    color: var(--primary-hover) !important;
    background: #fffbeb !important;
}

/* Attach button (📎) next to the chat input */
.st-key-attach_btn > div > button {
    width: 38px !important;
    height: 38px !important;
    border-radius: 50% !important;
    border: 1px solid var(--border) !important;
    background: var(--app-bg) !important;
    color: var(--text-muted) !important;
    font-size: 16px !important;
    padding: 0 !important;
    box-shadow: none !important;
    flex-shrink: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

/* Chat input field inside card */
.st-key-input_card [data-testid="stChatInput"] {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    border-radius: 0 !important;
}
.st-key-input_card [data-testid="stChatInput"] textarea {
    background: transparent !important;
    font-size: 14px !important;
    color: var(--text-primary) !important;
    border: none !important;
    outline: none !important;
    font-family: var(--font) !important;
}
.st-key-input_card [data-testid="stChatInputSubmitButton"] button {
    background: var(--primary-grad) !important;
    color: #fff !important;
    border-radius: 50% !important;
    border: none !important;
    width: 36px !important;
    height: 36px !important;
    box-shadow: 0 2px 8px rgba(245,158,11,0.25) !important;
}

/* Hint text */
.input-hint {
    text-align: center; color: var(--text-muted); font-size: 11px; margin-top: 6px;
}

/* Misc */
[data-testid="stChatMessage"] { padding: 0 !important; }
[data-testid="stMarkdownContainer"] > p { margin: 0 !important; }

/* Prevent white flash during Streamlit reruns */
html, body { background-color: var(--app-bg) !important; }
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {
    background-color: var(--app-bg) !important;
    opacity: 1 !important;
}
[data-testid="stSkeleton"] { display: none !important; }
/* Prevent Streamlit dimming content during rerun */
.stApp > * { opacity: 1 !important; }

/* Markdown content inside assistant bubble */
.bubble-assistant p { margin: 4px 0; font-size: 14px; line-height: 1.6; }
.bubble-assistant ul,
.bubble-assistant ol { margin: 6px 0 6px 18px; padding: 0; }
.bubble-assistant li { font-size: 14px; line-height: 1.6; margin: 3px 0; }
.bubble-assistant strong { font-weight: 600; color: var(--text-primary); }
.bubble-assistant em { font-style: italic; }
.bubble-assistant code {
    font-family: 'Courier New', monospace;
    background: #f5f5f4; border-radius: 4px;
    padding: 1px 5px; font-size: 13px;
}
.bubble-assistant pre {
    background: #f5f5f4; border-radius: 8px;
    padding: 10px 14px; overflow-x: auto; margin: 8px 0;
}
.bubble-assistant pre code { background: none; padding: 0; }
.bubble-assistant blockquote {
    border-left: 3px solid var(--primary);
    margin: 6px 0; padding-left: 10px; color: var(--text-muted);
}
</style>"""

st.markdown(CSS, unsafe_allow_html=True)



# =============================================================================
# SIDEBAR — native Streamlit sidebar
# =============================================================================
with st.sidebar:
    # Brand header
    logo_26 = _logo_img(28, 28, "8px")
    st.markdown(
        f'<div class="petlio-brand">{logo_26}<span class="petlio-brand-name">Petlio</span></div>',
        unsafe_allow_html=True,
    )

    # (RAG status caption intentionally hidden — uploads happen via the 📎 button
    # next to the chat input.)

    # New Chat
    if st.button("＋  New Chat", key="btn_new_chat", use_container_width=True):
        _start_new_chat()
        st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Search
    st.text_input(
        "Search",
        key="search_query",
        placeholder="🔍  Search chats...",
        label_visibility="collapsed",
    )

    st.markdown('<div class="sidebar-section-label">Recent Chats</div>', unsafe_allow_html=True)

    # Filtered chat history
    search_query = st.session_state.get("search_query", "").lower()
    filtered_sessions = [
        s for s in st.session_state.chat_sessions
        if not search_query
        or search_query in s.get("title", "").lower()
        or search_query in s.get("preview", "").lower()
    ]

    if not filtered_sessions:
        st.markdown(
            '<div style="padding:24px 16px;text-align:center;color:#78716c;font-size:13px;">'
            'No conversations yet</div>',
            unsafe_allow_html=True,
        )
    else:
        for session in filtered_sessions[:15]:
            is_active = session["id"] == st.session_state.current_chat_id
            title = session.get("title") or "New chat"
            preview = session.get("preview") or "Start a new conversation"
            time_str = _fmt_friendly_time(session.get("time"))
            first_letter = title[0].upper() if title else "P"
            item_key = (
                f"ch_item_active_{session['id']}"
                if is_active
                else f"ch_item_inactive_{session['id']}"
            )
            with st.container(key=item_key):
                st.markdown(
                    f"""
                    <div class="chat-hist-item">
                        <div class="chat-hist-icon">{first_letter}</div>
                        <div class="chat-hist-details">
                            <div class="chat-hist-header">
                                <span class="chat-hist-title">{title}</span>
                                <span class="chat-hist-time">{time_str}</span>
                            </div>
                            <div class="chat-hist-preview">{preview}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("", key=f"select_{session['id']}", use_container_width=True):
                    _load_chat_session(session["id"])
                    st.rerun()



# =============================================================================
# MAIN CHAT AREA
# =============================================================================

# Top header bar
logo_40 = _logo_img(40, 40, "12px")
st.markdown(
    f"""
    <div class="chat-top-bar">
        <div class="chat-top-logo">{logo_40}</div>
        <div style="flex:1;min-width:0;">
            <div class="chat-top-title">Petlio AI Assistant</div>
            <div class="chat-top-sub">Your friendly pet care companion</div>
        </div>
        <div class="online-dot"></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Scrollable message feed
with st.container(height=560, border=False):
    if not st.session_state.messages:
        logo_big = (
            f'<img src="{LOGO_DATA}" style="width:72px;height:72px;object-fit:contain;'
            f'border-radius:18px;box-shadow:0 8px 24px rgba(245,158,11,0.2);'
            f'display:block;margin:0 auto;" alt="Petlio" />'
            if LOGO_DATA
            else '<span style="font-size:64px;display:block;text-align:center;">🐾</span>'
        )
        st.markdown(
            f"""
            <div class="welcome-wrap">
                {logo_big}
                <div class="welcome-title">How can I help with your pet today?</div>
                <div class="welcome-sub">Ask me anything about pet care, health, nutrition, and more.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        suggestion_prompts = [
            "What vaccinations does my dog need?",
            "Best food for a senior cat?",
            "How to train a puppy?",
            "Signs my pet is sick?",
        ]
        with st.container(key="sug_wrap"):
            sug_cols = st.columns(len(suggestion_prompts), gap="small")
            for i, sug in enumerate(suggestion_prompts):
                with sug_cols[i]:
                    if st.button(sug, key=f"sug_{i}", use_container_width=True):
                        _submit_chat_prompt(sug)
    else:
        bot_avatar_html = (
            f'<img src="{LOGO_DATA}" style="width:32px;height:32px;'
            f'object-fit:contain;border-radius:10px;" alt="Petlio" />'
            if LOGO_DATA
            else '<span style="font-size:22px;">🐾</span>'
        )
        for message in st.session_state.messages:
            role = message["role"]
            content = message["content"]

            if role == "user":
                st.markdown(
                    f"""
                    <div class="msg-row user">
                        <div class="avatar-me">ME</div>
                        <div class="bubble-user">{content}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                formatted = _format_bubble_content(content)

                # Build sources panel — document sources + web search queries
                sources_html = ""
                raw_sources = message.get("sources") or []
                raw_web_searches = message.get("web_searches") or []
                unique_sources = list(dict.fromkeys(s for s in raw_sources if s and s != "unknown"))
                if unique_sources or raw_web_searches:
                    cards = ""
                    for idx, src in enumerate(unique_sources[:5]):
                        src_file = src.rsplit("/", 1)[-1] if "/" in src else src
                        ext = src_file.rsplit(".", 1)[-1].upper() if "." in src_file else "DOC"
                        display_name = (
                            src_file.rsplit(".", 1)[0]
                            .replace("_", " ")
                            .replace("-", " ")
                            .title()
                        )
                        cards += (
                            f'<div class="source-card">'
                            f'<span class="source-index">{idx + 1}</span>'
                            f'<div class="source-body">'
                            f'<span class="source-title">{display_name}'
                            f'<span class="source-domain">{ext}</span></span>'
                            f'</div></div>'
                        )
                    import html as _html_mod
                    for query in raw_web_searches[:3]:
                        safe_q = _html_mod.escape(query)
                        cards += (
                            f'<div class="source-card">'
                            f'<span class="source-index" style="font-size:13px;background:#dbeafe;color:#1e40af;">🌐</span>'
                            f'<div class="source-body">'
                            f'<span class="source-title">{safe_q}'
                            f'<span class="source-domain">WEB</span></span>'
                            f'</div></div>'
                        )
                    sources_html = (
                        f'<div class="sources-panel">'
                        f'<div class="sources-label">Sources</div>'
                        f'<div class="sources-list">{cards}</div>'
                        f'</div>'
                    )

                # Meta pills (the reasoning trace lives in its own expander below)
                meta_parts: list[str] = []
                if message.get("rag_used") and not unique_sources and not raw_web_searches:
                    meta_parts.append('<span class="meta-pill">🔍 RAG</span>')
                meta_html = (
                    f'<div class="meta-row">{"".join(meta_parts)}</div>'
                    if meta_parts
                    else ""
                )

                st.markdown(
                    f"""
                    <div class="msg-row assistant">
                        <div class="avatar-bot">{bot_avatar_html}</div>
                        <div class="bubble-assistant">{formatted}{sources_html}{meta_html}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Reasoning trace — collapsible expander listing every agent step
                steps = message.get("agent_steps") or []
                if steps:
                    with st.expander("🧠 Show reasoning trace", expanded=False):
                        for step in steps:
                            iteration = step.get("iteration", "?")
                            thought = step.get("thought", "")
                            action = step.get("action", "")
                            observation = step.get("observation", "")
                            st.markdown(
                                f"**Step {iteration}** · {thought}\n\n"
                                f"- **Action:** `{action}`\n"
                                f"- **Observation:** {observation}"
                            )

        # Stream pending prompt inside the message feed
        if st.session_state.get("pending_chat_prompt"):
            _process_pending_prompt()


# =============================================================================
# FLOATING INPUT CARD
# =============================================================================
with st.container(key="input_card"):
    pill_chips = [
        ("nutrition", "🥗 Nutrition"),
        ("health", "🏥 Health"),
        ("training", "🎓 Training"),
        ("care", "🛁 Care Tips"),
        ("warnings", "⚠️ Warnings"),
    ]
    key_map = {
        "nutrition": "Tell me about pet Nutrition",
        "health": "Tell me about pet Health",
        "training": "Tell me about pet Training",
        "care": "Tell me about pet Care Tips",
        "warnings": "Tell me about pet Warning Signs",
    }
    pill_cols = st.columns(len(pill_chips), gap="small")
    for col, (k, label) in zip(pill_cols, pill_chips):
        with col:
            if st.button(label, key=f"pill_{k}", use_container_width=True):
                _submit_chat_prompt(key_map[k])

    inp_cols = st.columns([0.06, 0.94], vertical_alignment="center")
    with inp_cols[0]:
        with st.container(key="attach_btn"):
            if st.button("📎", key="attach_docs", help="Upload a PDF or TXT for RAG", use_container_width=True):
                st.session_state.show_upload_picker = not st.session_state.show_upload_picker
                st.rerun()
    with inp_cols[1]:
        user_input = st.chat_input("Ask me anything about pet care...", key="chat_input")

    if st.session_state.show_upload_picker:
        uploaded = st.file_uploader(
            "Upload a PDF or TXT to add to the knowledge base",
            type=["pdf", "txt"],
            label_visibility="collapsed",
            key=f"upload_{st.session_state.current_chat_id}",
        )
        if uploaded:
            try:
                _handle_document_upload(uploaded)
                st.session_state.show_upload_picker = False
                st.rerun()
            except Exception as exc:
                logger.exception("Upload failed")
                st.error(f"❌ {exc}")

    st.markdown(
        '<div class="input-hint">Press Enter to send · Shift + Enter for new line</div>',
        unsafe_allow_html=True,
    )

if user_input:
    _submit_chat_prompt(user_input)
