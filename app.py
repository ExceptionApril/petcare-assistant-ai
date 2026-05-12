import os
import uuid
import streamlit as st
import time

from design import apply_design, petlio_logo_svg

from core.config import Config
from core.security import sanitize_for_llm, rate_limit_check, SecurityViolation
from rag.index import build_or_load_index
from rag.retriever import get_query_engine
from agent.engine import build_agent, run_agent
from agent.tools import web_search_tool, pet_weight_calculator_tool, medication_schedule_tool, get_rag_tool
from prompts.system import build_system_prompt
from prompts.langfuse_client import LangfuseTracer

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
    if "initialized" not in st.session_state:
        with st.spinner("Initializing Petlio AI..."):
            config = Config()
            st.session_state["config"] = config
            
            # Load RAG
            index = build_or_load_index(config.rag_data_dir, config.chroma_persist_dir)
            query_engine = get_query_engine(index, top_k=config.rag_top_k)
            st.session_state["rag_engine"] = query_engine
            
            # Setup tracer
            tracer = LangfuseTracer(config)
            st.session_state["tracer"] = tracer
            
            # Agent is built per-request to pick up the latest system prompt (based on sidebar toggles)
            # But we can store tools
            st.session_state["agent_tools"] = [
                web_search_tool,
                pet_weight_calculator_tool,
                medication_schedule_tool,
                get_rag_tool(query_engine)
            ]
            
            st.session_state["messages"] = []
            st.session_state["session_id"] = str(uuid.uuid4())
            st.session_state["initialized"] = True

def handle_user_message(user_input: str):
    """
    1. Rate limit check → if throttled: show warning, return early
    2. sanitize_for_llm(user_input) → if SecurityViolation: show error message, return early
    3. Start Langfuse trace
    4. Run agent (which internally uses RAG tool + web search + calculators)
    5. Log generation to Langfuse
    6. Append (user_msg, assistant_msg, tools_used) to session_state["messages"]
    7. End Langfuse trace
    """
    session_id = st.session_state["session_id"]
    config = st.session_state["config"]
    tracer = st.session_state["tracer"]
    
    # 1. Rate limit check
    if not rate_limit_check(session_id, config.rate_limit_per_minute):
        st.warning("You are sending messages too quickly. Please wait a moment.")
        return
        
    # 2. Sanitize input
    try:
        sanitized_input = sanitize_for_llm(user_input, st.session_state["messages"])
    except SecurityViolation as e:
        st.error("I can only help with pet care questions.")
        return
        
    # Append user message immediately for UI
    st.session_state["messages"].append({"role": "user", "content": sanitized_input})
    
    # 3. Start Langfuse trace
    trace_id = tracer.start_trace(
        session_id=session_id,
        user_message=sanitized_input,
        metadata={"pet_type": st.session_state.get("pet_type")}
    )
    
    # Build dynamic agent
    pet_type = st.session_state.get("pet_type", "Dog")
    pet_age = st.session_state.get("pet_age", "Adult")
    use_rag = st.session_state.get("use_rag", True)
    use_agent_tools = st.session_state.get("use_agent_tools", True)
    debug_mode = st.session_state.get("debug_mode", False)
    
    system_prompt = build_system_prompt(pet_type, pet_age, use_rag, use_agent_tools)
    
    # Choose tools based on toggles
    active_tools = []
    if use_agent_tools:
        # All tools including RAG
        active_tools = st.session_state["agent_tools"]
    elif use_rag:
        # Just RAG tool
        active_tools = [get_rag_tool(st.session_state["rag_engine"])]
        
    # If using OpenAI, we need to pass the client/model
    from llama_index.llms.openai import OpenAI as LlamaOpenAI
    # For openrouter fallback:
    api_key = config.gemini_api_key or config.openrouter_api_key
    # Just use standard OpenAI for agent
    llm = LlamaOpenAI(model="gpt-4o-mini", api_key=api_key)
    
    # Actually wait, prompt uses `google-generativeai`, `anthropic`, `openai`
    # Let's use OpenRouter format or default OpenAI
    # Or just default LlamaOpenAI with whatever key is available.
    if config.gemini_api_key and len(config.gemini_api_key) > 5:
        # We can use Gemini
        from llama_index.llms.gemini import Gemini
        llm = Gemini(model="models/gemini-2.0-flash", api_key=config.gemini_api_key)
    elif config.openrouter_api_key:
        llm = LlamaOpenAI(model="openai/gpt-4o-mini", api_key=config.openrouter_api_key, api_base="https://openrouter.ai/api/v1")
    else:
        st.error("No API key configured.")
        return

    agent = build_agent(active_tools, llm, system_prompt, debug_mode)
    
    # 4. Run agent
    start_time = time.time()
    with st.spinner("Thinking..."):
        response_text, tools_used = run_agent(agent, sanitized_input, st.session_state["messages"])
    latency_ms = int((time.time() - start_time) * 1000)
    
    # 5. Log generation
    tracer.log_generation(
        trace_id=trace_id,
        model=llm.metadata.model_name,
        prompt=system_prompt + "\\n\\nUser: " + sanitized_input,
        completion=response_text,
        latency_ms=latency_ms,
        tools_used=tools_used
    )
    
    # 6. Append to messages
    st.session_state["messages"].append({
        "role": "assistant", 
        "content": response_text,
        "tools": tools_used,
        "sources": [] # We can't cleanly extract RAG sources from agent response if it didn't include them, but the prompt says rag_query appends '📚 Sources: ...'
    })
    
    # 7. End trace
    tracer.end_trace(trace_id, response_text)


