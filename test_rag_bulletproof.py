#!/usr/bin/env python3
"""
Test the BULLETPROOF RAG system
Run this to verify everything is working
"""

import sys
from rag_engine import RAGEngine

print("\n" + "="*80)
print("🧪 BULLETPROOF RAG SYSTEM TEST")
print("="*80 + "\n")

# Test 1: Initialize RAG
print("TEST 1: Initialize RAG Engine")
print("-" * 40)
rag = RAGEngine()
status = rag.get_status()
print(f"✅ Storage Mode: {status['storage_mode']}")
print(f"✅ Using Memory: {status['using_memory']}")
print(f"✅ ChromaDB Available: {status['chroma_db_available']}")
print(f"✅ Documents: {status['document_count']}")
print()

# Test 2: Ingest a test document
print("TEST 2: Ingest Test Document")
print("-" * 40)
test_doc = """
My dog's name is Max and he is a Golden Retriever.
Max is 5 years old and weighs 70 pounds.
He loves playing fetch and swimming.
Max eats high-quality dog food twice a day.
He gets vaccinated every year and visits the vet for checkups.
Max's favorite treats are peanut butter dog biscuits.
He sleeps about 12-14 hours per day.
Max is very friendly and loves meeting other dogs and people.
"""

chunks_added = rag.ingest_bytes(test_doc.encode('utf-8'), "test_dog.txt")
print(f"✅ Chunks ingested: {chunks_added}")

status = rag.get_status()
print(f"✅ Total documents: {status['document_count']}")
print(f"✅ Sources: {status['sources']}")
print()

# Test 3: Verify document exists
print("TEST 3: Verify Document")
print("-" * 40)
is_verified = rag.verify_document("test_dog.txt")
print(f"✅ Document verified: {is_verified}")
print()

# Test 4: Retrieve chunks
print("TEST 4: Retrieve Chunks")
print("-" * 40)
queries = [
    "What is my dog's name?",
    "How old is Max?",
    "What does Max like to eat?",
    "What breed is my dog?",
]

for query in queries:
    print(f"\nQuery: '{query}'")
    chunks = rag.retrieve(query, k=3)
    if chunks:
        print(f"✅ Retrieved {len(chunks)} chunks")
        for i, chunk in enumerate(chunks, 1):
            print(f"  [{i}] Source: {chunk['source']}")
            print(f"      Similarity: {chunk['similarity']}")
            print(f"      Content: {chunk['content'][:60]}...")
    else:
        print(f"❌ No chunks retrieved!")

print()

# Test 5: Get context string
print("TEST 5: Context String")
print("-" * 40)
context = rag.get_context_string("My dog's name", k=2)
if context:
    print(f"✅ Context generated ({len(context)} chars)")
    print(f"Preview: {context[:100]}...")
else:
    print("❌ No context generated!")

print()

# Final Summary
print("=" * 80)
final_status = rag.get_status()
print("📊 FINAL STATUS")
print("-" * 40)
for key, value in final_status.items():
    print(f"{key:.<30} {value}")

print()
if final_status['healthy']:
    print("✅ RAG SYSTEM IS HEALTHY AND WORKING!")
    sys.exit(0)
else:
    print("❌ RAG SYSTEM NOT WORKING - CHECK LOGS ABOVE")
    sys.exit(1)
