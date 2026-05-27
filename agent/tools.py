from llama_index.core.tools import FunctionTool
import time

# Handle optional duckduckgo_search import
try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    DDGS = None

# Global context for tracing (set by app during agent execution)
_tool_context = {
    "tracer": None,
    "trace_id": ""
}

def set_tool_context(tracer, trace_id: str):
    """Set the tracer context for all tools in this session."""
    _tool_context["tracer"] = tracer
    _tool_context["trace_id"] = trace_id

def _log_tool_execution(tool_name: str, input_params: dict, output: str = "", error: str = "", latency_ms: int = 0):
    """Helper to log tool execution with tracing."""
    tracer = _tool_context.get("tracer")
    trace_id = _tool_context.get("trace_id", "")
    
    if tracer and tracer.is_enabled() and trace_id:
        tracer.log_tool_call(
            trace_id=trace_id,
            tool_name=tool_name,
            input_params=input_params,
            output=output if not error else None,
            error=error if error else None,
            latency_ms=latency_ms
        )

# ── Web Search ────────────────────────────────────────────────────────────────

def web_search(query: str) -> str:
    """Search the web for current pet care information using DuckDuckGo."""
    start_time = time.time()
    input_params = {"query": query}
    
    if not DDGS_AVAILABLE:
        error_msg = "Web search unavailable. DuckDuckGo library not installed."
        latency_ms = int((time.time() - start_time) * 1000)
        _log_tool_execution("web_search", input_params, error=error_msg, latency_ms=latency_ms)
        return error_msg + " Please consult a veterinarian for specific health questions."
    
    pet_keywords = ["pet", "dog", "cat", "bird", "fish", "rabbit", "vet", "animal", "puppy", "kitten"]
    if not any(kw in query.lower() for kw in pet_keywords):
        query = "pet care " + query
    
    try:
        results = DDGS().text(query, max_results=3)
        latency_ms = int((time.time() - start_time) * 1000)
        
        if not results:
            output = "No results found for that query."
            _log_tool_execution("web_search", input_params, output=output, latency_ms=latency_ms)
            return output
        
        formatted = []
        for r in results:
            formatted.append(f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n---")
        output = "\n".join(formatted)
        _log_tool_execution("web_search", input_params, output=output[:500], latency_ms=latency_ms)
        return output
        
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        error_msg = f"Web search unavailable: {e}"
        _log_tool_execution("web_search", input_params, error=error_msg, latency_ms=latency_ms)
        return error_msg


web_search_tool = FunctionTool.from_defaults(
    fn=web_search,
    name="web_search",
    description="Search the web for current pet care news, recalls, treatments, or recent research.",
)


# ── Pet Weight Calculator ─────────────────────────────────────────────────────

def pet_weight_calculator(species: str, weight_kg: float, age_years: float) -> str:
    """Evaluate if a pet's weight is healthy based on species and age."""
    start_time = time.time()
    input_params = {"species": species, "weight_kg": weight_kg, "age_years": age_years}
    
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
    
    latency_ms = int((time.time() - start_time) * 1000)
    _log_tool_execution("pet_weight_calculator", input_params, output=result, latency_ms=latency_ms)
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
    start_time = time.time()
    input_params = {"pet_type": pet_type, "age_months": age_months}
    
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
    
    latency_ms = int((time.time() - start_time) * 1000)
    _log_tool_execution("medication_schedule", input_params, output=sched, latency_ms=latency_ms)
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
        tracer = _tool_context.get("tracer")
        trace_id = _tool_context.get("trace_id", "")
        answer, _ = rag_query(query, query_engine, tracer=tracer, trace_id=trace_id)
        return answer

    return FunctionTool.from_defaults(
        fn=rag_lookup,
        name="rag_knowledge_base",
        description=(
            "Search the Petlio internal knowledge base (pet health, nutrition, medications). "
            "Use this for factual pet care questions before searching the web."
        ),
    )
