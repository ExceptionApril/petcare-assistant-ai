#!/usr/bin/env python3
"""
Test what happens with NO RAG context (user hasn't uploaded documents)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from agent_engine import ReActAgent
from llm_client import get_llm_client
from core.config import Config
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

print("=" * 80)
print("NO RAG CONTEXT TEST (User hasn't uploaded documents)")
print("=" * 80)

config = Config()
client = get_llm_client(config)
agent = ReActAgent(client, model=config.openrouter_model)

# Simulate what happens when a user asks a query with NO documents uploaded
user_query = "recall related documents tell me the name of my cat"

print(f"\nQuery: {user_query}")
print(f"RAG context: (empty)")
print(f"Web search triggered: {agent.should_search(user_query)}")

print("\nGenerating response with NO RAG context...")
print("-" * 80)

full_response = ""
for event_type, payload in agent.generate_response_stream(
    user_message=user_query,
    conversation_history=[],
    use_reasoning=False,  # Don't use reasoning since no search trigger
    rag_context="",      # NO RAG context
    temperature=0.7,
    max_tokens=600
):
    if event_type == "decision":
        print(f"[Decision] {payload}")
    elif event_type == "chunk":
        full_response += payload
        print(".", end="", flush=True)
    elif event_type == "done":
        print()

print(f"\nResponse: {full_response}")
print(f"Length: {len(full_response)} chars")

# Now check what the app would do with this
print("\n" + "=" * 80)
print("APP FALLBACK CHECK")
print("=" * 80)

if not full_response.strip():
    print("[EMPTY] Response is empty - app shows fallback message")
    print('   "I can only help with pet care-related questions."')
else:
    print("[OK] Response has content - app displays response")
    print(f"   Preview: {full_response[:100]}...")
