"""Petlio AI - Current working chat experience with OpenRouter, RAG, and Langfuse."""

from __future__ import annotations

import datetime as _dt
import logging
import os
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

st.set_page_config(
    layout="wide",
    page_title="Petlio AI",
    page_icon="🐾",
    initial_sidebar_state="collapsed",
)


def petlio_logo_svg() -> str | None:
    """Return the local Petlio logo as a data URL when available."""
    logo_path = Path(__file__).resolve().parent / "img" / "petlio_logo.png"
    if not logo_path.exists():
        return None

    import base64

    try:
        data = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
        return f"data:image/png;base64,{data}"
    except Exception:
        return None


def _fmt_time() -> str:
    return _dt.datetime.now().strftime("%I:%M %p")


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
    st.session_state.current_chat_id = uuid.uuid4().hex
    st.session_state.messages = []
    st.session_state.token_count = 0
    st.session_state.chat_input = ""
    st.session_state.show_upload_picker = False
    _sync_active_chat()


def _handle_document_upload(uploaded_file) -> None:
    if not uploaded_file or not st.session_state.rag:
        return

    with st.spinner("Indexing..."):
        file_bytes = uploaded_file.read()
        chunks_added = st.session_state.rag.ingest_bytes(file_bytes, uploaded_file.name)
        _trace_rag(
            st.session_state.langfuse_tracer,
            f"Document upload: {uploaded_file.name}",
            [{"text": f"Ingested {chunks_added} chunks", "source": uploaded_file.name}],
        )
        st.success(f"✅ {uploaded_file.name} ({chunks_added} chunks)")


def _submit_chat_prompt(prompt_text: str) -> None:
    if not prompt_text:
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

    st.session_state.messages.append({"role": "user", "content": prompt_text})

    with st.spinner("Thinking..."):
        try:
            rag_context = ""
            sources_used: list[str] = []
            retrieved_chunks: list[dict] = []

            if st.session_state.rag and st.session_state.rag.get_document_count() > 0:
                try:
                    retrieved_chunks = st.session_state.rag.retrieve(prompt_text, k=3)
                    sources_used = [chunk.get("source", "unknown") for chunk in retrieved_chunks]
                    rag_context = st.session_state.rag.get_context_string(prompt_text, k=3)
                    _trace_rag(st.session_state.langfuse_tracer, prompt_text, retrieved_chunks)
                except Exception as exc:
                    logger.error("RAG error: %s", exc)

            if not st.session_state.agent:
                st.error("❌ Agent not initialized")
                return

            response_text, agent_steps = st.session_state.agent.generate_response(
                user_message=prompt_text,
                conversation_history=st.session_state.messages[-4:],
                use_reasoning=True,
                rag_context=rag_context,
                temperature=st.session_state.temperature,
                max_tokens=st.session_state.max_tokens,
            )

            _trace_llm(
                st.session_state.langfuse_tracer,
                user_input=prompt_text,
                response_text=response_text,
                tokens_used=len(prompt_text.split()) + len(response_text.split()),
            )
            _trace_agent_steps(st.session_state.langfuse_tracer, agent_steps)

            st.session_state.token_count += len(prompt_text.split()) + len(response_text.split())
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": response_text,
                    "sources": sources_used,
                    "agent_steps": agent_steps,
                    "rag_used": bool(rag_context),
                }
            )
            _sync_active_chat()
        except Exception as exc:
            logger.exception("Chat processing failed")
            st.error(f"❌ Error: {exc}")

    st.rerun()


st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --bg: #fdfaf1;
    --panel: #ffffff;
    --panel-soft: #faf7ef;
    --line: #e6e1d7;
    --text: #111827;
    --muted: #6b7280;
    --muted-2: #9ca3af;
    --gold: #f5c563;
    --gold-2: #f0b84d;
    --navy: #1b2333;
    --shadow: 0 14px 36px rgba(17, 24, 39, 0.06);
}

* { box-sizing: border-box; }
html, body, .stApp, [data-testid="stAppViewContainer"] {
    margin: 0;
    background: linear-gradient(180deg, #fffaf0 0%, #fdfaf1 100%);
    font-family: 'Inter', sans-serif;
    color: var(--text);
    height: 100vh;
    overflow: hidden;
}

#MainMenu, .stDeployButton, header, footer, [data-testid="stHeader"], [data-testid="collapsedControl"] {
    display: none !important;
}

