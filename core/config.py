import os
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass
class Config:
    """Application configuration from environment variables."""
    
    # LLM - OpenRouter (required)
    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_model: str
    
    # RAG
    chroma_db_path: str
    rag_top_k: int

    # Supabase (optional — persistent pgvector RAG store)
    supabase_url: str
    supabase_key: str
    
    # Langfuse (optional)
    langfuse_secret_key: str
    langfuse_public_key: str
    langfuse_base_url: str
    
    # Security
    max_input_chars: int
    rate_limit_per_minute: int

    def __init__(self):
        """Load configuration from environment (.env or system env vars)."""
        load_dotenv()

        def _clean(name: str, default: str = "") -> str:
            # Strip whitespace AND surrounding quote chars — Streamlit Cloud's
            # TOML paste box occasionally leaves embedded quotes in the value.
            return os.getenv(name, default).strip().strip('"').strip("'").strip()

        # Required: OpenRouter API Key. Do NOT raise here — the UI surfaces
        # the missing-key state inline so the user can fix Streamlit secrets
        # without the whole app crashing.
        self.openrouter_api_key = _clean("OPENROUTER_API_KEY")

        # OpenRouter configuration
        self.openrouter_base_url = _clean("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.openrouter_model = _clean("OPENROUTER_MODEL", "openai/gpt-oss-120b:free")
        
        # RAG configuration
        self.chroma_db_path = _clean("CHROMA_DB_PATH", "./chroma_db")
        self.rag_top_k = int(_clean("RAG_TOP_K", "3") or "3")

        # Supabase configuration (optional — enables persistent pgvector RAG)
        self.supabase_url = _clean("SUPABASE_URL")
        self.supabase_key = _clean("SUPABASE_KEY")

        # Langfuse configuration (optional)
        self.langfuse_secret_key = _clean("LANGFUSE_SECRET_KEY")
        self.langfuse_public_key = _clean("LANGFUSE_PUBLIC_KEY")
        self.langfuse_base_url = _clean("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

        # Security configuration
        self.max_input_chars = int(_clean("MAX_INPUT_CHARS", "4000") or "4000")
        self.rate_limit_per_minute = int(_clean("RATE_LIMIT_PER_MINUTE", "20") or "20")

    def is_openrouter_configured(self) -> bool:
        """True only if a non-placeholder API key is set."""
        k = self.openrouter_api_key
        return bool(k) and "REPLACE_ME" not in k and "YOUR_KEY" not in k
    
    def is_supabase_enabled(self) -> bool:
        """True when a Supabase pgvector backend is configured."""
        return bool(self.supabase_url and self.supabase_key
                    and "REPLACE_ME" not in self.supabase_url)

    def is_langfuse_enabled(self) -> bool:
        """Check if Langfuse tracing is configured."""
        return bool(self.langfuse_secret_key and self.langfuse_public_key)

    @property
    def langfuse_host(self) -> str:
        """Alias for langfuse_base_url to maintain compatibility."""
        return self.langfuse_base_url
