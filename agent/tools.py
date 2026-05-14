from llama_index.core.tools import FunctionTool
from duckduckgo_search import DDGS


# ── Web Search ────────────────────────────────────────────────────────────────

def web_search(query: str) -> str:
    """Search the web for current pet care information using DuckDuckGo."""
    pet_keywords = ["pet", "dog", "cat", "bird", "fish", "rabbit", "vet", "animal", "puppy", "kitten"]
    if not any(kw in query.lower() for kw in pet_keywords):
        query = "pet care " + query
    try:
        results = DDGS().text(query, max_results=3)
        if not results:
            return "No results found for that query."
        formatted = []
        for r in results:
            formatted.append(f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n---")
        return "\n".join(formatted)
    except Exception as e:
        return f"Web search unavailable: {e}"


web_search_tool = FunctionTool.from_defaults(
    fn=web_search,
    name="web_search",
    description="Search the web for current pet care news, recalls, treatments, or recent research.",
)


# ── Pet Weight Calculator ─────────────────────────────────────────────────────

def pet_weight_calculator(species: str, weight_kg: float, age_years: float) -> str:
    """Evaluate if a pet's weight is healthy based on species and age."""
    s = species.lower().strip()
    result = f"Species: {species}, Weight: {weight_kg} kg, Age: {age_years} yr\n"
    if s in ("dog", "canine"):
        if weight_kg < 5:
            result += "Assessment: Underweight. Consider higher-calorie diet. Consult vet."
        elif weight_kg > 40:
            result += "Assessment: Potentially overweight. Recommend vet evaluation."
        else:
            result += "Assessment: Healthy weight range. Maintain current diet."
    elif s in ("cat", "feline"):
        if weight_kg < 3:
            result += "Assessment: Underweight. Increase caloric intake. Consult vet."
        elif weight_kg > 6:
            result += "Assessment: Overweight. Recommend portion control and vet check."
        else:
            result += "Assessment: Healthy weight range for cat."
    elif s in ("rabbit",):
        if weight_kg < 1:
            result += "Assessment: Underweight for a rabbit."
        elif weight_kg > 3:
            result += "Assessment: Overweight for a rabbit."
        else:
            result += "Assessment: Healthy weight range for rabbit."
    elif s in ("guinea pig",):
        if weight_kg < 0.7:
            result += "Assessment: Underweight for a guinea pig."
        elif weight_kg > 1.2:
            result += "Assessment: Overweight for a guinea pig."
        else:
            result += "Assessment: Healthy weight range for guinea pig."
    else:
        result += f"Species '{species}' not in database. Please consult a veterinarian directly."
    return result


pet_weight_calculator_tool = FunctionTool.from_defaults(
    fn=pet_weight_calculator,
    name="pet_weight_calculator",
    description=(
        "Calculate whether a pet is underweight, healthy, overweight, or obese. "
        "Args: species (str), weight_kg (float), age_years (float)."
    ),
)


# ── Medication Scheduler ──────────────────────────────────────────────────────

def medication_schedule(pet_type: str, age_months: int) -> str:
    """Return a recommended vaccination and deworming schedule for a pet."""
    pt = pet_type.lower().strip()
    sched = f"📅 Recommended Schedule — {pet_type.title()} (Age: {age_months} months)\n\n"
    if pt in ("dog", "canine"):
        if age_months < 4:
            sched += "• DAPP booster every 3–4 weeks until 16 weeks old\n"
            sched += "• Deworming every 2 weeks\n"
        elif age_months < 12:
            sched += "• Rabies vaccine at 12–16 weeks\n"
            sched += "• Monthly heartworm, flea & tick prevention\n"
        else:
            sched += "• Annual DAPP & Rabies boosters\n"
            sched += "• Monthly heartworm, flea & tick prevention\n"
    elif pt in ("cat", "feline"):
        if age_months < 4:
            sched += "• FVRCP booster every 3–4 weeks until 16 weeks old\n"
            sched += "• Deworming every 2 weeks\n"
        elif age_months < 12:
            sched += "• Rabies vaccine at 12–16 weeks\n"
            sched += "• Monthly flea prevention\n"
        else:
            sched += "• Annual FVRCP & Rabies boosters\n"
            sched += "• Monthly flea prevention\n"
    else:
        sched += f"No standard schedule available for '{pet_type}'. Please consult a vet."
    return sched


medication_schedule_tool = FunctionTool.from_defaults(
    fn=medication_schedule,
    name="medication_schedule",
    description=(
        "Get a recommended vaccination and deworming schedule. "
        "Args: pet_type (str), age_months (int)."
    ),
)


# ── RAG Lookup Tool Factory ───────────────────────────────────────────────────

def get_rag_tool(query_engine):
    """Wrap the RAG query engine as a LlamaIndex FunctionTool."""
    from rag.retriever import rag_query

    def rag_lookup(query: str) -> str:
        """Search the internal Petlio knowledge base for reliable pet care information."""
        answer, _ = rag_query(query, query_engine)
        return answer

    return FunctionTool.from_defaults(
        fn=rag_lookup,
        name="rag_knowledge_base",
        description=(
            "Search the Petlio internal knowledge base (pet health, nutrition, medications). "
            "Use this for factual pet care questions before searching the web."
        ),
    )
