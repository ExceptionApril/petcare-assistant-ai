#!/usr/bin/env python3
"""
Test the new verify_document() function to ensure documents are actually persisting.
"""
import os
from rag_engine import RAGEngine

print("Testing document persistence verification...")
print("=" * 70)

# Initialize RAG
rag = RAGEngine()

# Test 1: Verify existing documents
print("\n[Test 1] Verifying existing documents...")
existing_sources = rag.get_sources()
print(f"Sources in database: {existing_sources}")

for source in existing_sources[:2]:
    is_present = rag.verify_document(source)
    print(f"  {source}: {'✓' if is_present else '✗'}")

# Test 2: Upload new document and verify immediately
print("\n[Test 2] Upload new document and verify...")
test_content = b"""PET EMERGENCY GUIDE

What to do in pet emergencies:

1. Stay Calm
   - Your pet can sense your stress
   - Take a deep breath

2. Call Veterinarian
   - Get emergency contact info
   - Describe symptoms clearly

3. Common Emergencies
   - Choking
   - Difficulty breathing
   - Severe bleeding
   - Unconsciousness
   - Severe pain or distress
"""

chunks = rag.ingest_bytes(test_content, "pet_emergency.txt")
print(f"Chunks added: {chunks}")

# Verify immediately after upload
is_verified = rag.verify_document("pet_emergency.txt")
print(f"Verification result: {'✓ PASS' if is_verified else '✗ FAIL'}")

# Check updated sources
updated_sources = rag.get_sources()
print(f"Updated sources: {updated_sources}")

# Test 3: New RAG instance reads the same data (simulating app rerun)
print("\n[Test 3] New RAG instance verification (simulating app rerun)...")
print("Creating new RAGEngine instance...")
rag2 = RAGEngine()

count = rag2.get_document_count()
sources = rag2.get_sources()
print(f"New instance sees: {count} documents, sources: {sources}")

is_new_doc_visible = rag2.verify_document("pet_emergency.txt")
print(f"New document visible in new instance: {'✓ PASS' if is_new_doc_visible else '✗ FAIL'}")

print("\n" + "=" * 70)
if is_verified and is_new_doc_visible:
    print("✅ PERSISTENCE VERIFICATION WORKING!")
    print("Documents persist correctly across RAG instances.")
else:
    print("❌ PERSISTENCE ISSUE DETECTED!")
    print("Documents may not be persisting correctly.")
