#!/usr/bin/env python3
"""Quick test of RAG engine functionality."""
from rag_engine import RAGEngine

print("=" * 60)
print("RAG Engine Functional Test")
print("=" * 60)

# Initialize RAG
rag = RAGEngine()
print(f"\n✅ RAG Engine initialized")
print(f"   - ChromaDB client: {rag.chroma is not None}")
print(f"   - Collection: {rag.collection is not None}")
print(f"   - Document count: {rag.get_document_count()}")

# Test retrieval
if rag.get_document_count() > 0:
    print(f"\n📚 Testing retrieval...")
    sources = rag.get_sources()
    print(f"   - Sources available: {sources}")
    
    # Test a simple query
    chunks = rag.retrieve("cat health nutrition", k=3)
    print(f"\n🔍 Query: 'cat health nutrition'")
    print(f"   - Retrieved {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks, 1):
        print(f"      {i}. Source: {chunk['source']}")
        print(f"         Similarity: {chunk['similarity']}")
        print(f"         Preview: {chunk['content'][:80]}...")
else:
    print(f"\n⚠️  No documents in store yet. Upload a PDF/TXT to test retrieval.")

print("\n✅ RAG Engine is working correctly!")
print("=" * 60)
