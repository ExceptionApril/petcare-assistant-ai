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
    "openai/gpt-oss-120b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "openai/gpt-oss-20b:free",
    "meta-llama/llama-3.2-3b-instruct:free",
]


def stream_completion(client: OpenAI, messages: list, model: str,
                      max_tokens: int = 1200, temperature: float = 0.7):
    """Stream a chat completion, yielding text chunks as they arrive."""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        stream=True,
    )
    for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
