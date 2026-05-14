"""
core/session.py
---------------
Streamlit session state helpers for Petlio.
Provides typed accessor/initialiser utilities so no other module
needs to touch st.session_state keys directly.
"""
from __future__ import annotations

from typing import Any
import streamlit as st


# ── Public key constants ───────────────────────────────────────────────────────

KEY_MESSAGES = "messages"
KEY_SESSION_ID = "session_id"
KEY_RAG_ENGINE = "rag_engine"
KEY_AGENT = "agent"
KEY_TRACER = "tracer"
KEY_CONFIG = "config"
KEY_EMBED_MODEL = "embed_model"
KEY_INITIALIZED = "_petlio_initialized"
KEY_RATE_LIMIT = "rate_limit_data"

# Sidebar preference keys
KEY_PET_TYPE = "pet_type"
KEY_PET_AGE = "pet_age"
KEY_USE_RAG = "use_rag"
KEY_USE_AGENT = "use_agent"
KEY_DEBUG_MODE = "debug_mode"


# ── Accessors ─────────────────────────────────────────────────────────────────

def get(key: str, default: Any = None) -> Any:
    """Retrieve a value from session state with an optional default."""
    return st.session_state.get(key, default)


def set_val(key: str, value: Any) -> None:
    """Set a value in session state."""
    st.session_state[key] = value


def is_initialized() -> bool:
    """Return True if the Petlio session has already been set up."""
    return st.session_state.get(KEY_INITIALIZED, False)


def mark_initialized() -> None:
    """Mark the session as fully initialized."""
    st.session_state[KEY_INITIALIZED] = True


def get_messages() -> list[dict]:
    """Return the conversation message history, initializing if necessary."""
    if KEY_MESSAGES not in st.session_state:
        st.session_state[KEY_MESSAGES] = []
    return st.session_state[KEY_MESSAGES]


def append_message(role: str, content: str, tools_used: list[str] | None = None) -> None:
    """Append a chat message (with optional tool metadata) to the history."""
    entry: dict[str, Any] = {"role": role, "content": content}
    if tools_used is not None:
        entry["tools_used"] = tools_used
    get_messages().append(entry)


def clear_messages() -> None:
    """Wipe the conversation history."""
    st.session_state[KEY_MESSAGES] = []
