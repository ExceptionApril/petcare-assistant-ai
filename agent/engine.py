from llama_index.core.agent import ReActAgent


def build_agent(tools: list, llm, system_prompt: str, debug_mode: bool = False) -> ReActAgent:
    """
    Build a LlamaIndex ReActAgent.
    - Injects system prompt via `context` param (supported by all LlamaIndex versions).
    - max_iterations=5 prevents runaway loops.
    """
    agent = ReActAgent.from_tools(
        tools=tools,
        llm=llm,
        verbose=debug_mode,
        max_iterations=5,
        context=system_prompt,
    )
    return agent


def run_agent(agent: ReActAgent, user_message: str, chat_history: list = None) -> tuple[str, list[str]]:
    """
    Run one agent turn.
    Returns (response_text, list_of_tool_names_used).
    Never raises — returns a safe fallback message on any exception.
    """
    try:
        response = agent.chat(user_message)
        tools_used = []
        if response.sources:
            for src in response.sources:
                if hasattr(src, "tool_name"):
                    tools_used.append(src.tool_name)
        return str(response), tools_used
    except Exception as e:
        return (
            "🐾 I ran into a problem processing your request. "
            "Please try rephrasing your question or try again shortly.",
            [],
        )
