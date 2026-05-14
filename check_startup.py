import sys, os, traceback
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

errors = []

def check(name, fn):
    print(f"[{name}]")
    try:
        fn()
    except Exception as e:
        print(f"  ERROR: {e}")
        errors.append(name)

def chk_config():
    from core.config import Config
    c = Config()
    print("  openrouter key set:", bool(c.openrouter_api_key))

def chk_security():
    from core.security import sanitize_for_llm, rate_limit_check, SecurityViolation, SYSTEM_PROMPT_WRAPPER
    print("  OK, prompt wrapper len:", len(SYSTEM_PROMPT_WRAPPER))

def chk_rag_loader():
    from rag.loader import load_documents, get_embed_model
    print("  OK")

def chk_rag_index():
    from rag.index import build_or_load_index
    print("  OK")

def chk_rag_retriever():
    from rag.retriever import get_query_engine, rag_query
    print("  OK")

def chk_agent_tools():
    from agent.tools import web_search_tool, pet_weight_calculator_tool, medication_schedule_tool, get_rag_tool
    print("  OK")

def chk_agent_engine():
    from agent.engine import build_agent, run_agent
    print("  OK")

def chk_prompts():
    from prompts.system import build_system_prompt
    sp = build_system_prompt("Dog", "Adult", True, True)
    print("  prompt len:", len(sp))

def chk_langfuse():
    from prompts.langfuse_client import LangfuseTracer
    print("  OK")

def chk_llm():
    from llama_index.llms.openai import OpenAI as LO
    key = os.getenv("OPENROUTER_API_KEY", "")
    llm = LO(model="gpt-4o-mini", api_key=key, api_base="https://openrouter.ai/api/v1")
    print("  model:", llm.model)

def chk_global_llm():
    from llama_index.core import Settings
    from llama_index.llms.openai import OpenAI as LO
    key = os.getenv("OPENROUTER_API_KEY", "")
    Settings.llm = LO(model="gpt-4o-mini", api_key=key, api_base="https://openrouter.ai/api/v1")
    print("  Settings.llm model:", Settings.llm.model)

def chk_rag_full():
    from llama_index.core import Settings
    from llama_index.llms.openai import OpenAI as LO
    from rag.index import build_or_load_index
    from rag.retriever import get_query_engine
    key = os.getenv("OPENROUTER_API_KEY", "")
    Settings.llm = LO(model="gpt-4o-mini", api_key=key, api_base="https://openrouter.ai/api/v1")
    idx = build_or_load_index("./data", "./.chroma_db")
    qe = get_query_engine(idx, top_k=2)
    print("  RAG query engine built OK")

checks = [
    ("Config", chk_config),
    ("Security", chk_security),
    ("RAG loader", chk_rag_loader),
    ("RAG index", chk_rag_index),
    ("RAG retriever", chk_rag_retriever),
    ("Agent tools", chk_agent_tools),
    ("Agent engine", chk_agent_engine),
    ("Prompts", chk_prompts),
    ("Langfuse", chk_langfuse),
    ("LLM (OpenRouter)", chk_llm),
    ("Global LLM config", chk_global_llm),
    ("RAG full pipeline", chk_rag_full),
]

for name, fn in checks:
    check(name, fn)

print()
if errors:
    print("FAILED:", errors)
    sys.exit(1)
else:
    print("ALL CHECKS PASSED - ready to launch!")