[data-testid="stMainBlockContainer"] {
    max-width: 100% !important;
    padding: 0 !important;
    height: 100vh;
    overflow: hidden;
}

.block-container {
    padding: 0 !important;
    max-width: 100% !important;
}

.shell {
    display: grid;
    grid-template-columns: minmax(250px, 1.25fr) minmax(520px, 4.8fr) minmax(240px, 1.4fr);
    gap: 18px;
    padding: 18px;
    height: 100vh;
    overflow: hidden;
}

.panel {
    background: var(--panel);
    border: 1px solid rgba(230, 225, 215, 0.95);
    border-radius: 22px;
    box-shadow: var(--shadow);
    overflow: hidden;
}

.sidebar {
    background: transparent;
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
}

.sidebar-top,
.sidebar-mid,
.sidebar-bottom {
    padding: 18px 16px;
}

.sidebar-top {
    border-bottom: 1px solid var(--line);
}

.brand {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
}

.brand-mark {
    width: 42px;
    height: 42px;
    border-radius: 14px;
    background: linear-gradient(135deg, var(--gold), var(--gold-2));
    display: grid;
    place-items: center;
    font-weight: 800;
    color: #111827;
    box-shadow: 0 8px 20px rgba(245, 197, 99, 0.3);
    flex-shrink: 0;
}

.brand-mark img,
.chat-avatar img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
}

.brand-title { font-size: 1rem; font-weight: 800; color: var(--text); margin: 0; }
.brand-subtitle { font-size: 0.78rem; color: var(--muted); margin-top: 4px; }

.section-label {
    display: block;
    font-size: 0.8rem;
    font-weight: 800;
    color: var(--text);
    letter-spacing: 0.02em;
    margin-bottom: 10px;
}

.section-divider {
    height: 1px;
    background: var(--line);
    margin: 16px 0;
}

