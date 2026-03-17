import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error as urlerror
from urllib import request as urlrequest

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
from design import petlio_logo_svg
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  


APP_NAME = "Petlio AI Assistant"
GEMINI_PROXY_HOST = "127.0.0.1"
GEMINI_PROXY_PORT = 8767
_PROXY_STARTED = False

# === PROMPT SYSTEM ===

ROLE_DEFINITION = (
    "You are Petlio, a friendly and knowledgeable pet-care assistant for first-time pet owners. "
    "Your sole purpose is to help users with all aspects of caring for any type of pet. "
    "You are warm, practical, and concise."
)

ALLOWED_TOPICS = (
    "You help with ALL of the following pet-care topics (this list is not exhaustive): "
    "feeding and nutrition, feeding schedules, food types and amounts, grooming, bathing, "
    "training and behavior, exercise and play, health and wellness, vaccinations, "
    "parasite prevention, first aid, emergency care, vet visits, pet adoption, "
    "breed information, pet safety, cage or habitat setup, and general pet wellbeing. "
    "This applies to dogs, cats, birds, fish, rabbits, hamsters, guinea pigs, reptiles, "
    "monkeys, turtles, snakes, and any other animal kept as a pet."
)

IN_SCOPE_PRIORITY_RULE = (
    "ALWAYS ANSWER questions that mention: a pet, an animal, feeding, grooming, training, "
    "health, vet, breed, habitat, or any animal species. "
    "Examples you MUST answer (do NOT refuse these): "
    "'What should I feed my pet?', "
    "'What vaccinations does my dog need?', "
    "'How do I train my cat?', "
    "'I have a monkey, what do I feed it?', "
    "'What should I feed my monkey?', "
    "'How do I groom my rabbit?', "
    "'Is my fish sick?'. "
    "If the question is even loosely related to a pet or animal, answer it helpfully."
)

SCOPE_GUARD_RULE = (
    "ONLY refuse — with exactly 'I can only help with pet care questions.' and nothing else — "
    "when the question has absolutely no connection to any animal or pet care. "
    "Clear refusal examples (no animal or pet mentioned at all): "
    "'Write me Python code', 'Solve this math problem', 'What is the capital of France?', "
    "'Give me a pasta recipe', 'Who won the election?'. "
    "When in doubt, answer as a pet-care assistant."
)

PARTIAL_REQUEST_RULE = (
    "If a request blends pet-care and non-pet topics (e.g., 'How to feed my dog AND build a REST API?'), "
    "answer ONLY the pet-care portion and completely ignore the non-pet portion."
)

RESPONSE_QUALITY_RULES = (
    "Response guidelines: "
    "Keep advice practical, actionable, and concise. "
    "Use simple language for first-time pet owners. "
    "When uncertain about medical/health issues, recommend consulting a veterinarian. "
    "Never invent information—only provide established pet care best practices."
)

SCHEDULE_FORMAT_RULE = (
    "When a user asks about a feeding schedule, meal times, or daily routine for any pet, "
    "you MUST respond using EXACTLY this tagged format and nothing else outside the tags:\n"
    "[SCHEDULE]\n"
    "Title: <schedule title here>\n"
    "Row: <time> | <description>\n"
    "Row: <time> | <description>\n"
    "Note: <note text here>\n"
    "[/SCHEDULE]\n"
    "Example:\n"
    "[SCHEDULE]\n"
    "Title: Puppy Feeding Schedule (2-6 months)\n"
    "Row: 8:00 AM | Morning meal - 1/2 cup puppy food + fresh water\n"
    "Row: 12:00 PM | Midday meal - 1/2 cup puppy food + water check\n"
    "Row: 5:00 PM | Evening meal - 1/2 cup puppy food + fresh water\n"
    "Note: Adjust portions based on breed size and activity level.\n"
    "[/SCHEDULE]\n"
    "Always tailor the schedule to the specific pet type, breed, and age the user mentions. "
    "Do NOT add any text outside the [SCHEDULE]...[/SCHEDULE] tags."
)

def _build_system_prompt() -> str:
    return "\n\n".join([
        ROLE_DEFINITION,
        ALLOWED_TOPICS,
        IN_SCOPE_PRIORITY_RULE,
        SCOPE_GUARD_RULE,
        PARTIAL_REQUEST_RULE,
        RESPONSE_QUALITY_RULES,
        SCHEDULE_FORMAT_RULE,
    ])


_PET_KEYWORDS = {
    "pet", "animal", "dog", "cat", "bird", "fish", "rabbit", "hamster",
    "guinea pig", "turtle", "snake", "parrot", "monkey", "reptile", "puppy",
    "kitten", "pup", "feline", "canine", "vet", "veterinarian", "feed", "feeding",
    "groom", "grooming", "train", "training", "breed", "paw", "fur", "feather",
    "aquarium", "cage", "kennel", "litter", "vaccination", "vaccine", "parasite",
    "flea", "tick", "worm", "leash", "collar", "habitat", "tank",
}

_REFUSAL_RESPONSE = "i can only help with pet care questions."


def _looks_like_pet_question(prompt: str) -> bool:
    """Return True if the prompt contains any known pet-related keyword."""
    lower = prompt.lower()
    return any(kw in lower for kw in _PET_KEYWORDS)

PET_CARE_SYSTEM_PROMPT = _build_system_prompt()


