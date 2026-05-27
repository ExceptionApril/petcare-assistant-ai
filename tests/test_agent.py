import pytest
from unittest.mock import patch, MagicMock
from agent_engine import ReActAgent

@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    # Mock chat.completions.create
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "ANSWER: Dogs should be fed high-quality kibble twice a day."
    mock_response.choices = [mock_choice]
    client.chat.completions.create.return_value = mock_response
    return client

def test_agent_should_search():
    agent = ReActAgent(None, "openai/gpt-4o-mini")
    
    # Needs search
    assert agent.should_search("search the web for puppy vaccines") is True
    assert agent.should_search("what is the latest news on cat flu") is True
    
    # Direct answer
    assert agent.should_search("how are you") is False
    assert agent.should_search("my dog is happy") is False

def test_web_search():
    with patch('agent_engine.DDGS') as MockDDGS:
        mock_instance = MockDDGS.return_value.__enter__.return_value
        mock_instance.text.return_value = [
            {"title": "Puppy Care Guide", "body": "Puppies need vaccination."}
        ]
        
        result = ReActAgent.web_search("puppy care")
        assert "Puppy Care Guide" in result
        assert "Puppies need vaccination." in result

def test_web_search_failed():
    with patch('agent_engine.DDGS') as MockDDGS:
        mock_instance = MockDDGS.return_value.__enter__.return_value
        mock_instance.text.side_effect = Exception("Network error")
        
        result = ReActAgent.web_search("puppy care")
        assert "Search failed" in result

def test_generate_response_direct(mock_llm_client):
    agent = ReActAgent(mock_llm_client, "openai/gpt-4o-mini")
    
    # Mock LLM to return a clean pet care response
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Dogs are great pets that need daily walks."
    mock_response.choices = [mock_choice]
    mock_llm_client.chat.completions.create.return_value = mock_response
    
    response_text, agent_steps = agent.generate_response(
        user_message="Tell me about dogs",
        conversation_history=[],
        use_reasoning=False
    )
    
    assert "daily walks" in response_text
    assert len(agent_steps) == 1
    assert agent_steps[0]["action"] == "generate_response"

def test_generate_response_blocked_non_petcare(mock_llm_client):
    agent = ReActAgent(mock_llm_client, "openai/gpt-4o-mini")
    
    # Mock LLM to return non-petcare response (e.g. coding help)
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Here is a Python function: def add(a, b): return a + b"
    mock_response.choices = [mock_choice]
    mock_llm_client.chat.completions.create.return_value = mock_response
    
    response_text, agent_steps = agent.generate_response(
        user_message="Help me code in Python",
        conversation_history=[],
        use_reasoning=False
    )
    
    assert "I'm sorry, I can only help with pet care-related questions." in response_text
    assert len(agent_steps) == 1
    assert agent_steps[0]["action"] == "block_non_petcare"
