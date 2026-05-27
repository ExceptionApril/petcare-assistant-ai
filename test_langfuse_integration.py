#!/usr/bin/env python3
"""
Langfuse Integration Test Script
Test all components of the Langfuse tracing integration
Run: python test_langfuse_integration.py
"""

import sys
sys.path.insert(0, '.')

from core.config import Config
from prompts.langfuse_client import LangfuseTracer
import json

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")

def test_langfuse():
    print_header("Langfuse Integration Test")
    
    # 1. Load config
    print("\n1️⃣  Loading configuration...")
    try:
        config = Config()
        print("✅ Config loaded successfully")
        print(f"   - Langfuse Host: {config.langfuse_host}")
        print(f"   - Public Key: {config.langfuse_public_key[:20]}..." if config.langfuse_public_key else "   - Public Key: NOT SET")
        print(f"   - Secret Key: {config.langfuse_secret_key[:20]}..." if config.langfuse_secret_key else "   - Secret Key: NOT SET")
    except Exception as e:
        print(f"❌ Config failed: {e}")
        return False
    
    # 2. Initialize tracer
    print("\n2️⃣  Initializing Langfuse tracer...")
    try:
        tracer = LangfuseTracer(config)
        print(f"✅ Tracer initialized")
        print(f"   - Enabled: {tracer.is_enabled()}")
        if not tracer.is_enabled():
            print("⚠️  Langfuse is DISABLED - check your credentials in .env")
            return False
    except Exception as e:
        print(f"❌ Tracer initialization failed: {e}")
        return False
    
    # 3. Create test trace
    print("\n3️⃣  Creating test trace...")
    trace_id = None
    try:
        trace_id = tracer.start_trace(
            session_id="test-session-001",
            user_message="How should I care for my dog?",
            metadata={
                "pet_type": "dog",
                "pet_age": "3 years",
                "test_mode": True,
                "use_rag": True,
                "use_agent": True
            }
        )
        print(f"✅ Test trace created")
        print(f"   - Trace ID: {trace_id}")
    except Exception as e:
        print(f"❌ Trace creation failed: {e}")
        return False
    
    if not trace_id:
        print("❌ Trace ID is empty")
        return False
    
    # 4. Log generation
    print("\n4️⃣  Logging LLM generation...")
    try:
        tracer.log_generation(
            trace_id=trace_id,
            model="openrouter:gpt-4o-mini",
            prompt="You are a pet care assistant...",
            completion="Dogs need regular exercise, a balanced diet...",
            latency_ms=2341,
            tools_used=["rag_knowledge_base", "web_search"]
        )
        print("✅ Generation logged")
        print(f"   - Model: openrouter:gpt-4o-mini")
        print(f"   - Latency: 2341ms")
        print(f"   - Tools: rag_knowledge_base, web_search")
    except Exception as e:
        print(f"❌ Generation logging failed: {e}")
        return False
    
    # 5. Log RAG retrieval
    print("\n5️⃣  Logging RAG retrieval...")
    try:
        tracer.log_rag_retrieval(
            trace_id=trace_id,
            query="How often should I bathe my dog?",
            results="Dogs should be bathed every 4-8 weeks...",
            sources=["pet_health_guide.txt", "pet_care_practices.txt"]
        )
        print("✅ RAG retrieval logged")
        print(f"   - Sources: 2")
        print(f"   - Files: pet_health_guide.txt, pet_care_practices.txt")
    except Exception as e:
        print(f"❌ RAG retrieval logging failed: {e}")
        return False
    
    # 6. Log tool calls
    print("\n6️⃣  Logging tool executions...")
    try:
        tracer.log_tool_call(
            trace_id=trace_id,
            tool_name="pet_weight_calculator",
            input_params={"species": "dog", "weight_kg": 25, "age_years": 3},
            output="Assessment: Healthy weight range. Maintain current diet.",
            latency_ms=245
        )
        print("✅ Tool execution logged")
        print(f"   - Tool: pet_weight_calculator")
        print(f"   - Latency: 245ms")
    except Exception as e:
        print(f"❌ Tool call logging failed: {e}")
        return False
    
    # 7. Log events
    print("\n7️⃣  Logging events...")
    try:
        tracer.log_event(
            trace_id=trace_id,
            event_name="rag-retrieval-success",
            event_type="success",
            metadata={
                "query_length": 45,
                "source_count": 2,
                "latency_ms": 523
            }
        )
        print("✅ Success event logged")
        
        tracer.log_event(
            trace_id=trace_id,
            event_name="user-feedback",
            event_type="info",
            metadata={
                "feedback": "thumbs_up",
                "rating": 5
            },
            score=0.95
        )
        print("✅ Feedback event logged")
    except Exception as e:
        print(f"❌ Event logging failed: {e}")
        return False
    
    # 8. End trace
    print("\n8️⃣  Ending trace...")
    try:
        tracer.end_trace(
            trace_id=trace_id,
            output="Dogs need regular exercise, a balanced diet...",
            is_error=False
        )
        print("✅ Trace ended successfully")
    except Exception as e:
        print(f"❌ Trace ending failed: {e}")
        return False
    
    # 9. Get trace link
    print("\n9️⃣  Generating trace link...")
    try:
        link = tracer.get_trace_link(trace_id)
        print("✅ Trace link generated")
        print(f"   - URL: {link}")
    except Exception as e:
        print(f"❌ Link generation failed: {e}")
        return False
    
    # Success!
    print_header("✅ ALL TESTS PASSED!")
    print(f"""
Your Langfuse tracing integration is working perfectly!

📊 Next Steps:
1. View your test trace in Langfuse:
   {link}

2. Use the Petlio AI application:
   streamlit run app.py

3. Ask pet care questions and see them traced in Langfuse

4. Check the Langfuse dashboard for:
   - Session analytics
   - Tool performance metrics
   - Error tracking
   - User feedback scores

📖 Documentation:
   - Tracing Guide: LANGFUSE_TRACING_GUIDE.md
   - Verification Guide: LANGFUSE_VERIFICATION_GUIDE.md

💬 Need help?
   - Langfuse Docs: https://langfuse.com/docs
   - API Reference: https://langfuse.com/docs/reference
   - Community: https://langfuse.com/discord
""")
    
    return True

if __name__ == "__main__":
    success = test_langfuse()
    sys.exit(0 if success else 1)
