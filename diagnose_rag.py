#!/usr/bin/env python3
"""
Comprehensive RAG diagnostic script - tests all components of the RAG system.
Run this to identify where the RAG system is failing.
"""
import os
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

print("=" * 70)
print("RAG SYSTEM COMPREHENSIVE DIAGNOSTIC")
print("=" * 70)

# Step 1: Check environment and paths
print("\n[1/7] Checking environment and file paths...")
CHROMA_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
print(f"✓ CHROMA_DB_PATH: {CHROMA_PATH}")
print(f"  Absolute path: {os.path.abspath(CHROMA_PATH)}")
print(f"  Exists: {os.path.exists(CHROMA_PATH)}")
print(f"  Is directory: {os.path.isdir(CHROMA_PATH)}")

if os.path.exists(CHROMA_PATH):
    try:
        perm = oct(os.stat(CHROMA_PATH).st_mode)
        print(f"  Permissions: {perm}")
        items = os.listdir(CHROMA_PATH)
        print(f"  Contents: {items}")
    except Exception as e:
        print(f"  ✗ Cannot read directory: {e}")

# Step 2: Test ChromaDB initialization
print("\n[2/7] Testing ChromaDB initialization...")
try:
    import chromadb
    print("✓ chromadb package imported")
    
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    print("✓ DefaultEmbeddingFunction imported")
    
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    print(f"✓ ChromaDB PersistentClient created at {CHROMA_PATH}")
except Exception as e:
    print(f"✗ ChromaDB initialization failed: {e}")
    sys.exit(1)

# Step 3: Test embedding function
print("\n[3/7] Testing embedding function...")
try:
    ef = DefaultEmbeddingFunction()
    test_embedding = ef(["test"])
    print(f"✓ Embedding function works")
    print(f"  Embedding dimension: {len(test_embedding[0])}")
except Exception as e:
    print(f"✗ Embedding function failed: {e}")
    sys.exit(1)

# Step 4: Test collection access
print("\n[4/7] Testing collection access...")
try:
    collection = client.get_or_create_collection(
        name="petcare_docs",
        embedding_function=ef,
    )
    doc_count = collection.count()
    print(f"✓ Collection 'petcare_docs' accessible")
    print(f"  Documents in collection: {doc_count}")
    
    if doc_count > 0:
        # Get sample metadata
        sample = collection.get(limit=5, include=["metadatas"])
        sources = {m["source"] for m in sample["metadatas"]}
        print(f"  Sources: {sources}")
    else:
        print("  ⚠️  Collection is empty!")
except Exception as e:
    print(f"✗ Collection access failed: {e}")
    sys.exit(1)

# Step 5: Test RAGEngine initialization
print("\n[5/7] Testing RAGEngine initialization...")
try:
    from rag_engine import RAGEngine
    rag = RAGEngine()
    print("✓ RAGEngine imported and initialized")
    
    doc_count = rag.get_document_count()
    print(f"  Documents available: {doc_count}")
    
    sources = rag.get_sources()
    print(f"  Sources: {sources}")
except Exception as e:
    print(f"✗ RAGEngine initialization failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 6: Test document upload
print("\n[6/7] Testing document upload...")
test_content = b"""Test Document - Dog Nutrition

This is a test document about dog nutrition. 
Dogs need proper balanced nutrition with proteins, fats, and carbohydrates.
Quality dog food should contain:
- Protein for muscle development
- Healthy fats for coat health
- Digestible carbohydrates for energy"""

try:
    chunks = rag.ingest_bytes(test_content, "test_dog_nutrition.txt")
    print(f"✓ Document upload successful")
    print(f"  Chunks added: {chunks}")
    
    new_count = rag.get_document_count()
    print(f"  Total documents now: {new_count}")
    
    new_sources = rag.get_sources()
    print(f"  Sources: {new_sources}")
except Exception as e:
    print(f"✗ Document upload failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 7: Test retrieval
print("\n[7/7] Testing document retrieval...")
test_queries = [
    "What should I feed my dog?",
    "dog nutrition and health",
    "protein requirements for dogs",
]

retrieval_working = False
for query in test_queries:
    try:
        chunks = rag.retrieve(query, k=2, min_similarity=0)
        print(f"\n✓ Query: '{query}'")
        print(f"  Chunks found: {len(chunks)}")
        if chunks:
            retrieval_working = True
            for i, chunk in enumerate(chunks, 1):
                print(f"  [{i}] Source: {chunk['source']}, Similarity: {chunk['similarity']}")
                print(f"      Preview: {chunk['content'][:60]}...")
        else:
            print(f"  ⚠️  No chunks returned")
    except Exception as e:
        print(f"✗ Query failed: '{query}' - {e}")

# Summary
print("\n" + "=" * 70)
print("DIAGNOSTIC SUMMARY")
print("=" * 70)

checks = {
    "ChromaDB accessible": True,
    "Embedding function works": True,
    "Collection exists": True,
    "Documents in store": rag.get_document_count() > 0,
    "Retrieval working": retrieval_working,
}

passed = sum(1 for v in checks.values() if v)
total = len(checks)

for check, status in checks.items():
    status_str = "✅" if status else "❌"
    print(f"{status_str} {check}")

print(f"\n{passed}/{total} checks passed")

if passed == total:
    print("\n✅ RAG SYSTEM FULLY OPERATIONAL")
else:
    print(f"\n⚠️  RAG SYSTEM HAS ISSUES - {total - passed} check(s) failed")
    print("   Please review the output above for details.")

print("=" * 70)
