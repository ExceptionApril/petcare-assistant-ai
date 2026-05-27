#!/usr/bin/env python3
"""Debug RAG retrieval with different thresholds."""
from rag_engine import RAGEngine

print("=" * 60)
print("RAG Engine Debug - Retrieval Analysis")
print("=" * 60)

rag = RAGEngine()
print(f"\n📊 Database Status:")
print(f"   - Total documents: {rag.get_document_count()}")
print(f"   - Sources: {rag.get_sources()}")

if rag.get_document_count() > 0:
    print(f"\n🔍 Testing with different similarity thresholds...")
    query = "cat health nutrition"
    
    # Test with no threshold filtering
    print(f"\nQuery: '{query}'")
    chunks_no_filter = rag.retrieve(query, k=5, min_similarity=0)
    print(f"\n1. With min_similarity=0 (no filtering):")
    print(f"   - Retrieved {len(chunks_no_filter)} chunks")
    for i, chunk in enumerate(chunks_no_filter[:3], 1):
        print(f"      {i}. Source: {chunk['source']}, Similarity: {chunk['similarity']}")
        print(f"         Content: {chunk['content'][:100]}...")
    
    # Test with low threshold
    chunks_low = rag.retrieve(query, k=5, min_similarity=0.1)
    print(f"\n2. With min_similarity=0.1:")
    print(f"   - Retrieved {len(chunks_low)} chunks")
    
    # Test with default threshold
    chunks_default = rag.retrieve(query, k=5, min_similarity=0.3)
    print(f"\n3. With min_similarity=0.3 (default):")
    print(f"   - Retrieved {len(chunks_default)} chunks")
else:
    print("\n⚠️  No documents in store. Cannot test retrieval.")

print("\n" + "=" * 60)
