"""Petlio design helpers for the refactored one-page layout."""
from __future__ import annotations

from pathlib import Path
import base64

import streamlit as st

APP_NAME = "Petlio"

COLORS = {
    "gold": "#F5C563",
    "gold_dark": "#f0b84d",
    "cream": "#FEFDFB",
    "cream_light": "#FFF9E6",
    "navy": "#1a2d4d",
    "gray_900": "rgb(17, 24, 39)",
    "gray_100": "#f3f4f6",
    "gray_200": "#e5e7eb",
    "gray_400": "#9ca3af",
    "gray_500": "#6b7280",
    "gray_600": "#4b5563",
    "gray_700": "#374151",
    "gray_900_dark": "#111827",
    "white": "#ffffff",
}


def petlio_logo_svg() -> str | None:
    """Return the bundled Petlio logo as a data URL."""
    logo_path = Path(__file__).resolve().parent / "img" / "petlio_logo.png"
    if not logo_path.exists():
        return None

    try:
        data = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
        return f"data:image/png;base64,{data}"
    except Exception:
        return None


CSS = """<style>
:root {
    --bg: #fdfaf1;
    --panel: #ffffff;
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
    color: var(--text);
}

#MainMenu, .stDeployButton, header, footer, [data-testid="stHeader"], [data-testid="collapsedControl"] {
    display: none !important;
}

[data-testid="stMainBlockContainer"] {
    max-width: 100% !important;
    padding: 0 !important;
}

.shell {
    display: grid;
    grid-template-columns: minmax(250px, 1.25fr) minmax(520px, 4.8fr) minmax(240px, 1.4fr);
    gap: 18px;
    padding: 18px;
    min-height: 100vh;
}

.panel {
    background: var(--panel);
    border: 1px solid rgba(230, 225, 215, 0.95);
    border-radius: 22px;
    box-shadow: var(--shadow);
    overflow: hidden;
}

.sidebar {
    background: linear-gradient(180deg, #161b26 0%, #202635 100%);
    color: #f8fafc;
    display: flex;
    flex-direction: column;
    min-height: calc(100vh - 36px);
}

.sidebar-top,
.sidebar-mid,
.sidebar-bottom {
    padding: 18px 16px;
}

.sidebar-top { border-bottom: 1px solid rgba(255, 255, 255, 0.08); }

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

.brand-title { font-size: 1rem; font-weight: 800; color: #f8fafc; margin: 0; }
.brand-subtitle { font-size: 0.78rem; color: #cbd5e1; margin-top: 4px; }

[data-testid="column"]:nth-of-type(1) .stButton > button {
    width: 100% !important;
    border: none !important;
    background: linear-gradient(135deg, var(--gold), var(--gold-2)) !important;
    color: #111827 !important;
    font-weight: 800 !important;
    border-radius: 14px !important;
    padding: 0.75rem 1rem !important;
    box-shadow: 0 10px 24px rgba(245, 197, 99, 0.24) !important;
}

.section-label {
    display: block;
    font-size: 0.8rem;
    font-weight: 800;
    color: #f8fafc;
    letter-spacing: 0.02em;
    margin-bottom: 10px;
}

.section-divider {
    height: 1px;
    background: rgba(255, 255, 255, 0.08);
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
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(255, 255, 255, 0.08);
    color: #e2e8f0;
}

.center {
    display: flex;
    flex-direction: column;
    min-height: calc(100vh - 36px);
    background: linear-gradient(180deg, #fdfaf1 0%, #fff7e6 100%);
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

.chat-title { font-weight: 800; font-size: 1rem; color: var(--text); }
.chat-subtitle { color: var(--muted); font-size: 0.78rem; margin-top: 3px; }

.messages {
    flex: 1;
    overflow-y: auto;
    padding: 18px 20px 10px;
    background: linear-gradient(180deg, #fdfaf1 0%, #fff8e6 100%);
    min-height: 360px;
}

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

.chips {
    display: flex;
    gap: 8px;
    padding: 10px 18px 2px;
    flex-wrap: wrap;
    border-top: 1px solid rgba(230, 225, 215, 0.6);
    background: rgba(255,255,255,0.82);
}

.chip {
    padding: 7px 12px;
    border: 1px solid var(--line);
    background: #fff;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--muted);
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

.right {
    display: flex;
    flex-direction: column;
    min-height: calc(100vh - 36px);
    background: #fff;
}

.right-head {
    padding: 18px 18px 12px;
    border-bottom: 1px solid var(--line);
}

[data-testid="column"]:nth-of-type(3) .stButton > button {
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

[data-testid="column"]:nth-of-type(3) .stCaption {
    margin: -0.3rem 0 0.8rem 0.2rem !important;
    color: var(--muted-2) !important;
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
</style>"""


def apply_design() -> None:
    """Apply the shared one-page Petlio styling to a Streamlit app."""
    st.markdown(CSS, unsafe_allow_html=True)
