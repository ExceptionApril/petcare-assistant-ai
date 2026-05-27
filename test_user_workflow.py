#!/usr/bin/env python3
"""
Test the actual user workflow: upload → query → retrieve
This simulates what the user is experiencing on Streamlit Cloud.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from rag_engine import RAGEngine
from agent_engine import ReActAgent
from llm_client import get_llm_client
from core.config import Config
import logging

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

print("=" * 80)
print("USER WORKFLOW TEST")
print("=" * 80)

# Step 1: Initialize RAG
print("\n[1] Initialize RAG system")
print("-" * 80)
rag = RAGEngine()
doc_count = rag.get_document_count()
print(f"Initial doc count: {doc_count}")

# Step 2: Create a test document
print("\n[2] Create test document")
print("-" * 80)
test_content = """
CAT HEALTH GUIDE

Your cat's name is very important for identification. Common medical records will ask for your cat's name.
In case of emergency, having your cat's name, age, and medical history ready is crucial.

If your cat is exhibiting signs of illness, always consult a veterinarian.
"""

test_filename = "test_cat_health.txt"
chunks_added = rag.ingest_bytes(test_content.encode('utf-8'), test_filename)
print(f"Chunks added: {chunks_added}")

# Step 3: Verify persistence
print("\n[3] Verify document persistence")
print("-" * 80)
is_persisted = rag.verify_document(test_filename)
print(f"Document persisted: {is_persisted}")

new_doc_count = rag.get_document_count()
print(f"New doc count: {new_doc_count}")

# Step 4: Test RAG retrieval with the user's actual query
print("\n[4] Test RAG retrieval")
print("-" * 80)
user_query = "recall related documents tell me the name of my cat"
print(f"User query: '{user_query}'")

chunks = rag.retrieve(user_query, k=3, min_similarity=0.15)
print(f"Retrieved chunks: {len(chunks)}")
for i, chunk in enumerate(chunks, 1):
    print(f"  [{i}] Source: {chunk['source']}")
    print(f"      Similarity: {chunk['similarity']:.3f}")
    print(f"      Preview: {chunk['content'][:100]}...")

if chunks:
    rag_context = "\n\n".join([c['content'] for c in chunks])
else:
    rag_context = ""

# Step 5: Initialize agent and test response generation
print("\n[5] Test agent response generation")
print("-" * 80)

try:
    config = Config()
    print(f"API Key present: {bool(config.openrouter_api_key)}")
    print(f"Model: {config.openrouter_model}")
    
    client = get_llm_client(config)
    agent = ReActAgent(client, model=config.openrouter_model)
    
    # Test direct response (no search trigger in query)
    print(f"\nGenerating response (no web search)...")
    conversation_history = []
    
    full_response = ""
    agent_steps = []
    event_count = 0
    
    for event_type, payload in agent.generate_response_stream(
        user_message=user_query,
        conversation_history=conversation_history,
        use_reasoning=True,
        rag_context=rag_context,
        temperature=0.7,
        max_tokens=600
    ):
        event_count += 1
        if event_type == "decision":
            print(f"  [Decision] {payload}")
        elif event_type == "thinking":
            print(f"  [Thinking] {payload}")
        elif event_type == "chunk":
            full_response += payload
            print(".", end="", flush=True)
        elif event_type == "done":
            agent_steps = payload
            print()
    
    print(f"\nTotal events: {event_count}")
    print(f"Response length: {len(full_response)} chars")
    print(f"Agent steps: {len(agent_steps)}")
    
    if full_response:
        print(f"\n✅ Response received!")
        print(f"Response preview: {full_response[:200]}...")
    else:
        print(f"\n❌ Response is empty!")
        print(f"Agent steps: {agent_steps}")
        
except Exception as e:
    logger.error(f"Agent test failed: {e}", exc_info=True)
    print(f"\n❌ Error: {type(e).__name__}: {e}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