def _call_model(client: OpenAI, system_prompt: str, prompt: str) -> str:
    """Call the model and return the text response, or empty string on failure."""
    response = client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_tokens=700,
    )
    try:
        if response and response.choices and len(response.choices) > 0:
            choice = response.choices[0]
            if choice and choice.message and choice.message.content is not None:
                return str(choice.message.content).strip()
    except (AttributeError, IndexError, TypeError):
        pass
    return ""


_OVERRIDE_PROMPT = (
    "The user is asking a pet-care question. Answer it helpfully and concisely as Petlio."
)


def _build_reply(api_key: str, prompt: str) -> dict:
    """Use OpenRouter with OpenAI Python client - unified API for all models."""
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=30.0,
        )

        text = _call_model(client, PET_CARE_SYSTEM_PROMPT, prompt)

        # If the model falsely refused a clearly pet-related question, retry once
        # with a minimal override system prompt that removes the scope guard.
        if text.lower().strip().rstrip(".") == _REFUSAL_RESPONSE.rstrip(".") and _looks_like_pet_question(prompt):
            text = _call_model(client, _OVERRIDE_PROMPT, prompt)

        if not text:
            return {"ok": False, "error": "Empty response from OpenRouter. The model may be overloaded, try again."}
        return {"ok": True, "text": text}

    except Exception as exc:
        error_msg = str(exc)
        if "Invalid API Key" in error_msg or "401" in error_msg:
            error_msg = "Invalid OpenRouter API key. Get one at https://openrouter.ai"
        elif "Connection" in error_msg or "timeout" in error_msg:
            error_msg = "Could not connect to OpenRouter. Check your internet connection."
        return {"ok": False, "error": error_msg}


