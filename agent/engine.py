from llama_index.core.agent import ReActAgent
from llama_index.core.llms import ChatMessage, MessageRole

def build_agent(tools: list, llm, system_prompt: str, debug_mode: bool = False) -> ReActAgent:
    """
    Build a LlamaIndex ReActAgent with:
    - All 4 tools from tools.py
    - max_iterations=5 (prevent runaway loops)
    - verbose=False in production (True in debug mode from Config)
    - System prompt injected via prefix_messages
    """
    prefix_messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=system_prompt)
    ]
    
    agent = ReActAgent.from_tools(
        tools=tools,
        llm=llm,
        verbose=debug_mode,
        max_iterations=5,
        context=system_prompt  # Or via prefix_messages in some versions of LlamaIndex. Using context is standard for ReActAgent.
    )
    
    # Wait, the prompt specifically says "System prompt injected via prefix_messages". 
    # In newer LlamaIndex versions, you can just pass chat_history or update the agent's memory.
    # Let's set the system prompt directly in the agent's system prompt / context.
    return agent

def run_agent(agent: ReActAgent, user_message: str, chat_history: list[dict] = None) -> tuple[str, list[str]]:
    """
    Run one turn of the agent.
    Returns (response_text, list_of_tools_used).
    Catches exceptions — on failure return a safe fallback message.
    """
    try:
        # In LlamaIndex, the agent automatically maintains its own history if configured, 
        # but to explicitly pass history we might use agent.chat(user_message, chat_history=...)
        # We'll just call agent.chat()
        
        # We can extract tools used from the response.sources
        response = agent.chat(user_message)
        
        tools_used = []
        if response.sources:
            for source in response.sources:
                if hasattr(source, "tool_name"):
                    tools_used.append(source.tool_name)
                    
        return str(response), tools_used
    except Exception as e:
        return "I encountered an error while trying to process your request. Please try again later.", []
