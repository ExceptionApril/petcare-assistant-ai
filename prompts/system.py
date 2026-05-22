from core.security import SYSTEM_PROMPT_WRAPPER

PETLIO_SYSTEM_PROMPT_V2 = SYSTEM_PROMPT_WRAPPER

from core.security import SYSTEM_PROMPT_WRAPPER

def build_system_prompt(
    pet_type: str,
    pet_age: str,
    use_rag: bool = True,
    use_agent: bool = True,
    lf_client = None
) -> str:
    """
    Dynamically build the system prompt by:
    1. Fetching base prompt from Langfuse (or fallback to security.py)
    2. Injecting pet context (type, age)
    3. Appending RAG/Agent tool instructions
    """
    # Fetch base wrapper from Langfuse if available, otherwise use local fallback
    base_wrapper = SYSTEM_PROMPT_WRAPPER
    if lf_client and lf_client.is_enabled():
        base_wrapper = lf_client.get_prompt("petlio_system_prompt", fallback=SYSTEM_PROMPT_WRAPPER)

    additional_context = f"""
Pet Context for This Conversation:
- Pet Type: {pet_type}
- Pet Age: {pet_age}

You are an expert pet care assistant powered by advanced AI tools. Use the following capabilities to provide the best advice:
"""
    
    if use_rag:
        additional_context += """
KNOWLEDGE BASE (RAG): You have access to Petlio's knowledge base with verified pet health, nutrition, and medication information.
→ Use this for factual pet care queries and medical information
→ Always cite sources when available
→ Prefer knowledge base answers for health/medication topics
"""
    
    if use_agent:
        additional_context += """
AGENTIC TOOLS: You have access to specialized tools:
→ web_search: Find current pet care news, recalls, and treatments
→ pet_weight_calculator: Assess if a pet's weight is healthy
→ medication_schedule: Get vaccination and deworming schedules
→ rag_knowledge_base: Search our verified pet health database

TOOL USAGE GUIDELINES:
1. Use the RAG tool FIRST for health/nutrition/medication questions
2. Use web_search for CURRENT information (recalls, recent treatments, trending topics)
3. Use calculators for weight/medication assessments
4. Call tools proactively when needed - don't wait to be asked
5. Combine tool results with your knowledge for comprehensive answers

IMPORTANT: Always think step-by-step. If you're unsure whether to use a tool, use it!
"""
    
    additional_context += """
RESPONSE GUIDELINES:
- Be warm, friendly, and encouraging (we're helping their beloved pet!)
- Always recommend veterinary consultation for any medical concerns
- Use emojis occasionally for warmth (🐾, 💊, 🏥, etc.)
- Format long answers with bullet points or numbered lists
- Include sources and disclaimer: "Please confirm with your veterinarian"
"""
    
    return base_wrapper.format(additional_context=additional_context)
 