class _GeminiProxyHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json(200, {"ok": True})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/openrouter":
            self._send_json(404, {"ok": False, "error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw) if raw else {}
        except Exception:
            self._send_json(400, {"ok": False, "error": "Invalid JSON payload"})
            return

        prompt = (payload.get("prompt") or "").strip()
        api_key = (payload.get("apiKey") or "").strip() or os.getenv("OPENROUTER_API_KEY", "").strip()
        
        if not api_key:
            self._send_json(400, {"ok": False, "error": "OpenRouter API key missing"})
            return
        if not prompt:
            self._send_json(400, {"ok": False, "error": "Prompt is required"})
            return
        
        result = _build_reply(api_key=api_key, prompt=prompt)
        if result.get("ok"):
            self._send_json(200, result)
        else:
            self._send_json(502, result)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def ensure_gemini_proxy() -> None:
    global _PROXY_STARTED
    if _PROXY_STARTED:
        return

    def _serve() -> None:
        try:
            server = ThreadingHTTPServer((GEMINI_PROXY_HOST, GEMINI_PROXY_PORT), _GeminiProxyHandler)
            server.serve_forever()
        except Exception as e:
            print(f"Proxy server error: {e}")

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    import time
    time.sleep(0.5)  # Give the server time to start
    _PROXY_STARTED = True

PETLIO_LOGO = (
     f"<img src='{petlio_logo_svg()}' style='width:24px;height:24px;'>"
)

AI_REPLY_ICON = (
    "<svg viewBox='0 0 64 64' aria-hidden='true'>"
    "<rect x='8' y='8' width='40' height='40' rx='11' ry='11' fill='none' stroke='currentColor' stroke-width='3'/>"
    "<rect x='16' y='16' width='34' height='34' rx='10' ry='10' fill='none' stroke='currentColor' stroke-width='3'/>"
    "<path d='M20 35c2.5-5 7-8 13-8h7a3 3 0 0 0 3-3v-3.5l4.5 2.8a12 12 0 0 1 5.2 10.2v4.8c0 8.8-7.2 16-16 16H28c-8.8 0-16-7.2-16-16v-3.3z' fill='none' stroke='currentColor' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'/>"
    "<circle cx='38.5' cy='30.5' r='5.3' fill='#f5c563'/>"
    "<circle cx='38.5' cy='30.5' r='2.2' fill='currentColor'/>"
    "<path d='M22 39h13.5a3.5 3.5 0 0 1 3.5 3.5V45h-17z' fill='#f5c563'/>"
    "</svg>"
)


def icon_sidebar() -> str:
        return f"""
        <aside class="icon-sidebar">
            <div class="icon-logo">{PETLIO_LOGO}</div>
            <div class="icon-links">
                <button title="Home" aria-label="Home"></button>
                <button title="Chats" aria-label="Chats"></button>
                <button title="Stats" aria-label="Stats"></button>
            </div>
            <button class="icon-settings" title="Settings" aria-label="Settings"></button>
        </aside>
        """


def nav_sidebar() -> str:
        return f"""
        <aside class="nav-sidebar">
            <div class="nav-top">
                <div class="brand-row">
                    <div class="brand-icon">{PETLIO_LOGO}</div>
                    <div class="brand-name">Petlio</div>
                </div>
                <button id="new-chat-btn" class="new-chat-btn">+ New Chat</button>
            </div>
        </aside>
        """


def main_area() -> str:
        return f"""
        <main class="chat-main">
            <header class="chat-header">
                <div class="assistant-left">
                    <div class="assistant-badge">{PETLIO_LOGO}</div>
                    <div>
                        <h1>Petlio AI Assistant</h1>
                        <p>Your friendly pet care companion</p>
                    </div>
                </div>
            </header>

            <section id="chat-scroll" class="chat-scroll">
                <div id="messages" class="messages"></div>


            </section>

            <footer class="chat-footer">
                <div class="quick-actions">
                    <button data-prompt="What should I feed my pet?">Nutrition</button>
                    <button data-prompt="What vaccinations does my pet need?">Health</button>
                    <button data-prompt="How do I train my pet?">Training</button>
                    <button data-prompt="What are essential daily care tips?">Care Tips</button>
                    <button data-prompt="What are signs my pet is sick and needs a vet?">Warning Signs</button>
                </div>

                <div class="input-row">
                    <button class="plus-btn">+</button>
                    <input id="chat-input" type="text" placeholder="Ask me anything about pet care..." />
                    <button id="send-btn" class="send-btn">></button>
                </div>
            </footer>
        </main>
        """


def right_sidebar() -> str:
        return """
        <aside class="right-sidebar">
            <h2>Pet Care Chats</h2>
            <div id="chat-history-list" class="chat-history-list"></div>
            <button id="clear-history-btn" class="clear-history">Clear history</button>
        </aside>
        """


def confirmation_modal() -> str:
        return """
        <div id="new-chat-modal" class="modal hidden">
            <div class="modal-panel">
                <h3>Start New Chat?</h3>
                <p>Starting a new chat will clear your current conversation. Your chat history will still be saved.</p>
                <div class="modal-actions">
                    <button id="cancel-new-chat" class="ghost">Cancel</button>
                    <button id="confirm-new-chat" class="solid">Start New Chat</button>
                </div>
            </div>
        </div>
        """


def api_key_modal() -> str:
        return """
        <div id="api-key-modal" class="modal hidden">
            <div class="modal-panel">
                <h3>Gemini API Key</h3>
                <p>Paste your Gemini key to enable AI replies. It is stored only in your browser for this app.</p>
                <input id="api-key-input" type="password" placeholder="AIza..." class="key-input" />
                <div class="key-status-row">
                    <small id="api-key-status" class="key-status"></small>
                </div>
                <div class="modal-actions">
                    <button id="clear-api-key" class="ghost">Clear</button>
                    <button id="cancel-api-key" class="ghost">Cancel</button>
                    <button id="save-api-key" class="solid">Save Key</button>
                </div>
            </div>
        </div>
        """


def build_html(api_key: str) -> str:
    api_key_json = json.dumps(api_key)
    ai_reply_icon_json = json.dumps(AI_REPLY_ICON)
    return f"""
        <!doctype html>
        <html>
            <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <title>{APP_NAME}</title>
                <style>
                    :root {{
                        --accent-1: #F5C563;
                        --accent-2: #f0b84d;
                        --main-top: #FEFDFB;
                        --main-bottom: #FFF9E6;
                        --icon-dark: #111827;
                        --nav-light: #FAF9F6;
                        --gray-100: #f3f4f6;
                        --gray-200: #e5e7eb;
                        --gray-500: #6b7280;
                        --gray-700: #374151;
                        --text-main: #111827;
                        --white: #ffffff;
                    }}

                    * {{ box-sizing: border-box; }}
                    html, body {{ margin: 0; width: 100%; height: 100vh; overflow: hidden; font-family: "Segoe UI", Tahoma, sans-serif; background: #f5f7fa;}}
                    
                    .shell {{
                        width: 100%;
                        height: 98vh;
                        display: grid;
                        grid-template-columns: 56px 220px 1fr 240px;
                        overflow: hidden;
                        
                    }}

                    .icon-sidebar {{
                        background: var(--icon-dark);
                        color: #9ca3af;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        padding: 12px 0;
                        gap: 18px;
                        border-radius: 16px;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.08);
                        margin: 10px 10px 10px 0;
                        box-shadow: 0 6px 20px rgba(0,0,0,0.05)
                    }}

                    .icon-logo {{
                        width: 40px;
                        height: 40px;
                        border-radius: 10px;
                        background: #1f2937;
                        display: grid;
                        place-items: center;
                        color: var(--accent-1);
                        font-weight: 700;
                    }}
                    .icon-logo svg {{ width: 24px; height: 24px; }}

                    .icon-links {{ display: grid; gap: 10px; margin-top: 6px; flex: 1; align-content: start; }}
                    .icon-links button,
                    .icon-settings {{
                        width: 36px;
                        height: 36px;
                        border: none;
                        border-radius: 8px;
                        background: transparent;
                        color: #9ca3af;
                        cursor: pointer;
                        transition: 180ms ease;
                    }}

                    .icon-links button:hover,
                    .icon-settings:hover {{ background: #1f2937; color: #f3f4f6; }}

                    .nav-sidebar {{
                        background: var(--nav-light);
                        border-right: 1px solid var(--gray-200);
                        display: flex;
                        flex-direction: column;
                        overflow: hidden;
                        border-top-right-radius: 16px;
                        border-bottom-right-radius: 16px;
                        margin: 10px 10px 10px 0;
                        box-shadow: 0 6px 20px rgba(0,0,0,0.05)
                    }}

                    .nav-top {{ padding: 16px; border-bottom: 1px solid var(--gray-200); }}
                    .brand-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }}
                    .brand-icon {{
                        width: 30px;
                        height: 30px;
                        border-radius: 8px;
                        background: linear-gradient(90deg, #97b9bf, #e8ad7e);
                        color: #111827;
                        display: grid;
                        place-items: center;
                        font-weight: 700;
                    }}
                    .brand-icon svg {{ width: 18px; height: 18px; }}
                    .brand-name {{ font-weight: 700; color: var(--text-main); }}
                    .new-chat-btn {{
                        width: 100%;
                        border: none;
                        border-radius: 10px;
                        padding: 11px 14px;
                        color: #111827;
                        font-weight: 700;
                        cursor: pointer;
                        background: linear-gradient(135deg, var(--accent-1), var(--accent-2));
                        transition: transform 150ms ease, filter 150ms ease;
                    }}
                    .new-chat-btn:hover {{ transform: translateY(-1px); filter: brightness(1.02); }}

                    .chat-main {{ 
                        display: flex; 
                        flex-direction: column; 
                        background: #fff9e6; 
                        min-width: 0; height: 100%; 
                        overflow: hidden;
                        border-radius: 16px;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.08);
                        margin: 10px 10px 10px 0;
                        box-shadow: 0 6px 20px rgba(0,0,0,0.05);
                        }}

                    .chat-header {{
                        height: 64px;
                        min-height: 64px;
                        padding: 0 14px;
                        border-bottom: 1px solid var(--gray-200);
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        background: #ffffff;
                        flex-shrink: 0;
                    }}
                    .assistant-left {{ display: flex; align-items: center; gap: 10px; }}
                    .assistant-badge {{ 
                        width: 34px;
                        height: 34px;
                        border-radius: 50%;
                        display: grid;
                        place-items: center;
                        background: linear-gradient(90deg, #97b9bf, #e8ad7e);
                        color: #111827;
                        font-weight: 700;
                    }}
                    .assistant-badge svg {{ width: 20px; height: 20px; }}
                    .assistant-left h1 {{ margin: 0; font-size: 18px; color: var(--text-main); }}
                    .assistant-left p {{ margin: 2px 0 0; font-size: 12px; color: var(--gray-500); }}
                    .assistant-actions {{ display: flex; gap: 8px; }}
                    .assistant-actions button {{
                        width: 34px;
                        height: 34px;
                        border: none;
                        border-radius: 9px;
                        background: #f9fafb;
                        color: #4b5563;
                        cursor: pointer;
                        transition: 180ms ease;
                    }}
                    .assistant-actions button:hover {{ background: #f3f4f6; }}

                    .chat-scroll {{
                        flex: 1;
                        overflow-y: auto;
                        overflow-x: hidden;
                        background: linear-gradient(180deg, var(--main-top), var(--main-bottom));
                        padding: 14px;
                        display: flex;
                        flex-direction: column;
                        gap: 10px;
                        min-height: 0;
                    }}

                    .messages {{
                        display: flex;
                        flex-direction: column;
                        gap: 12px;
                    }}

                    .msg-row {{ display: flex; gap: 10px; animation: slideUp 240ms ease; }}
                    .msg-row.user {{ justify-content: flex-end; }}
                    .msg-row.ai {{ justify-content: flex-start; }}
                    .avatar {{
                        width: 32px;
                        height: 32px;
                        border-radius: 50%;
                        flex: 0 0 32px;
                        display: grid;
                        place-items: center;
                        font-size: 12px;
                        font-weight: 700;
                    }}
                    .avatar.ai {{ background: linear-gradient(135deg, var(--accent-1), var(--accent-2)); color: #111827; }}
                    .avatar.user {{ background: #1f2937; color: #fff; }}
                    .avatar.ai svg {{ width: 24px; height: 24px; }}
                    .bubble {{ max-width: min(640px, 75%); border-radius: 14px; padding: 12px 14px; line-height: 1.45; font-size: 14px; }}
                    .bubble.user {{ background: linear-gradient(135deg, var(--accent-1), var(--accent-2)); color: #111827; }}
                    .bubble.ai {{ background: #fff; border: 1px solid var(--gray-200); color: #111827; }}
                    .time {{ font-size: 11px; opacity: 0.72; margin-top: 6px; }}

                    .typing {{ display: inline-flex; gap: 4px; padding: 10px; }}
                    .typing span {{ width: 7px; height: 7px; border-radius: 50%; background: #9ca3af; animation: bounce 800ms infinite; }}
                    .typing span:nth-child(2) {{ animation-delay: 130ms; }}
                    .typing span:nth-child(3) {{ animation-delay: 260ms; }}

                    .feeding-card {{
                        background: #ffffff;
                        border: 1px solid var(--gray-200);
                        border-radius: 14px;
                        padding: 12px;
                        box-shadow: 0 8px 20px rgba(17, 24, 39, 0.04);
                        animation: fadeIn 300ms ease;
                        flex-shrink: 0;
                    }}
                    .feeding-card h3 {{ margin: 0 0 10px; font-size: 17px; color: #111827; }}
                    .card-row {{ display: grid; grid-template-columns: 86px 1fr; gap: 10px; padding: 9px 0; border-top: 1px solid #f3f4f6; font-size: 14px; }}
                    .card-row:first-of-type {{ border-top: none; }}
                    .card-row span:first-child {{ font-weight: 700; color: #374151; }}
                    .card-row span:last-child {{ color: #4b5563; }}
                    .card-note {{ margin-top: 8px; font-size: 13px; color: #4b5563; }}

                    .chat-footer {{
                        border-top: 1px solid var(--gray-200);
                        padding: 10px 14px;
                        background: #ffffff;
                        display: grid;
                        gap: 8px;
                        flex-shrink: 0;
                        border-radius: 16px;
                        margin: 12px;
                        box-shadow:
                            0 4px 8px rgba(0,0,0,0.04),
                            0 12px 24px rgba(0,0,0,0.08),
                            0 20px 40px rgba(0,0,0,0.04);
                    }}
                    .quick-actions {{ display: flex; gap: 8px; overflow-x: auto; padding-bottom: 4px; justify-content: center; }}
                    .quick-actions button {{
                        border: 1px solid var(--gray-200);
                        border-radius: 999px;
                        background: #ffffff;
                        color: #374151;
                        padding: 8px 12px;
                        cursor: pointer;
                        white-space: nowrap;
                        transition: 180ms ease;
                    }}
                    .quick-actions button:hover {{ border-color: #d1d5db; background: #f9fafb; }}

                    .input-row {{ display: grid; grid-template-columns: 40px 1fr 42px; gap: 10px; align-items: center; }}
                    .plus-btn,
                    .send-btn {{ border: none; border-radius: 50%; cursor: pointer; transition: transform 180ms ease, filter 180ms ease; }}
                    .plus-btn {{ height: 40px; width: 40px; background: #f3f4f6; color: #4b5563; font-size: 22px; line-height: 1; }}
                    .send-btn {{
                        height: 42px;
                        width: 42px;
                        font-weight: 700;
                        color: #111827;
                        background: linear-gradient(135deg, var(--accent-1), var(--accent-2));
                    }}
                    .plus-btn:hover,
                    .send-btn:hover {{ transform: translateY(-1px); filter: brightness(1.03); }}

                    #chat-input {{
                        border: 1px solid var(--gray-200);
                        border-radius: 999px;
                        padding: 10px 14px;
                        font-size: 14px;
                        color: #111827;
                        outline: none;
                    }}
                    #chat-input:focus {{ border-color: #d1d5db; box-shadow: 0 0 0 3px rgba(245, 197, 99, 0.2); }}

                    .right-sidebar {{
                        border-left: 1px solid var(--gray-200);
                        background: #ffffff;
                        padding: 14px;
                        overflow-y: auto;
                        overflow-x: hidden;
                        display: flex;
                        flex-direction: column;
                        gap: 8px;
                        border-top-left-radius: 16px;
                        border-bottom-left-radius: 16px;
                        margin: 10px 10px 10px 0;
                        box-shadow: 0 6px 20px rgba(0,0,0,0.05);
                    }}
                    .right-sidebar h2 {{ margin: 0 0 8px; font-size: 22px; color: #111827; }}
                    .chat-history-list {{ display: grid; gap: 6px; }}
                    .log {{
                        text-align: left;
                        border: 1px solid transparent;
                        background: #ffffff;
                        border-radius: 10px;
                        padding: 10px;
                        cursor: pointer;
                        transition: 180ms ease;
                        display: grid;
                        gap: 6px;
                    }}
                    .log.active {{ border-color: #f0b84d; background: #fff7de; }}
                    .log:hover {{ border-color: #e5e7eb; background: #fafafa; }}
                    .log span {{ color: #111827; font-size: 15px; line-height: 1.25; }}
                    .log small {{ color: #6b7280; font-size: 12px; }}
                    .clear-history {{
                        margin-top: auto;
                        border: 1px solid var(--gray-200);
                        background: #ffffff;
                        color: #4b5563;
                        font-size: 13px;
                        border-radius: 8px;
                        padding: 8px 10px;
                        cursor: pointer;
                        text-align: center;
                    }}
                    .clear-history:hover {{ background: #f9fafb; border-color: #d1d5db; }}

                    .modal {{
                        position: fixed;
                        inset: 0;
                        background: rgba(17, 24, 39, 0.42);
                        display: grid;
                        place-items: center;
                        z-index: 1000;
                    }}
                    .hidden {{ display: none; }}
                    .modal-panel {{
                        width: min(420px, 90vw);
                        background: #ffffff;
                        border-radius: 14px;
                        padding: 18px;
                        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
                    }}
                    .modal-panel h3 {{ margin: 0; color: #111827; }}
                    .modal-panel p {{ margin: 10px 0 14px; color: #4b5563; font-size: 14px; line-height: 1.45; }}
                    .key-input {{
                        width: 100%;
                        border: 1px solid var(--gray-200);
                        border-radius: 9px;
                        padding: 10px 12px;
                        font-size: 14px;
                        color: #111827;
                        outline: none;
                    }}
                    .key-input:focus {{ box-shadow: 0 0 0 3px rgba(245, 197, 99, 0.2); border-color: #d1d5db; }}
                    .key-status-row {{ min-height: 18px; margin-top: 8px; }}
                    .key-status {{ color: #6b7280; font-size: 12px; }}
                    .modal-actions {{ display: flex; gap: 8px; justify-content: flex-end; }}
                    .modal-actions button {{ border: none; border-radius: 9px; padding: 9px 12px; cursor: pointer; font-weight: 600; }}
                    .modal-actions .ghost {{ background: #f3f4f6; color: #374151; }}
                    .modal-actions .solid {{ background: linear-gradient(135deg, var(--accent-1), var(--accent-2)); color: #111827; }}

                    @keyframes bounce {{
                        0%, 80%, 100% {{ transform: translateY(0); opacity: 0.45; }}
                        40% {{ transform: translateY(-3px); opacity: 1; }}
                    }}
                    @keyframes slideUp {{
                        from {{ transform: translateY(8px); opacity: 0; }}
                        to {{ transform: translateY(0); opacity: 1; }}
                    }}
                    @keyframes fadeIn {{
                        from {{ opacity: 0; }}
                        to {{ opacity: 1; }}
                    }}

                    @media (max-width: 1280px) {{
                        .shell {{ grid-template-columns: 56px 220px 1fr; }}
                        .right-sidebar {{ display: none; }}
                    }}
                    @media (max-width: 900px) {{
                        .shell {{ grid-template-columns: 1fr; }}
                        .icon-sidebar, .nav-sidebar, .right-sidebar {{ display: none; }}
                    }}
                    @media (max-width: 980px) {{
                        .shell {{ grid-template-columns: 64px 1fr; }}
                        .nav-sidebar {{ display: none; }}
                    }}
                </style>
            </head>
            <body>
                <div class="shell">
                    {icon_sidebar()}
                    {nav_sidebar()}
                    {main_area()}
                    {right_sidebar()}
                </div>
                {confirmation_modal()}
                {api_key_modal()}

                <script>
                    const GEMINI_API_KEY = {api_key_json};
                    const AI_REPLY_ICON = {ai_reply_icon_json};
                    const GEMINI_PROXY_URL = "http://127.0.0.1:8767/api/openrouter";
                    const messagesEl = document.getElementById("messages");
                    const chatInput = document.getElementById("chat-input");
                    const sendBtn = document.getElementById("send-btn");
                    const modal = document.getElementById("new-chat-modal");
                    const apiKeyModal = document.getElementById("api-key-modal");
                    const historyListEl = document.getElementById("chat-history-list");
                    const clearHistoryBtn = document.getElementById("clear-history-btn");
                    let runtimeApiKey = "";

                    const initialMessages = [];

                    let messages = [];
                    let conversations = [];
                    let activeConversationId = null;

                    function getTime() {{
                        const d = new Date();
                        let h = d.getHours();
                        const m = String(d.getMinutes()).padStart(2, "0");
                        const ap = h >= 12 ? "PM" : "AM";
                        h = h % 12 || 12;
                        return `${{h}}:${{m}} ${{ap}}`;
                    }}

                    function escapeHtml(text) {{
                        return String(text || "")
                            .replace(/&/g, "&amp;")
                            .replace(/</g, "&lt;")
                            .replace(/>/g, "&gt;")
                            .replace(/"/g, "&quot;")
                            .replace(/'/g, "&#39;");
                    }}

                    function parseScheduleCard(text) {{
                        var start = text.indexOf("[SCHEDULE]");
                        var end = text.indexOf("[/SCHEDULE]");
                        if (start === -1 || end === -1) return null;
                        var inner = text.slice(start + 10, end).trim();
                        var lines = inner.split("\\n");
                        var title = "", rows = [], note = "";
                        for (var i = 0; i < lines.length; i++) {{
                            var line = lines[i].trim();
                            if (line.indexOf("Title:") === 0) {{
                                title = line.slice(6).trim();
                            }} else if (line.indexOf("Row:") === 0) {{
                                var parts = line.slice(4).split("|");
                                rows.push({{ time: (parts[0] || "").trim(), desc: (parts[1] || "").trim() }});
                            }} else if (line.indexOf("Note:") === 0) {{
                                note = line.slice(5).trim();
                            }}
                        }}
                        return {{ title: title, rows: rows, note: note }};
                    }}

                    function scheduleCardTemplate(data, time) {{
                        var rowsHtml = "";
                        for (var i = 0; i < data.rows.length; i++) {{
                            rowsHtml += '<div class="card-row">'
                                + '<span>' + escapeHtml(data.rows[i].time) + '</span>'
                                + '<span>' + escapeHtml(data.rows[i].desc) + '</span>'
                                + '</div>';
                        }}
                        var noteHtml = data.note
                            ? '<div class="card-note"><strong>Note:</strong> ' + escapeHtml(data.note) + '</div>'
                            : "";
                        return '<div class="msg-row ai">'
                            + '<div class="avatar ai">AI</div>'
                            + '<div style="flex:1;min-width:0;">'
                            + '<article class="feeding-card">'
                            + '<h3>' + escapeHtml(data.title) + '</h3>'
                            + rowsHtml
                            + noteHtml
                            + '</article>'
                            + '<div class="time" style="padding-left:4px;margin-top:4px;">' + escapeHtml(time) + '</div>'
                            + '</div>'
                            + '</div>';
                    }}

                    function applyMarkdown(text) {{
                        return escapeHtml(text)
                            .replace(/\\*\\*(.*?)\\*\\*/g, "<strong>$1</strong>")
                            .replace(/\\*(.*?)\\*/g, "<em>$1</em>")
                            .replace(/\\n/g, "<br>");
                    }}

                    function rowTemplate(msg) {{
                        var isUser = msg.sender === "user";
                        if (!isUser) {{
                            var card = parseScheduleCard(msg.text);
                            if (card) return scheduleCardTemplate(card, msg.time);
                        }}
                        var safeText = applyMarkdown(msg.text);
                        var safeTime = escapeHtml(msg.time);
                        var avatarAi = !isUser ? '<div class="avatar ai">' + AI_REPLY_ICON + '</div>' : "";
                        var avatarUser = isUser ? '<div class="avatar user">ME</div>' : "";
                        var bubbleClass = isUser ? "user" : "ai";
                        var rowClass = isUser ? "user" : "ai";
                        return '<div class="msg-row ' + rowClass + '">'
                            + avatarAi
                            + '<div class="bubble ' + bubbleClass + '">'
                            + '<div>' + safeText + '</div>'
                            + '<div class="time">' + safeTime + '</div>'
                            + '</div>'
                            + avatarUser
                            + '</div>';
                    }}

                    function cloneMessages(items) {{
                        return (items || []).map((item) => ({{
                            sender: item.sender,
                            text: item.text,
                            time: item.time,
                        }}));
                    }}

                    function buildChatTitle(items) {{
                        const firstUser = (items || []).find((item) => item.sender === "user");
                        if (!firstUser || !firstUser.text) return "New chat";
                        const title = String(firstUser.text).trim();
                        if (!title) return "New chat";
                        return title.length > 34 ? `${{title.slice(0, 34)}}...` : title;
                    }}

                    function createConversation(seedMessages) {{
                        const convo = {{
                            id: `chat_${{Date.now()}}_${{Math.random().toString(36).slice(2, 7)}}`,
                            messages: cloneMessages(seedMessages || []),
                            title: buildChatTitle(seedMessages || []),
                            updatedAt: Date.now(),
                        }};
                        conversations.unshift(convo);
                        return convo;
                    }}

                    function saveActiveConversation() {{
                        const index = conversations.findIndex((item) => item.id === activeConversationId);
                        if (index === -1) return;
                        conversations[index].messages = cloneMessages(messages);
                        conversations[index].title = buildChatTitle(messages);
                        conversations[index].updatedAt = Date.now();
                        conversations.sort((a, b) => b.updatedAt - a.updatedAt);
                    }}

                    function renderHistory() {{
                        if (!historyListEl) return;
                        historyListEl.innerHTML = conversations.map((item) => {{
                            const activeClass = item.id === activeConversationId ? "active" : "";
                            const timeLabel = new Date(item.updatedAt).toLocaleTimeString([], {{ hour: "numeric", minute: "2-digit" }});
                            return `
                                <button class="log ${{activeClass}}" data-chat-id="${{item.id}}">
                                    <span>${{escapeHtml(item.title)}}</span>
                                    <small>${{escapeHtml(timeLabel)}}</small>
                                </button>
                            `;
                        }}).join("");

                        historyListEl.querySelectorAll(".log").forEach((btn) => {{
                            btn.addEventListener("click", () => {{
                                const id = btn.getAttribute("data-chat-id") || "";
                                const selected = conversations.find((item) => item.id === id);
                                if (!selected) return;
                                activeConversationId = selected.id;
                                messages = cloneMessages(selected.messages);
                                render();
                                renderHistory();
                            }});
                        }});
                    }}

                    function typingTemplate() {{
                        return '<div id="typing-row" class="msg-row ai">'
                            + '<div class="avatar ai">' + AI_REPLY_ICON + '</div>'
                            + '<div class="bubble ai">'
                            + '<div class="typing"><span></span><span></span><span></span></div>'
                            + '</div>'
                            + '</div>';
                    }}

                    function render() {{
                        messagesEl.innerHTML = messages.map(rowTemplate).join("");
                        const scrollEl = document.getElementById("chat-scroll");
                        if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
                    }}

                    function updateApiKeyStatus() {{
                        const statusEl = document.getElementById("api-key-status");
                        if (!statusEl) return;
                        statusEl.textContent = runtimeApiKey
                            ? "API key configured"
                            : "No API key configured";
                    }}

                    function initApiKey() {{
                        try {{
                            const saved = localStorage.getItem("petlio_gemini_api_key") || "";
                            runtimeApiKey = saved || GEMINI_API_KEY || "";
                        }} catch (_error) {{
                            runtimeApiKey = GEMINI_API_KEY || "";
                        }}
                        updateApiKeyStatus();
                    }}

                    async function callGemini(prompt) {{
                        const body = {{ prompt: prompt }};
                        if (runtimeApiKey) {{
                            body.apiKey = runtimeApiKey;
                        }}

                        let response;
                        try {{
                            response = await fetch(GEMINI_PROXY_URL, {{
                                method: "POST",
                                headers: {{
                                    "Content-Type": "application/json",
                                }},
                                body: JSON.stringify(body)
                            }});
                        }} catch (_error) {{
                            return "Could not reach API proxy. Keep Streamlit running and refresh the page.";
                        }}

                        let data = {{}};
                        try {{
                            data = await response.json();
                        }} catch (_error) {{
                            data = {{}};
                        }}
                        if (!response.ok) {{
                            const errorText = (data && typeof data.error === "string")
                                ? data.error
                                : (data && data.error && data.error.message)
                                    ? data.error.message
                                    : `Request failed with status ${{response.status}}`;
                            return `API error: ${{errorText}}`;
                        }}

                        const aiText = data && data.text ? String(data.text).trim() : "";
                        return aiText || "I could not generate a response. Please try rephrasing your question.";
                    }}

                    async function sendMessage(text) {{
                        if (!text || !text.trim()) return;
                        const clean = text.trim();

                        messages.push({{ sender: "user", text: clean, time: getTime() }});
                        render();
                        messagesEl.insertAdjacentHTML("beforeend", typingTemplate());
                        const scrollEl = document.getElementById("chat-scroll");
                        if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;

                        chatInput.value = "";
                        chatInput.disabled = true;
                        sendBtn.disabled = true;

                        try {{
                            const aiReply = await callGemini(clean);
                            messages.push({{
                                sender: "ai",
                                text: aiReply,
                                time: getTime()
                            }});
                            render();
                            saveActiveConversation();
                            renderHistory();
                        }} finally {{
                            const typing = document.getElementById("typing-row");
                            if (typing) typing.remove();
                            chatInput.disabled = false;
                            sendBtn.disabled = false;
                            chatInput.focus();
                        }}
                    }}

                    function bootstrap() {{
                        if (!messagesEl || !chatInput || !sendBtn || !modal) {{
                            return;
                        }}

                        initApiKey();

                        sendBtn.addEventListener("click", () => sendMessage(chatInput.value));
                        chatInput.addEventListener("keydown", (event) => {{
                            if (event.key === "Enter") sendMessage(chatInput.value);
                        }});

                        document.querySelectorAll(".quick-actions button").forEach((btn) => {{
                            btn.addEventListener("click", () => {{
                                chatInput.value = btn.dataset.prompt || "";
                                chatInput.focus();
                            }});
                        }});

                        const newChatBtn = document.getElementById("new-chat-btn");
                        const cancelBtn = document.getElementById("cancel-new-chat");
                        const confirmBtn = document.getElementById("confirm-new-chat");
                        const apiKeyBtn = document.getElementById("api-key-btn");
                        const apiKeyInput = document.getElementById("api-key-input");
                        const cancelApiKeyBtn = document.getElementById("cancel-api-key");
                        const saveApiKeyBtn = document.getElementById("save-api-key");
                        const clearApiKeyBtn = document.getElementById("clear-api-key");

                        const starter = createConversation(initialMessages);
                        activeConversationId = starter.id;
                        messages = cloneMessages(starter.messages);

                        if (newChatBtn) {{
                            newChatBtn.addEventListener("click", () => {{
                                modal.classList.remove("hidden");
                            }});
                        }}

                        if (cancelBtn) {{
                            cancelBtn.addEventListener("click", () => {{
                                modal.classList.add("hidden");
                            }});
                        }}

                        if (confirmBtn) {{
                            confirmBtn.addEventListener("click", () => {{
                                saveActiveConversation();
                                const newChat = createConversation([]);
                                activeConversationId = newChat.id;
                                messages = [];
                                render();
                                renderHistory();
                                modal.classList.add("hidden");
                                chatInput.focus();
                            }});
                        }}

                        if (clearHistoryBtn) {{
                            clearHistoryBtn.addEventListener("click", () => {{
                                conversations = [];
                                const fresh = createConversation([]);
                                activeConversationId = fresh.id;
                                messages = [];
                                render();
                                renderHistory();
                                chatInput.focus();
                            }});
                        }}

                        if (apiKeyBtn && apiKeyModal) {{
                            apiKeyBtn.addEventListener("click", () => {{
                                if (apiKeyInput) {{
                                    apiKeyInput.value = runtimeApiKey || "";
                                    apiKeyInput.focus();
                                }}
                                apiKeyModal.classList.remove("hidden");
                            }});
                        }}

                        if (cancelApiKeyBtn && apiKeyModal) {{
                            cancelApiKeyBtn.addEventListener("click", () => {{
                                apiKeyModal.classList.add("hidden");
                            }});
                        }}

                        if (saveApiKeyBtn && apiKeyInput && apiKeyModal) {{
                            saveApiKeyBtn.addEventListener("click", () => {{
                                runtimeApiKey = (apiKeyInput.value || "").trim();
                                try {{
                                    if (runtimeApiKey) {{
                                        localStorage.setItem("petlio_gemini_api_key", runtimeApiKey);
                                    }} else {{
                                        localStorage.removeItem("petlio_gemini_api_key");
                                    }}
                                }} catch (_error) {{}}
                                updateApiKeyStatus();
                                apiKeyModal.classList.add("hidden");
                            }});
                        }}

                        if (clearApiKeyBtn && apiKeyInput) {{
                            clearApiKeyBtn.addEventListener("click", () => {{
                                runtimeApiKey = "";
                                apiKeyInput.value = "";
                                try {{ localStorage.removeItem("petlio_gemini_api_key"); }} catch (_error) {{}}
                                updateApiKeyStatus();
                            }});
                        }}

                        render();
                        renderHistory();
                    }}

                    bootstrap();
                </script>
            </body>
        </html>
        """


def main() -> None:
    st.set_page_config(
        page_title=APP_NAME,
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={"Get help": None, "Report a bug": None, "About": None},
    )

    ensure_gemini_proxy()

    st.markdown(
        """
        <style>
            [data-testid="stHeader"],
            [data-testid="collapsedControl"],
            [data-testid="stSidebar"] { display: none !important; }
            [data-testid="stAppViewContainer"],
            [data-testid="stMainBlockContainer"],
            .block-container {
                margin: 0 !important;
                padding: 0 !important;
                max-width: 100% !important;
                overflow: hidden !important;
            }
            iframe {
                width: 100% !important;
                height: 100vh !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    components.html(build_html(api_key=api_key), height=900, scrolling=False)


if __name__ == "__main__":
    main()
