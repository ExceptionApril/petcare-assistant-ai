"""Run this to test RAG before starting the app: python test_rag.py"""
from rag_engine import RAGEngine

print("=== RAG PIPELINE TEST ===\n")

# 1. Initialize
try:
    rag = RAGEngine()
    print()
except Exception as e:
    print(f"❌ Failed to initialize RAG: {e}")
    print("Make sure Ollama is running: ollama serve")
    exit(1)

# 2. Ingest a test document
test_text = """
Golden Retrievers are friendly, reliable, and trustworthy dogs.
They are known for their golden coat and love of water.
Golden Retrievers need daily exercise, at least 1-2 hours per day.
They should be fed high-quality dog food, about 2-3 cups per day split into two meals.
Common health issues include hip dysplasia, elbow dysplasia, and cataracts.
They typically live 10-12 years.
Golden Retrievers are excellent family dogs and get along well with children and other pets.
"""

chunks = rag._ingest_text(test_text.strip(), "golden_retriever_guide.txt")
print(f"Ingested {chunks} chunks\n")

# 3. Test retrieval
queries = [
    "How much exercise does a golden retriever need?",
    "What are common health problems in dogs?",
    "How long do golden retrievers live?"
]

for query in queries:
    print(f"Query: '{query}'")
    results = rag.retrieve(query, k=2)
    if results:
        for r in results:
            print(f"  [{r['similarity']:.2f}] {r['content'][:100]}...")
    else:
        print("  No results found")
    print()

# 4. Test context string
print("Context string for prompt injection:")
context = rag.get_context_string("What do golden retrievers eat?")
print(context[:200] + "..." if len(context) > 200 else context)
print("\n=== TEST COMPLETE ===")
