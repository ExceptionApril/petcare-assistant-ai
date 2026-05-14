import streamlit as st
import uuid
import time
import os
from llama_index.llms.openai import OpenAI as LlamaOpenAI

from core.config import Config
from core.session import (
    is_initialized, mark_initialized, get_messages, append_message,
    KEY_SESSION_ID, KEY_RAG_ENGINE, KEY_AGENT, KEY_TRACER, KEY_CONFIG
)
from core.security import sanitize_for_llm, rate_limit_check, SecurityViolation
from prompts.system import build_system_prompt
from prompts.langfuse_client import LangfuseTracer
from rag.index import build_or_load_index
from rag.retriever import get_query_engine
from agent.tools import web_search_tool, pet_weight_calculator_tool, medication_schedule_tool, get_rag_tool
from agent.engine import build_agent, run_agent
from design import apply_design, petlio_logo_svg

st.set_page_config(page_title="Petlio AI Assistant", layout="wide")

# Apply the design system CSS
apply_design()

def initialize_session():
    """
    If st.session_state not yet initialized:
    1. Load Config()
    2. Build/load RAG index → store in session_state["rag_engine"]
    3. Build agent → store in session_state["agent"]
    4. Initialize LangfuseTracer → store in session_state["tracer"]
    5. Set session_state["messages"] = []
    6. Set session_state["session_id"] = uuid4()
    Show a st.spinner("Initializing Petlio AI...") during this step.
    """
    if not is_initialized():
        st.session_state[KEY_SESSION_ID] = str(uuid.uuid4())
        get_messages() # Initializes empty list
        
        with st.spinner("Initializing Petlio AI..."):
            config = Config()
            st.session_state[KEY_CONFIG] = config
            
            # Langfuse
            tracer = LangfuseTracer(config)
            st.session_state[KEY_TRACER] = tracer
            
            # RAG
            try:
                index = build_or_load_index(config.rag_data_dir, config.chroma_persist_dir)
                rag_engine = get_query_engine(index, top_k=config.rag_top_k)
                st.session_state[KEY_RAG_ENGINE] = rag_engine
            except Exception as e:
                st.error(f"Failed to load RAG index: {e}")
                st.session_state[KEY_RAG_ENGINE] = None

            mark_initialized()

def get_llm(api_key_override: str = ""):
    config: Config = st.session_state[KEY_CONFIG]
    api_key = api_key_override or config.openrouter_api_key or config.gemini_api_key
    # Final report says: Gemini 2.0 Flash via OpenRouter
    return LlamaOpenAI(
        model="google/gemini-2.0-flash-001", # Use standard openrouter string for gemini flash
        api_key=api_key,
        api_base="https://openrouter.ai/api/v1",
    )

def handle_user_message(user_input: str, pet_type: str, pet_age: str, use_rag: bool, use_agent: bool, debug_mode: bool, api_key: str):
    """
    1. Rate limit check → if throttled: show warning, return early
    2. sanitize_for_llm(user_input) → if SecurityViolation: show error message, return early
    3. Start Langfuse trace
    4. Run agent (which internally uses RAG tool + web search + calculators)
    5. Log generation to Langfuse
    6. Append (user_msg, assistant_msg, tools_used) to session_state["messages"]
    7. End Langfuse trace
    """
    session_id = st.session_state[KEY_SESSION_ID]
    tracer: LangfuseTracer = st.session_state[KEY_TRACER]
    
    # 1. Rate limit
    if not rate_limit_check(session_id):
        st.warning("Rate limit exceeded. Please wait a minute before sending another message.")
        return
        
    # 2. Security
    try:
        sanitized = sanitize_for_llm(user_input, get_messages())
    except SecurityViolation as e:
        st.error(str(e))
        return
        
    append_message("user", sanitized)
    
    # 3. Langfuse
    trace_id = tracer.start_trace(
        session_id=session_id, 
        user_message=sanitized,
        metadata={"pet_type": pet_type, "pet_age": pet_age, "use_rag": use_rag, "use_agent": use_agent}
    )
    
    # Build Agent Dynamically based on current settings
    system_prompt = build_system_prompt(pet_type, pet_age, use_rag, use_agent)
    llm = get_llm(api_key)
    
    tools = []
    if use_agent:
        tools.extend([web_search_tool, pet_weight_calculator_tool, medication_schedule_tool])
    if use_rag and st.session_state[KEY_RAG_ENGINE]:
        tools.append(get_rag_tool(st.session_state[KEY_RAG_ENGINE]))
        
    agent = build_agent(tools, llm, system_prompt, debug_mode=debug_mode)
    
    # 4. Run Agent
    start_time = time.time()
    with st.spinner("Thinking..."):
        response_text, tools_used = run_agent(agent, sanitized, get_messages())
    latency_ms = int((time.time() - start_time) * 1000)
    
    # 5. Log Generation
    tracer.log_generation(
        trace_id=trace_id,
        model="gemini-2.0-flash",
        prompt=system_prompt,
        completion=response_text,
        latency_ms=latency_ms,
        tools_used=tools_used
    )
    
    # 6. Append assistant message
    append_message("assistant", response_text, tools_used)
    
    # 7. End Trace
    tracer.end_trace(trace_id, response_text)

