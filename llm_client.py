"""Direct OpenAI SDK client configured for OpenRouter."""
import os
from openai import OpenAI
from core.config import Config


def get_llm_client(config: Config) -> OpenAI:
    """
    Initialize OpenAI client pointed at OpenRouter.
    Uses free models only from OpenRouter.
    """
    return OpenAI(
        api_key=config.openrouter_api_key,
        base_url=config.openrouter_base_url,
        default_headers={
            "HTTP-Referer": "http://localhost:8501",
            "X-Title": "Petlio AI Chatbot"
        }
    )


def create_message_payload(
    system_prompt: str,
    conversation_history: list,
    user_message: str,
    model: str = "",
    max_tokens: int = 600,
    temperature: float = 0.7,
    stream: bool = True
):
    """Create a chat completion payload."""
    messages = [
        {"role": "system", "content": system_prompt},
        *conversation_history,
        {"role": "user", "content": user_message}
    ]
    
    return {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream
    }


FALLBACK_MODELS = [
    "meta-llama/llama-3.3-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-3-4b-it:free"
]
