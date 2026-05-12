import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
import streamlit as st

@dataclass
class Config:
    # LLM
    gemini_api_key: str
    openrouter_api_key: str
    
    # RAG
    chroma_persist_dir: str
    rag_data_dir: str
    rag_top_k: int
    
    # Agentic
    enable_web_search: bool
    
    # Langfuse
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_host: str
    
    # Security
    max_input_chars: int
    rate_limit_per_minute: int

    def __init__(self):
        # Load local .env file if it exists
        load_dotenv()
        
        self.gemini_api_key = self._get_env_or_secret("GEMINI_API_KEY", required=True)
        self.openrouter_api_key = self._get_env_or_secret("OPENROUTER_API_KEY", default="")
        
        self.chroma_persist_dir = self._get_env_or_secret("CHROMA_PERSIST_DIR", default="./.chroma_db")
        self.rag_data_dir = self._get_env_or_secret("RAG_DATA_DIR", default="./data")
        self.rag_top_k = int(self._get_env_or_secret("RAG_TOP_K", default="3"))
        
        self.enable_web_search = self._get_env_or_secret("ENABLE_WEB_SEARCH", default="true").lower() in ("true", "1", "yes")
        
        self.langfuse_public_key = self._get_env_or_secret("LANGFUSE_PUBLIC_KEY", default="")
        self.langfuse_secret_key = self._get_env_or_secret("LANGFUSE_SECRET_KEY", default="")
        self.langfuse_host = self._get_env_or_secret("LANGFUSE_HOST", default="https://cloud.langfuse.com")
        
        self.max_input_chars = int(self._get_env_or_secret("MAX_INPUT_CHARS", default="4000"))
        self.rate_limit_per_minute = int(self._get_env_or_secret("RATE_LIMIT_PER_MINUTE", default="20"))

    def _get_env_or_secret(self, key: str, default: str = "", required: bool = False) -> str:
        """
        Check Streamlit secrets first, then OS environment (which includes .env).
        Raises EnvironmentError if required and not found.
        """
        value = None
        
        # 1. Try Streamlit Secrets first
        try:
            if key in st.secrets:
                value = st.secrets[key]
        except FileNotFoundError:
            pass # No secrets file, that's fine
            
        # 2. Try OS Environment
        if value is None:
            value = os.environ.get(key)
            
        # 3. Validation
        if value is None or str(value).strip() == "":
            if required:
                raise EnvironmentError(f"Missing required configuration key: {key}")
            return default
            
        return str(value)
