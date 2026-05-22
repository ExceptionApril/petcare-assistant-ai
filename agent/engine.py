import logging

# Handle import compatibility for different LlamaIndex versions
try:
    from llama_index.core.agent import ReActAgent
except ImportError:
    try:
        from llama_index.core.agent.react import ReActAgent
    except ImportError:
        try:
            from llama_index.core.agent.react.base import ReActAgent
        except ImportError:
            from llama_index.legacy.agent.react import ReActAgent

logger = logging.getLogger(__name__)

def build_agent(tools: list, llm, system_prompt: str, debug_mode: bool = False):
    """
    Build a LlamaIndex ReActAgent for agentic AI.
    - max_iterations=5 prevents runaway loops
    - verbose=debug_mode logs tool usage
    - system_prompt injected into agent via system prompt
    - Returns agent ready to process user queries
    """
    try:
        # Pass system_prompt directly as context so the LLM behaves strictly
        agent = ReActAgent.from_tools(
            tools=tools,
            llm=llm,
            verbose=debug_mode,
            max_iterations=5,
            context=system_prompt,
        )
        logger.info(f"Agent built successfully with {len(tools)} tools")
        return agent
                
    except Exception as e:
        logger.error(f"Failed to build agent: {e}", exc_info=True)
        # Return a fallback agent that just echoes the message
        class FallbackAgent:
            def __init__(self, llm_instance):
                self.llm = llm_instance
                self.tools = tools
                
            def chat(self, message):
                logger.warning(f"Using fallback agent (ReActAgent unavailable). Message: {message}")
                return f"I understand you asked about: {message}. Please try again or use a simpler question."
        
        logger.warning("Returning fallback agent due to build failure")
        return FallbackAgent(llm)


def run_agent(agent: ReActAgent, user_message: str, chat_history: list = None) -> tuple[str, list[str]]:
    """
    Run one agent turn with RAG + agentic tools.
    Returns (response_text, list_of_tool_names_used).
    Gracefully handles errors without raising exceptions.
    
    Args:
        agent: The ReActAgent instance
        user_message: User's input query
        chat_history: Optional previous messages for context
        
    Returns:
        tuple: (response_str, tools_used_list)
    """
    try:
        logger.debug(f"Running agent with user message: {user_message[:100]}...")
        
        response = agent.chat(user_message)
        
        tools_used = []
        if hasattr(response, "sources") and response.sources:
            for src in response.sources:
                if hasattr(src, "tool_name"):
                    tool_name = src.tool_name
                    if tool_name not in tools_used:
                        tools_used.append(tool_name)
                        logger.debug(f"Tool used: {tool_name}")
        
        response_text = str(response).strip()
        logger.info(f"Agent response completed. Tools used: {tools_used}")
        return response_text, tools_used
        
    except Exception as e:
        logger.error(f"Error during agent execution: {e}", exc_info=True)
        
        fallback_msg = (
            "🐾 I ran into a problem processing your request. "
            "This might be a temporary issue with the knowledge base or connection. "
            "Please try rephrasing your question or try again shortly.\n\n"
            f"Error details: {str(e)[:200]}"
        )
        return fallback_msg, []

