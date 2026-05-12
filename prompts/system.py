from core.security import SYSTEM_PROMPT_WRAPPER

PETLIO_SYSTEM_PROMPT_V2 = SYSTEM_PROMPT_WRAPPER

def build_system_prompt(
    pet_type: str,
    pet_age: str,
    use_rag: bool = True,
    use_agent: bool = True
) -> str:
    """
    Dynamically build the system prompt by:
    1. Starting with SYSTEM_PROMPT_WRAPPER from security.py
    2. Injecting pet context (type, age)
    3. Appending RAG instruction if use_rag=True
    4. Appending agent tool instruction if use_agent=True
    5. Returning the final composed prompt string
    """
    additional_context = f"Current User Pet Context:\n- Pet Type: {pet_type}\n- Pet Age: {pet_age}\n\n"
    
    if use_rag:
        additional_context += "You have access to a RAG knowledge base. Please use it for pet health, nutrition, and medication queries.\n"
        
    if use_agent:
        additional_context += "You have agentic tools available. Use the web search tool for current info and calculator tools when appropriate.\n"
        
    return SYSTEM_PROMPT_WRAPPER.format(additional_context=additional_context)
