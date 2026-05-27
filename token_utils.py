"""Token counting and optimization utilities."""
import tiktoken

# Token encoding for cl100k_base (used by llama and most open models)
try:
    TOKENIZER = tiktoken.get_encoding("cl100k_base")
except:
    TOKENIZER = None


def count_tokens(text: str) -> int:
    """Count tokens in text."""
    if not TOKENIZER:
        # Rough estimate: 1 token ~4 characters
        return len(text) // 4
    
    try:
        return len(TOKENIZER.encode(text))
    except Exception:
        return len(text) // 4


def truncate_to_tokens(text: str, max_tokens: int = 1200) -> str:
    """Truncate text to max token count."""
    if not TOKENIZER:
        # Rough estimate
        max_chars = max_tokens * 4
        return text[:max_chars]
    
    try:
        tokens = TOKENIZER.encode(text)
        truncated_tokens = tokens[:max_tokens]
        return TOKENIZER.decode(truncated_tokens)
    except Exception:
        return text[:max_tokens * 4]


def estimate_conversation_tokens(messages: list) -> int:
    """Estimate total tokens in conversation."""
    total = 0
    for msg in messages:
        if isinstance(msg, dict):
            total += count_tokens(msg.get("content", ""))
    return total


class TokenCounter:
    """Track tokens used in a session."""
    
    def __init__(self):
        self.total_tokens = 0
        self.message_tokens = {}
    
    def add_message_tokens(self, message_id: str, token_count: int):
        """Record tokens for a message."""
        self.message_tokens[message_id] = token_count
        self.total_tokens += token_count
    
    def get_total(self) -> int:
        """Get total tokens used."""
        return self.total_tokens
    
    def reset(self):
        """Reset counter."""
        self.total_tokens = 0
        self.message_tokens = {}