def render_message_bubble(msg):
    is_user = msg["role"] == "user"
    avatar_class = "user" if is_user else "ai"
    bubble_class = "user" if is_user else "ai"
    avatar_content = "ME" if is_user else "AI"
    content = msg["content"].replace("\\n", "<br>")
    
    html = f'''
    <div class="message {avatar_class}">
        <div class="message-avatar {avatar_class}">{avatar_content}</div>
        <div class="message-bubble {bubble_class}">
            {content}
        </div>
    </div>
    '''
    st.markdown(html, unsafe_allow_html=True)
    
    if not is_user and st.session_state.get("debug_mode", False) and msg.get("tools"):
        with st.expander("Debug Info: Tools Used"):
            st.write(msg["tools"])

def main():
    st.set_page_config(page_title="Petlio AI Assistant", layout="wide")
    apply_design()
    
    initialize_session()
    
    # Sidebar Controls
    with st.sidebar:
        st.header("Pet Context")
        st.session_state["pet_type"] = st.selectbox("Pet Type", ["Dog", "Cat", "Rabbit", "Bird", "Other"], index=0)
        st.session_state["pet_age"] = st.selectbox("Pet Age", ["Baby", "Young", "Adult", "Senior"], index=2)
        
        st.header("Features")
        st.session_state["use_rag"] = st.toggle("Enable Knowledge Base", value=True)
        st.session_state["use_agent_tools"] = st.toggle("Enable Smart Tools", value=True)
        st.session_state["debug_mode"] = st.toggle("Debug Mode", value=False)
        
        # We don't implement API Key input setting config here unless requested, 
        # but the prompt says: "API Key input (existing behavior, keep it)"
        api_key_input = st.text_input("API Key (Gemini or OpenRouter)", type="password")
        if api_key_input:
            if "openrouter" in api_key_input.lower() or api_key_input.startswith("sk-or-"):
                st.session_state["config"].openrouter_api_key = api_key_input
            else:
                st.session_state["config"].gemini_api_key = api_key_input
                
        if st.button("Clear History"):
            st.session_state["messages"] = []
            st.session_state["session_id"] = str(uuid.uuid4())
            st.rerun()

    # Chat Display
    st.markdown('<div class="chat-messages">', unsafe_allow_html=True)
    for msg in st.session_state["messages"]:
        render_message_bubble(msg)
    st.markdown('</div>', unsafe_allow_html=True)
        
    # Input
    user_input = st.chat_input("Ask me anything about pet care...")
    if user_input:
        handle_user_message(user_input)
        st.rerun()

if __name__ == "__main__":
    main()