def render_chat_messages(debug_mode: bool):
    """Render messages using the design.py HTML structure via st.markdown"""
    messages = get_messages()
    
    if not messages:
        st.markdown(
            '<div class="empty-chat"><p><b>Welcome to Petlio!</b></p><p>Ask me anything about pet health, nutrition, or care.</p></div>', 
            unsafe_allow_html=True
        )
        return

    html = '<div class="chat-messages">'
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        
        if role == "user":
            html += f'''
            <div class="message user">
                <div class="message-bubble user">{content}</div>
                <div class="message-avatar user">U</div>
            </div>
            '''
        else:
            tools_used = msg.get("tools_used", [])
            tools_html = ""
            if debug_mode and tools_used:
                tools_list = ", ".join(tools_used)
                tools_html = f'<div style="font-size:0.75rem; color:#9ca3af; margin-top:0.5rem;">🔧 Tools used: {tools_list}</div>'
                
            html += f'''
            <div class="message ai">
                <div class="message-avatar ai"><img src="{petlio_logo_svg()}" style="width:20px;height:20px;"></div>
                <div class="message-bubble ai">{content}{tools_html}</div>
            </div>
            '''
    html += '</div>'
    
    st.markdown(html, unsafe_allow_html=True)


def main():
    try:
        initialize_session()
    except Exception as e:
        st.error(f"Startup error: {e}")
        st.stop()
        
    # 8.3 Sidebar Controls
    with st.sidebar:
        st.title("🐾 Petlio Settings")
        
        pet_type = st.selectbox("Pet Type", ["Dog", "Cat", "Rabbit", "Bird", "Other"])
        pet_age = st.selectbox("Pet Age", ["0-6 months", "6-12 months", "1-3 years", "3-7 years", "7+ years"])
        
        st.divider()
        use_rag = st.toggle("Enable Knowledge Base (RAG)", value=True)
        use_agent = st.toggle("Enable Smart Tools", value=True)
        debug_mode = st.toggle("Debug Mode", value=False)
        
        st.divider()
        api_key = st.text_input("API Key (Optional override)", type="password", help="Leave blank to use .env key")

    # Main Chat Interface
    st.markdown("""
        <div class="chat-header">
            <div class="header-content">
                <div class="header-left">
                    <div class="header-avatar"><img src="{logo}" style="width:24px;height:24px;"></div>
                    <div>
                        <div class="header-title">Petlio AI Assistant</div>
                        <div class="header-subtitle">Your friendly pet care companion</div>
                    </div>
                </div>
            </div>
        </div>
    """.format(logo=petlio_logo_svg()), unsafe_allow_html=True)
    
    # Message display
    render_chat_messages(debug_mode)
    
    # Input
    user_input = st.chat_input("Ask me anything about pet care...")
    if user_input:
        handle_user_message(user_input, pet_type, pet_age, use_rag, use_agent, debug_mode, api_key)
        st.rerun()

if __name__ == "__main__":
    main()
