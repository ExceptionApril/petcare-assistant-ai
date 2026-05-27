# Petlio AI - Presentation Report

## 1. Design Decisions: RAG vs. Agentic AI

When designing Petlio AI, we opted for a **hybrid architecture** that leverages both Retrieval-Augmented Generation (RAG) and Agentic AI capabilities to provide the most accurate and reliable pet care assistance.

### RAG (Retrieval-Augmented Generation)
* **Purpose:** Allows users to interact with their own specific data, such as veterinary records or specialized pet care manuals. 
* **Implementation:** We implemented RAG using **ChromaDB** with built-in ONNX embeddings for lightweight, local vector storage, and **PyPDF** for document parsing. 
* **Why RAG?** RAG grounds the LLM in factual, user-provided context, effectively eliminating hallucinations when dealing with specific medical history or explicit care instructions.

### Agentic AI (ReAct Reasoning Loop)
* **Purpose:** Enables the assistant to fetch real-time, up-to-date information that the foundational model might not know (e.g., recent product recalls, latest news).
* **Implementation:** We built a custom **ReAct-style (Reason + Act) Agent** that can dynamically decide when to answer directly and when to invoke external tools. We integrated **DuckDuckGo Search** as the primary tool for web browsing.
* **Why Agentic AI?** It provides autonomy. Instead of hardcoding when to search, the LLM analyzes the user's intent and dynamically pulls fresh data from the internet.

### Models and Frameworks
* **Frontend:** **Streamlit** was chosen for its rapid prototyping capabilities, allowing us to build a reactive, chat-based UI quickly.
* **LLM Provider:** We utilized **OpenRouter** (via the OpenAI Python SDK) to access a fallback chain of powerful open-source models: `meta-llama/llama-3.3-70b-instruct`, `openai/gpt-oss-120b`, and `meta-llama/llama-3.2-3b-instruct`. This ensures high availability and cost efficiency.
* **Observability:** **Langfuse** (v3+ OTel API) is integrated deeply for tracing, debugging, and prompt management.

---

## 2. Prompt Engineering and Management

Prompt engineering was critical for maintaining the persona and ensuring safety (guardrails) within the application.

### System Prompts & Guardrails
* **Immutable Persona:** The core system prompt enforces the "Petlio" persona—a helpful, honest, and safe pet care assistant. 
* **Domain Restriction:** We implemented strict guardrails using both prompt instructions and code-level validation. The system intercepts prompts using known injection patterns (e.g., "ignore previous instructions") and validates that queries contain pet-related keywords (`_pet_keywords` set) before processing.
* **ReAct Prompts:** The agentic loop utilizes a specialized prompt that forces the LLM to output specific syntax (`SEARCH: [query]` or `ANSWER: [response]`), creating a reliable parsing mechanism for tool execution.

### Langfuse Prompt Management
* Instead of hardcoding all prompts in the codebase, we integrated **Langfuse Prompt Management**. 
* The `langfuse_tracer.py` module uses `Langfuse.get_prompt()` to dynamically fetch the latest system prompts from the Langfuse cloud.
* **Benefits:** This allows non-technical team members to iterate on prompt wording, adjust the persona, or add new behavioral guidelines without requiring a code deployment or app restart.

---

## 3. Functional Demo

* **Live Streamlit App:** [Insert Streamlit Share URL here]
* **GitHub Repository:** [Insert GitHub Repo URL here]

*(Note: To run locally, clone the repository, install `requirements.txt`, configure `.env` with `OPENROUTER_API_KEY` and Langfuse credentials, and run `streamlit run app.py`)*