.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 9px;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 700;
    margin: 0 6px 8px 0;
    border: 1px solid transparent;
}
.status-ok { background: #dcfce7; color: #166534; border-color: #bbf7d0; }
.status-warn { background: #fef3c7; color: #92400e; border-color: #fde68a; }
.status-err { background: #fee2e2; color: #991b1b; border-color: #fecaca; }

.center {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: linear-gradient(180deg, #ffffff 0%, #fffef9 100%);
    overflow: hidden;
}

.chat-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 18px 20px;
    border-bottom: 1px solid var(--line);
    background: rgba(255,255,255,0.92);
}

.chat-avatar {
    width: 42px;
    height: 42px;
    border-radius: 50%;
    background: linear-gradient(135deg, #97b9bf, #e8ad7e);
    display: grid;
    place-items: center;
    font-size: 1.2rem;
    flex-shrink: 0;
    box-shadow: 0 8px 20px rgba(151, 185, 191, 0.24);
}

.chat-avatar img {
    border-radius: 50%;
}

.chat-title { font-weight: 800; font-size: 1rem; color: var(--text); }
.chat-subtitle { color: var(--muted); font-size: 0.78rem; margin-top: 3px; }

.messages {
    flex: 1;
    overflow-y: auto;
    padding: 18px 20px 10px;
    background: linear-gradient(180deg, #fdfaf1 0%, #fff8e6 100%);
    min-height: 0;
}

.message-row {
    display: flex;
    margin-bottom: 12px;
}

.message-row.user { justify-content: flex-end; }
.message-row.assistant { justify-content: flex-start; }

.bubble {
    max-width: min(78%, 700px);
    padding: 12px 15px;
    border-radius: 18px;
    line-height: 1.55;
    font-size: 0.92rem;
    word-break: break-word;
}

.bubble.user {
    background: linear-gradient(135deg, var(--gold), var(--gold-2));
    color: #111827;
    border-bottom-right-radius: 6px;
    box-shadow: 0 8px 18px rgba(245, 197, 99, 0.18);
}

.bubble.assistant {
    background: #ffffff;
    color: var(--text);
    border: 1px solid var(--line);
    border-bottom-left-radius: 6px;
    box-shadow: 0 4px 10px rgba(17, 24, 39, 0.05);
}

.meta-row {
    color: var(--muted-2);
    font-size: 0.72rem;
    margin-top: 4px;
}

.chips {
    display: flex;
    gap: 8px;
    padding: 0;
    flex-wrap: wrap;
    justify-content: center;
    border: 0;
    background: transparent;
}

.chip-btn {
    border: 1px solid var(--line) !important;
    background: #fff !important;
    color: var(--muted) !important;
    border-radius: 999px !important;
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    padding: 8px 16px !important;
    line-height: 1 !important;
    box-shadow: none !important;
    width: auto !important;
}

.chip-btn:active,
.chip-btn:focus-visible {
    background: #fff !important;
    color: var(--muted) !important;
    border-color: var(--line) !important;
    box-shadow: none !important;
}

.chip-btn:hover {
    border-color: var(--gold) !important;
    background: #fff9e6 !important;
    color: #111827 !important;
}

.chip-container-marker { display: none; }
.chip-container-marker + div [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important;
    justify-content: center !important;
}
.chip-container-marker + div [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: fit-content !important;
    flex: 0 0 auto !important;
    width: auto !important;
}
.chip-container-marker + div [data-testid="stButton"] > button {
    border-radius: 999px !important;
    border: 1px solid rgba(226,232,240,0.9) !important;
    background: #fff !important;
    color: #6b7280 !important;
    font-weight: 700 !important;
    padding: 8px 14px !important;
}
.chip-container-marker + div [data-testid="stButton"] > button:hover {
    background: #fff8ea !important;
    color: #111827 !important;
    border-color: var(--gold) !important;
}

/* Neutralize nested Streamlit columns/vertical blocks inside the center panel and chip row */
div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(2) div[data-testid="stColumn"] {
    background: transparent !important;
    min-height: 0 !important;
    height: auto !important;
    box-shadow: none !important;
}

div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(2) div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] {
    background: transparent !important;
    min-height: 0 !important;
    height: auto !important;
    overflow: visible !important;
}

 

.composer-card {
    flex-shrink: 0 !important;
    margin-top: 0px;
    padding: 0px;
    background: transparent;
    border: none;
    box-shadow: none;
}

.composer-footer {
    margin-top: 8px;
    margin-bottom: 0px;
}

[data-testid="stChatInput"] {
    border: 1px solid var(--line) !important;
    border-radius: 999px !important;
    background: #fff !important;
    box-shadow: 0 10px 24px rgba(17,24,39,0.05) !important;
}

[data-testid="stChatInput"]:focus-within {
    border-color: var(--gold) !important;
    box-shadow: 0 0 0 3px rgba(245,197,99,0.18), 0 10px 24px rgba(17,24,39,0.05) !important;
}

[data-testid="stChatInputSubmitButton"] button {
    background: linear-gradient(135deg, var(--gold), var(--gold-2)) !important;
    color: #111827 !important;
    border-radius: 50% !important;
    border: none !important;
}

 

.center {
    background: linear-gradient(180deg, #fdfaf1 0%, #fff7e6 100%);
    display: flex !important;
    flex-direction: column !important;
    height: 100% !important;
}

.right {
    background: #ffffff;
}

div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(1) .stButton > button {
    width: 100% !important;
    background: linear-gradient(135deg, var(--gold), var(--gold-2)) !important;
    color: #111827 !important;
    border: none !important;
    border-radius: 14px !important;
    font-weight: 800 !important;
    box-shadow: 0 10px 22px rgba(245, 197, 99, 0.22) !important;
}

div[data-testid="stColumn"]:nth-of-type(2) div[data-testid="stHorizontalBlock"] [data-testid="stButton"] > button {
    width: auto !important;
    padding: 8px 16px !important;
    border-radius: 999px !important;
    border: 1px solid var(--line) !important;
    background: #ffffff !important;
    color: var(--muted) !important;
    box-shadow: none !important;
    font-weight: 700 !important;
}

div[data-testid="stColumn"]:nth-of-type(2) div[data-testid="stHorizontalBlock"] [data-testid="stButton"] > button:hover {
    border-color: var(--gold) !important;
    background: #fff9e6 !important;
    color: #111827 !important;
}

div[data-testid="stColumn"]:nth-of-type(2) div[data-testid="stHorizontalBlock"]:last-of-type [data-testid="stButton"] > button {
    width: 42px !important;
    height: 42px !important;
    padding: 0 !important;
    border-radius: 50% !important;
    border: 1px solid rgba(230, 225, 215, 0.95) !important;
    background: #fff !important;
    color: #111827 !important;
    box-shadow: 0 8px 18px rgba(17, 24, 39, 0.08) !important;
}

div[data-testid="stColumn"]:nth-of-type(2) div[data-testid="stHorizontalBlock"]:last-of-type [data-testid="stButton"] > button:hover {
    border-color: var(--gold) !important;
    background: #fff9e6 !important;
}

[data-testid="stChatMessage"] {
    padding: 0 !important;
}

[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
    margin: 0 !important;
}

.composer-footer [data-testid="stColumn"] {
    padding: 0 4px !important;
}

.composer-footer [data-testid="stColumn"] [data-testid="stButton"] > button {
    width: 40px !important;
    height: 40px !important;
    padding: 0 !important;
    border-radius: 50% !important;
    border: 1px solid #e5e7eb !important;
    background: #ffffff !important;
    color: #111827 !important;
    font-weight: 700 !important;
    box-shadow: 0 2px 8px rgba(17, 24, 39, 0.06) !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

.composer-footer [data-testid="stColumn"] [data-testid="stButton"] > button:hover {
    background: #f9fafb !important;
    border-color: var(--gold) !important;
}

[data-testid="stChatInput"] {
    border: 1px solid var(--line) !important;
    border-radius: 999px !important;
    background: #ffffff !important;
    box-shadow: 0 2px 8px rgba(17, 24, 39, 0.04) !important;
    padding: 10px 16px !important;
}

[data-testid="stChatInput"]:focus-within {
    border-color: var(--gold) !important;
    box-shadow: 0 0 0 2px rgba(245, 197, 99, 0.1), 0 2px 8px rgba(17, 24, 39, 0.04) !important;
}

.right {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: #fff;
    overflow: hidden;
}

.right-head {
    padding: 18px 18px 12px;
    border-bottom: 1px solid var(--line);
}

.history-item {
    border: 1px solid transparent;
    background: #fafafa;
    border-radius: 14px;
    padding: 12px 13px;
    margin-bottom: 8px;
}

.history-title {
    font-size: 0.84rem;
    font-weight: 800;
    color: var(--text);
}

.history-time {
    margin-top: 4px;
    color: var(--muted-2);
    font-size: 0.72rem;
}

.empty-state {
    text-align: center;
    color: var(--muted-2);
    padding: 64px 18px 40px;
}

.empty-state h2 {
    margin: 12px 0 6px;
    color: var(--text);
    font-size: 1rem;
}

.expander-card {
    border: 1px solid var(--line);
    border-radius: 12px;
    background: #fcfcfc;
}

div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(1) > div[data-testid="stVerticalBlock"] {
    background: #ffffff !important;
    min-height: calc(100vh - 36px) !important;
    border-radius: 22px !important;
    overflow: hidden !important;
}

div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(1) {
    background: #ffffff !important;
    border-radius: 22px !important;
    overflow: hidden !important;
}

div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(2) > div[data-testid="stVerticalBlock"] {
    background: linear-gradient(180deg, #fdfaf1 0%, #fff7e6 100%) !important;
    min-height: calc(100vh - 36px) !important;
    border-radius: 22px !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    display: flex !important;
    flex-direction: column !important;
}

div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(2) {
    background: linear-gradient(180deg, #fdfaf1 0%, #fff7e6 100%) !important;
    border-radius: 22px !important;
    overflow: hidden !important;
}

div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3) > div[data-testid="stVerticalBlock"] {
    background: #ffffff !important;
    min-height: calc(100vh - 36px) !important;
    border-radius: 22px !important;
    overflow: hidden !important;
}

div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3) {
    background: #ffffff !important;
    border-radius: 22px !important;
    overflow: hidden !important;
}

div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(1) [data-testid="stButton"] > button {
    width: 100% !important;
    border: none !important;
    background: linear-gradient(135deg, var(--gold), var(--gold-2)) !important;
    color: #111827 !important;
    font-weight: 800 !important;
    border-radius: 14px !important;
    padding: 0.75rem 1rem !important;
    box-shadow: 0 10px 24px rgba(245, 197, 99, 0.24) !important;
}

div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3) [data-testid="stButton"] > button {
    width: 100% !important;
    background: #fffaf0 !important;
    color: #111827 !important;
    border: 1px solid #f3c15c !important;
    border-radius: 14px !important;
    text-align: left !important;
    font-weight: 700 !important;
    box-shadow: none !important;
    padding: 0.82rem 0.95rem !important;
    margin-bottom: 0.5rem !important;
}

div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3) .stCaption {
    margin: -0.3rem 0 0.8rem 0.2rem !important;
    color: var(--muted-2) !important;
}

div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    overflow: hidden !important;
}

div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] {
    height: 100% !important;
    overflow: hidden !important;
}

div[data-testid="stColumn"] div[data-testid="stColumn"] {
    background: transparent !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    min-height: 0 !important;
    height: auto !important;
    overflow: visible !important;
}

/* Sticky footer for center column */
div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(2) > div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"]:last-of-type {
    position: sticky;
    bottom: 0;
    z-index: 99;
    padding: 10px 18px 18px 18px;
    background: linear-gradient(180deg, rgba(255,247,230,0) 0%, #fff7e6 15%, #fff7e6 100%);
}

div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(2) > div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"]:last-of-type > div > div[data-testid="stVerticalBlock"] {
    background: #ffffff;
    border: 1px solid var(--line);
    border-radius: 24px;
    padding: 12px 18px 0px 18px;
    box-shadow: 0 4px 20px rgba(17,24,39,0.05);
}
</style>
""",
    unsafe_allow_html=True,
)


if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = []
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = uuid.uuid4().hex
if "token_count" not in st.session_state:
    st.session_state.token_count = 0
if "show_upload_picker" not in st.session_state:
    st.session_state.show_upload_picker = False
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.7
if "max_tokens" not in st.session_state:
    st.session_state.max_tokens = 400
if "pending_chat_prompt" not in st.session_state:
    st.session_state.pending_chat_prompt = ""

_normalize_chat_sessions()
if not st.session_state.chat_sessions:
    st.session_state.chat_sessions = [_build_chat_snapshot(st.session_state.current_chat_id)]
elif not any(session["id"] == st.session_state.current_chat_id for session in st.session_state.chat_sessions):
    st.session_state.chat_sessions.insert(0, _build_chat_snapshot(st.session_state.current_chat_id))

_sync_active_chat()

if "agent" not in st.session_state:
    try:
        from core.config import Config
        from agent_engine import ReActAgent
        from llm_client import get_llm_client

        config = Config()
        st.session_state.agent_config = config
        st.session_state.agent = ReActAgent(get_llm_client(config), config.openrouter_model)
    except Exception as exc:
        logger.exception("Agent initialization failed")
        st.error(f"❌ Failed to initialize agent: {exc}")
        st.session_state.agent = None
        st.session_state.agent_config = None

if "rag" not in st.session_state:
    try:
        from rag_engine import RAGEngine

        st.session_state.rag = RAGEngine()
    except Exception as exc:
        logger.exception("RAG initialization failed")
        st.error(f"❌ Failed to initialize RAG: {exc}")
        st.session_state.rag = None

if "langfuse_tracer" not in st.session_state:
    try:
        from core.config import Config
        from langfuse_tracer import LangfuseTracer

        tracer_config = st.session_state.get("agent_config") or Config()
        st.session_state.langfuse_tracer = LangfuseTracer(tracer_config)
    except Exception as exc:
        logger.warning("Langfuse initialization failed: %s", exc)
        st.session_state.langfuse_tracer = None


col_left, col_center, col_right = st.columns([1.4, 4.8, 1.5], gap="small")

with col_left:
    st.markdown('<div class="panel sidebar">', unsafe_allow_html=True)
    st.markdown("<div class='sidebar-top'>", unsafe_allow_html=True)
    sidebar_logo = petlio_logo_svg()
    sidebar_mark = f'<img src="{sidebar_logo}" alt="Petlio logo" />' if sidebar_logo else "P"
    st.markdown(
        """
        <div class="brand">
            <div class="brand-mark">%s</div>
            <div>
                <div class="brand-title">Petlio</div>
                <div class="brand-subtitle">Your friendly pet care companion</div>
            </div>
        </div>
        """ % sidebar_mark,
        unsafe_allow_html=True,
    )

    if st.button("+ New Chat", use_container_width=True, key="new_chat"):
        _start_new_chat()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.session_state.health_status = {
        "router": bool(os.getenv("OPENROUTER_API_KEY", "").strip()),
        "langfuse": bool(st.session_state.langfuse_tracer and st.session_state.langfuse_tracer.is_enabled()),
        "docs": st.session_state.rag.get_document_count() if st.session_state.rag else 0,
        "tokens": st.session_state.token_count,
    }
    st.markdown("</div>", unsafe_allow_html=True)

with col_center:
    st.markdown('<div class="panel center">', unsafe_allow_html=True)
    center_logo = petlio_logo_svg()
    center_mark = f'<img src="{center_logo}" alt="Petlio logo" />' if center_logo else "🐾"
    temperature = st.session_state.temperature
    max_tokens = st.session_state.max_tokens
    st.markdown(
        """
        <div class="chat-header">
            <div class="chat-avatar">%s</div>
            <div>
                <div class="chat-title">Petlio AI Assistant</div>
                <div class="chat-subtitle">Your friendly pet care companion</div>
            </div>
        </div>
        """ % center_mark,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="messages">', unsafe_allow_html=True)
    if not st.session_state.messages:
        st.markdown(
            """
            <div class="empty-state">
                <h2>Ask me anything about pet care</h2>
                <div>Upload documents in the left panel for personalized answers.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        for message in st.session_state.messages:
            role = message["role"]
            avatar = "🙂" if role == "user" else "🐾"
            with st.chat_message(role, avatar=avatar):
                st.markdown(f'<div class="bubble {role}">{message["content"]}</div>', unsafe_allow_html=True)

                if role == "assistant":
                    if message.get("sources"):
                        with st.expander(f"📚 Sources ({len(message['sources'])} documents used)"):
                            for source in sorted(set(message["sources"])):
                                st.caption(f"• {source}")

                    if message.get("agent_steps"):
                        with st.expander("🧠 Reasoning"):
                            for step in message["agent_steps"]:
                                st.markdown(f"**{step.get('thought', 'Thinking')}**")
                                if step.get("action"):
                                    st.caption(f"Action: {step['action']}")
                                if step.get("observation"):
                                    st.caption(step.get("observation", ""))

                    if message.get("rag_used"):
                        st.caption("🔍 Answer enhanced with uploaded documents")
    st.markdown('</div>', unsafe_allow_html=True)

    # Quick prompts as a horizontal tab bar
    quick_prompts = [
        ("Nutrition", "What should I feed my pet?"),
        ("Health", "What are common signs my pet is sick?"),
        ("Training", "Can you help me train my pet?"),
        ("Care Tips", "Share general pet care tips."),
        ("Warning Signs", "What warning signs should I watch for?"),
    ]
    
    key_map = {
        'nutrition': 'What should I feed my pet?',
        'health': 'What are common signs my pet is sick?',
        'training': 'Can you help me train my pet?',
        'care': 'Share general pet care tips.',
        'warnings': 'What warning signs should I watch for?',
    }
    chips = [
        ('nutrition', '🥗 Nutrition'),
        ('health', '❤️ Health'),
        ('training', '🎓 Training'),
        ('care', '💡 Care Tips'),
        ('warnings', '⚠️ Warning Signs'),
    ]

    with st.container():
        st.markdown('<div class="chip-container-marker"></div>', unsafe_allow_html=True)
        chip_cols = st.columns(len(chips), gap="small")
        for col, (k, label) in zip(chip_cols, chips):
            with col:
                if st.button(label, key=f"chip_{k}", use_container_width=True):
                    _submit_chat_prompt(key_map[k])

        if st.session_state.show_upload_picker:
            st.markdown(
                "<div style='padding:0 20px 10px 20px;'>"
                "<div class='expander-card' style='padding:14px 14px 10px;'>"
                "<div style='font-weight:700;margin-bottom:6px;'>Upload docs</div>"
                "<div style='color:#6b7280;font-size:0.82rem;margin-bottom:10px;'>PDF or TXT files are indexed into RAG.</div>"
                "</div></div>",
                unsafe_allow_html=True,
            )
            uploaded = st.file_uploader(
                "Upload PDF or TXT",
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

        st.markdown('<div class="composer-footer">', unsafe_allow_html=True)
        footer_cols = st.columns([0.08, 0.92], vertical_alignment="center")
        
        with footer_cols[0]:
            if st.button("＋", key="attach_docs", help="Upload docs", use_container_width=True):
                st.session_state.show_upload_picker = not st.session_state.show_upload_picker
                st.rerun()
        
        with footer_cols[1]:
            user_input = st.chat_input("Ask me anything about pet care...", key="chat_input")

        if user_input:
            _submit_chat_prompt(user_input)

        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="panel right">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="right-head">
            <div style="font-size:1rem;font-weight:800;color:#111827;">Pet Care Chats</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for session in st.session_state.chat_sessions[:10]:
        history_clicked = st.button(
            session.get("preview") or session.get("title") or "New chat",
            key=f"history_{session['id']}",
            use_container_width=True,
        )
        if history_clicked:
            _load_chat_session(session["id"])
            st.rerun()

        st.caption(session.get("time", ""))

    st.markdown("</div>", unsafe_allow_html=True)
