# 🐾 Petlio — AI Pet Care Assistant

Petlio is a friendly, agentic pet-care chatbot built with Streamlit. It answers
questions about pet health, nutrition, training, grooming, and behaviour —
grounding its answers in your own uploaded documents when they help, searching
the web for fresh information when they don't, and falling back to its
pet-care knowledge otherwise.

Meet **Petcat**, the pixel-art mascot that walks, blinks, and wags its tail
while Petlio thinks.

## Features

- **Agentic RAG** — a retrieve → grade → rewrite → answer loop. Retrieved
  document chunks are graded for relevance by the model; weak results trigger a
  rewritten query and re-retrieval, and irrelevant documents are skipped in
  favour of a web search.
- **Robust web search** — DuckDuckGo via the maintained `ddgs` client (with a
  legacy fallback), used automatically when the knowledge base has nothing
  useful, or on demand via the 🌐 toggle.
- **Document upload (RAG)** — drop in a PDF or TXT and Petlio indexes it into a
  vector store using ChromaDB's built-in ONNX MiniLM embeddings (no external
  embedding service required).
- **Pluggable vector store** — local **ChromaDB** for development, or
  **Supabase** (Postgres + pgvector) for persistence on Streamlit Cloud.
- **Observability with Langfuse** — every chat turn is traced as a single
  session-grouped trace covering RAG retrieval, agent steps, and the LLM
  generation (Langfuse v3/v4 OTel API).
- **Streaming responses** with a live reasoning trace so you can see each step.
- **Security guardrails** — prompt-injection detection, an immutable system
  prompt, output filtering, and rate limiting.
- **Polished one-page UI** — the header, chat feed, and composer fit a single
  viewport; only the message feed scrolls. Responsive down to mobile.

## Tech stack

| Concern         | Choice                                            |
|-----------------|---------------------------------------------------|
| UI              | Streamlit                                         |
| LLM             | OpenRouter (free models) via the OpenAI SDK       |
| Embeddings / RAG| ChromaDB + built-in ONNX MiniLM (384-dim)         |
| Persistent store| Supabase (Postgres + pgvector), optional          |
| Web search      | `ddgs` (DuckDuckGo)                               |
| Observability   | Langfuse                                          |
| Markdown        | `markdown-it-py`                                  |

## Project structure

```
app.py                # Streamlit app: UI, chat loop, Petcat mascot
agent_engine.py       # ReActAgent: agentic RAG + web-search reasoning loop
llm_client.py         # OpenRouter client + streaming helper
rag_engine.py         # ChromaDB RAG engine + get_rag_engine() backend selector
rag_common.py         # Shared text extraction / chunking / embedding helpers
supabase_store.py     # Supabase (pgvector) vector store backend
langfuse_tracer.py    # Langfuse tracing wrapper (per-turn trace spans)
prompts/              # System-prompt builder (+ Langfuse prompt management)
core/                 # Config, security guardrails, session helpers
data/                 # Sample pet-care documents
tests/                # pytest suite (agent + security)
supabase_schema.sql   # SQL migration for the Supabase backend
SUPABASE_SETUP.md     # Supabase setup guide
```

## Getting started

### 1. Install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in the project root (or use `.streamlit/secrets.toml` on
Streamlit Cloud — see `.streamlit/secrets.toml.example`):

```ini
# Required — get a free key at https://openrouter.ai/keys
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-oss-120b:free   # optional; sensible default used otherwise

# Optional — observability (https://langfuse.com)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com

# Optional — persistent vector store (otherwise local ChromaDB is used)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-or-service-key
```

Only `OPENROUTER_API_KEY` is required. Langfuse and Supabase are optional — the
app degrades gracefully without them (tracing disabled, local ChromaDB store).

### 3. Run

```bash
streamlit run app.py
```

The app opens at <http://localhost:8501>.

## Testing

```bash
pytest tests/ -q
```

## Deployment (Streamlit Cloud)

1. Push this repo to GitHub.
2. Create a new app on [Streamlit Community Cloud](https://share.streamlit.io)
   pointing at `app.py`.
3. Add your keys under **Manage app → Settings → Secrets** (same names as the
   `.env` above).
4. For persistence across restarts, configure Supabase and run
   `supabase_schema.sql` — see [`SUPABASE_SETUP.md`](SUPABASE_SETUP.md).

---

> ℹ️ Petlio is an educational project. Always confirm any health or medical
> advice with a qualified veterinarian.
