from llama_index.core.tools import FunctionTool
from duckduckgo_search import DDGS
from rag.retriever import rag_query
import json

def web_search(query: str) -> str:
    """
    Use duckduckgo_search (DDGS().text()) to search the web.
    Return top 3 results formatted as: "Title: ...\nURL: ...\nSnippet: ...\n---"
    Scope queries to pet-related topics only (prepend "pet care " if no pet keyword detected).
    Max results: 3. Timeout: 5 seconds.
    """
    pet_keywords = ["pet", "dog", "cat", "bird", "fish", "rabbit", "vet", "animal"]
    if not any(kw in query.lower() for kw in pet_keywords):
        query = "pet care " + query
        
    try:
        results = DDGS().text(query, max_results=3)
        formatted_results = []
        for r in results:
            formatted_results.append(f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n---")
        return "\n".join(formatted_results)
    except Exception as e:
        return f"Web search failed: {str(e)}"

def pet_weight_calculator(species: str, weight_kg: float, age_years: float) -> str:
    """
    Calculate whether a pet is underweight, healthy, overweight, or obese
    based on species-specific thresholds.
    Return a structured assessment string with recommendation.
    Species supported: dog, cat, rabbit, guinea pig
    """
    species = species.lower()
    
    # Very simplified logic for demonstration
    if species == "dog":
        if weight_kg < 5: return "Assessment: Underweight. Recommend higher caloric intake."
        if weight_kg > 40: return "Assessment: Potentially Overweight. Recommend vet check."
        return "Assessment: Healthy weight range. Maintain current diet."
    elif species == "cat":
        if weight_kg < 3: return "Assessment: Underweight. Recommend higher caloric intake."
        if weight_kg > 6: return "Assessment: Overweight. Recommend portion control."
        return "Assessment: Healthy weight range. Maintain current diet."
    elif species == "rabbit":
        if weight_kg < 1: return "Assessment: Underweight."
        if weight_kg > 3: return "Assessment: Overweight."
        return "Assessment: Healthy weight range."
    elif species == "guinea pig":
        if weight_kg < 0.7: return "Assessment: Underweight."
        if weight_kg > 1.2: return "Assessment: Overweight."
        return "Assessment: Healthy weight range."
    else:
        return f"Species '{species}' not supported by weight calculator."

def medication_schedule(pet_type: str, age_months: int) -> str:
    """
    Return a recommended vaccination + deworming schedule as a formatted string.
    Based on standard veterinary guidelines.
    """
    pet_type = pet_type.lower()
    schedule = f"Recommended Schedule for {pet_type} (Age: {age_months} months):\n"
    
    if pet_type == "dog":
        if age_months < 4:
            schedule += "- DAPP booster every 3-4 weeks until 16 weeks old.\n"
            schedule += "- Deworming every 2 weeks.\n"
        elif age_months < 12:
            schedule += "- Rabies vaccine at 12-16 weeks.\n"
            schedule += "- Start monthly heartworm and flea/tick prevention.\n"
        else:
            schedule += "- Annual DAPP and Rabies boosters as required by law.\n"
            schedule += "- Monthly heartworm and flea/tick prevention.\n"
    elif pet_type == "cat":
        if age_months < 4:
            schedule += "- FVRCP booster every 3-4 weeks until 16 weeks old.\n"
            schedule += "- Deworming every 2 weeks.\n"
        elif age_months < 12:
            schedule += "- Rabies vaccine at 12-16 weeks.\n"
            schedule += "- Start monthly flea/tick and heartworm prevention.\n"
        else:
            schedule += "- Annual FVRCP and Rabies boosters as required by law.\n"
            schedule += "- Monthly flea/tick and heartworm prevention.\n"
    else:
        return f"Schedule not available for {pet_type}. Please consult a vet."
        
    return schedule

def rag_lookup_wrapper(query: str, query_engine) -> str:
    """Wrapper that calls rag_query and returns the answer + sources."""
    answer, sources = rag_query(query, query_engine)
    return answer

# To make rag_lookup_tool into a LlamaIndex FunctionTool that accepts query_engine dynamically, 
# we can use a factory function or lambda, or we can just pass it later in engine.py.
# The prompt says: "This wraps the RAG query engine as an agent tool so the agent can decide to use it"
def get_rag_tool(query_engine):
    def rag_lookup(query: str) -> str:
        """Search the internal pet care knowledge base for reliable information."""
        return rag_lookup_wrapper(query, query_engine)
    return FunctionTool.from_defaults(fn=rag_lookup)

web_search_tool = FunctionTool.from_defaults(fn=web_search)
pet_weight_calculator_tool = FunctionTool.from_defaults(fn=pet_weight_calculator)
medication_schedule_tool = FunctionTool.from_defaults(fn=medication_schedule)
