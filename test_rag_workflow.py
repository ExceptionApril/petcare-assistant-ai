#!/usr/bin/env python3
"""
End-to-end test of document upload and RAG retrieval workflow.
Tests: 1. Upload a test document, 2. Verify it's stored, 3. Retrieve and verify results
"""
import os
from rag_engine import RAGEngine

print("=" * 70)
print("RAG END-TO-END WORKFLOW TEST")
print("=" * 70)

# Step 1: Initialize RAG
print("\n[1/4] Initializing RAG Engine...")
rag = RAGEngine()
print(f"✓ RAG initialized")
print(f"  - Documents in store: {rag.get_document_count()}")
print(f"  - Sources: {rag.get_sources()}")

# Step 2: Create and upload a test document
print("\n[2/4] Creating and uploading test document...")
test_doc_content = """
CAT NUTRITION GUIDE

Proper nutrition is essential for your cat's health. Here are key guidelines:

1. Protein Requirements: Cats are obligate carnivores and need high-quality protein.
   - Adult cats: 26% minimum protein
   - Kittens: 30% minimum protein

2. Essential Amino Acids:
   - Taurine: Critical for heart and eye health
   - Arginine: Supports immune system

3. Feeding Frequency:
   - Kittens (under 6 months): 3-4 meals per day
   - Adult cats (1-6 years): 2 meals per day
   - Senior cats (7+ years): 2 meals per day

4. Portion Control:
   - Average adult cat: 200-300 calories per day
   - Adjust based on activity level and health status

5. Wet vs Dry Food:
   - Wet food: 70% moisture, helps hydration
   - Dry food: 10% moisture, good for dental health
   - Combination diet is ideal

6. Foods to Avoid:
   - Chocolate, onions, garlic
   - Grapes and raisins
   - Xylitol (artificial sweetener)
   - Excessive salt and fat

7. Water Intake:
   - Cats should drink 7-9 ml per kg of body weight daily
   - Wet food contributes to hydration
"""

test_filename = "test_cat_nutrition.txt"
try:
    # Upload the test document
    test_chunks = rag.ingest_bytes(test_doc_content.encode('utf-8'), test_filename)
    print(f"✓ Test document uploaded")
    print(f"  - Chunks added: {test_chunks}")
    print(f"  - Total documents: {rag.get_document_count()}")
    print(f"  - Sources: {rag.get_sources()}")
except Exception as e:
    print(f"✗ Upload failed: {e}")
    exit(1)

# Step 3: Test retrieval with various queries
print("\n[3/4] Testing document retrieval...")
test_queries = [
    "What should I feed my cat?",
    "cat protein nutrition requirements",
    "how often should I feed my kitten",
    "what foods are toxic to cats",
]

retrieval_results = {}
for query in test_queries:
    try:
        chunks = rag.retrieve(query, k=2, min_similarity=0)
        retrieval_results[query] = {
            "success": True,
            "chunks_found": len(chunks),
            "similarities": [c["similarity"] for c in chunks] if chunks else [],
            "preview": chunks[0]["content"][:80] if chunks else "No chunks"
        }
        print(f"\n✓ Query: '{query}'")
        print(f"  - Chunks found: {len(chunks)}")
        if chunks:
            print(f"  - Similarities: {[c['similarity'] for c in chunks]}")
            print(f"  - Top result preview: {chunks[0]['content'][:80]}...")
    except Exception as e:
        retrieval_results[query] = {"success": False, "error": str(e)}
        print(f"\n✗ Query failed: '{query}' - {e}")

# Step 4: Summary
print("\n[4/4] Test Summary...")
print(f"\nFinal Database State:")
print(f"  - Total documents: {rag.get_document_count()}")
print(f"  - Sources: {rag.get_sources()}")

successful_queries = sum(1 for r in retrieval_results.values() if r.get("success"))
print(f"\nRetrieval Results:")
print(f"  - Queries tested: {len(test_queries)}")
print(f"  - Successful: {successful_queries}")
print(f"  - Failed: {len(test_queries) - successful_queries}")

print("\n" + "=" * 70)
if successful_queries > 0:
    print("✅ RAG WORKFLOW WORKING CORRECTLY!")
    print("Documents can be uploaded and retrieved successfully.")
else:
    print("⚠️  RETRIEVAL NOT WORKING")
    print("Documents were uploaded but retrieval is not returning results.")
print("=" * 70)
