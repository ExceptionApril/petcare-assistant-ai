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
        
        # Required: OpenRouter API Key
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not self.openrouter_api_key:
            raise EnvironmentError("Missing required: OPENROUTER_API_KEY")
        
        # OpenRouter configuration
        self.openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
        self.openrouter_model = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip()
        
        # RAG configuration
        self.chroma_db_path = os.getenv("CHROMA_DB_PATH", "./chroma_db").strip()
        self.rag_top_k = int(os.getenv("RAG_TOP_K", "3"))
        
        # Langfuse configuration (optional)
        self.langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
        self.langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        self.langfuse_base_url = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com").strip()
        
        # Security configuration
        self.max_input_chars = int(os.getenv("MAX_INPUT_CHARS", "4000"))
        self.rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
    
    def is_langfuse_enabled(self) -> bool:
        """Check if Langfuse tracing is configured."""
        return bool(self.langfuse_secret_key and self.langfuse_public_key)

    @property
    def langfuse_host(self) -> str:
        """Alias for langfuse_base_url to maintain compatibility."""
        return self.langfuse_base_url
