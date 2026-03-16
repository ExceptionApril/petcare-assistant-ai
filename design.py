"""Petlio Design System - Fullscreen layout with 100% coverage"""
from urllib.parse import quote
import streamlit as st
import base64

APP_NAME = "Petlio"
MODEL_NAME = "gemini-2.0-flash"

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


def petlio_logo_svg():
    with open("./img/petlio_logo.png", "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{data}"

CSS = """<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif; }
[data-testid="stAppViewContainer"] { background: white; padding: 0 !important; width: 100vw !important; height: 100vh !important; position: fixed; top: 0; left: 0; }
[data-testid="stMainBlockContainer"] { padding: 0 !important; background: transparent; width: 100% !important; height: 100vh !important; }
.block-container { max-width: 100% !important; padding: 0 !important; width: 100%; height: 100vh; }
[data-testid="stHeader"] { display: none; }
[data-testid="stSidebar"] { display: none; }
[data-testid="collapsedControl"] { display: none; }

.nav-sidebar { width: 256px; background: #FAF9F6; border-right: 1px solid #e5e7eb; display: flex; flex-direction: column; overflow: hidden; flex-shrink: 0; height: 100vh; }
.nav-header { padding: 1rem; border-bottom: 1px solid #e5e7eb; flex-shrink: 0; }
.nav-logo { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; }
.nav-logo-icon { width: 32px; height: 32px; background: #F5C563; border-radius: 8px; display: flex; align-items: center; justify-content: center; }
.nav-logo-text { font-weight: 600; color: #111827; font-size: 0.95rem; }
.nav-button { width: 100%; background: #F5C563; color: #111827; border: none; padding: 0.65rem 1rem; border-radius: 8px; font-weight: 600; font-size: 0.875rem; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 0.5rem; transition: all 0.2s; }
.nav-button:hover { background: #f0b84d; }
.nav-menu { flex: 1; padding: 1rem; overflow-y: auto; min-height: 0; }
.nav-item { display: flex; align-items: center; gap: 0.75rem; padding: 0.6rem 0.75rem; color: #374151; font-size: 0.875rem; border-radius: 8px; margin-bottom: 0.25rem; transition: all 0.2s; cursor: pointer; }
.nav-item:hover { background: white; }
.nav-item.active { background: white; color: #111827; font-weight: 600; }
.nav-footer { padding: 1rem; border-top: 1px solid #e5e7eb; flex-shrink: 0; }

.chat-area { flex: 1; display: flex; flex-direction: column; background: white; overflow: hidden; min-width: 0; height: 100vh; }
.chat-header { border-bottom: 1px solid #e5e7eb; padding: 1rem; background: white; flex-shrink: 0; }
.header-content { display: flex; align-items: center; justify-content: space-between; }
.header-left { display: flex; align-items: center; gap: 0.75rem; }
.header-avatar { width: 40px; height: 40px; background: linear-gradient(135deg, #F5C563, #f0b84d); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.25rem; flex-shrink: 0; }
.header-title { font-weight: 600; color: #111827; font-size: 0.95rem; }
.header-subtitle { font-size: 0.75rem; color: #6b7280; margin-top: 0.2rem; }
.header-buttons { display: flex; gap: 0.5rem; flex-shrink: 0; }
.header-btn { width: 32px; height: 32px; background: #f3f4f6; border: none; border-radius: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; color: #4b5563; transition: all 0.2s; }
.header-btn:hover { background: #e5e7eb; }

.chat-messages { flex: 1; overflow-y: auto; padding: 1.5rem; background: linear-gradient(180deg, #FEFDFB 0%, #FFF9E6 100%); min-height: 0; }
.message { display: flex; margin-bottom: 1.5rem; gap: 0.75rem; align-items: flex-start; }
.message.user { justify-content: flex-end; }
.message.ai { justify-content: flex-start; }
.message-avatar { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1rem; flex-shrink: 0; }
.message-avatar.ai { background: linear-gradient(135deg, #F5C563, #f0b84d); color: #111827; font-weight: 700; }
.message-avatar.user { background: #111827; color: white; }
.message-bubble { max-width: 75%; padding: 1rem; border-radius: 16px; font-size: 0.875rem; line-height: 1.5; word-wrap: break-word; }
.message-bubble.ai { background: white; border: 1px solid #e5e7eb; color: #111827; }
.message-bubble.user { background: linear-gradient(135deg, #F5C563, #f0b84d); color: #111827; font-weight: 500; }
.message-time { font-size: 0.75rem; margin-top: 0.4rem; color: #9ca3af; }

.empty-chat { text-align: center; padding: 2rem; color: #6b7280; }
.empty-chat b { color: #111827; font-size: 1.1rem; }

.quick-actions { display: flex; gap: 0.5rem; margin-top: 1rem; margin-bottom: 1rem; overflow-x: auto; padding-bottom: 0.5rem; }
.quick-btn { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; background: white; border: 2px solid #e5e7eb; border-radius: 20px; font-size: 0.875rem; font-weight: 600; color: #374151; cursor: pointer; transition: all 0.2s; white-space: nowrap; flex-shrink: 0; }
.quick-btn:hover { border-color: #F5C563; background: #FFF9E6; color: #111827; }

.chat-input-area { background: white; border-top: 1px solid #e5e7eb; padding: 1rem; flex-shrink: 0; }
.input-row { display: flex; gap: 0.75rem; align-items: center; }
.input-field { flex: 1; padding: 0.75rem 1.5rem; background: #f3f4f6; border: none; border-radius: 24px; font-size: 0.875rem; color: #111827; outline: none; transition: all 0.2s; }
.input-field:focus { box-shadow: 0 0 0 2px #FFF9E6; background: white; border: 1px solid #F5C563; }
.input-field::placeholder { color: #6b7280; }

.chat-history { width: 288px; background: white; border-left: 1px solid #e5e7eb; padding: 1rem; overflow-y: auto; flex-shrink: 0; height: 100vh; }
.history-title { font-weight: 600; color: #111827; margin-bottom: 1rem; font-size: 0.95rem; }
.history-item { padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem; cursor: pointer; transition: all 0.2s; border: 1px solid transparent; background: #f9fafb; }
.history-item:hover { border-color: #e5e7eb; }
.history-item.active { background: #FFF9E6; border-color: #F5C563; }
.history-text { font-size: 0.875rem; color: #111827; font-weight: 500; line-height: 1.4; word-wrap: break-word; }
.history-time { font-size: 0.75rem; color: #6b7280; margin-top: 0.25rem; }

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #9ca3af; }

.stButton > button { background: linear-gradient(135deg, #F5C563, #f0b84d) !important; color: #111827 !important; border: none !important; border-radius: 8px !important; font-weight: 600 !important; }
.stButton > button:hover { box-shadow: 0 4px 12px rgba(245, 197, 99, 0.3) !important; }
.stTextInput input { background: white !important; border: 1px solid #e5e7eb !important; border-radius: 8px !important; color: #111827 !important; }
.stTextInput input:focus { border-color: #F5C563 !important; box-shadow: 0 0 0 2px #FFF9E6 !important; }
.stTextArea textarea { background: white !important; border: 1px solid #e5e7eb !important; border-radius: 8px !important; color: #111827 !important; }
.stSelectbox { background: white !important; }
</style>"""


def apply_design():
    """Apply fullscreen design to Streamlit app"""
    st.markdown(CSS, unsafe_allow_html=True)
