import pytest
from unittest.mock import patch, MagicMock
from agent.tools import web_search, pet_weight_calculator, medication_schedule
from agent.engine import build_agent, run_agent
from llama_index.core.tools import FunctionTool

def test_web_search_tool_returns_string():
    with patch('agent.tools.DDGS') as MockDDGS:
        mock_instance = MockDDGS.return_value
        mock_instance.text.return_value = [
            {"title": "Test Title", "href": "http://test.com", "body": "Test Body"}
        ]

        result = web_search("dog food")
        assert isinstance(result, str)
        assert "Test Title" in result
        assert "http://test.com" in result
        assert "Test Body" in result

def test_pet_weight_calculator_tool_dog():
    res = pet_weight_calculator("dog", 2.0, 1.0)
    assert "Underweight" in res
    
    res2 = pet_weight_calculator("dog", 20.0, 3.0)
    assert "Healthy" in res2

def test_pet_weight_calculator_tool_cat():
    res = pet_weight_calculator("cat", 8.0, 2.0)
    assert "Overweight" in res

def test_medication_schedule_tool():
    res = medication_schedule("dog", 12)
    assert len(res) > 0
    assert "Rabies" in res
    
def test_build_agent_and_run():
    mock_llm = MagicMock()
    mock_llm.chat.return_value = MagicMock(message=MagicMock(content="Mock response"))
    
    tools = [
        FunctionTool.from_defaults(fn=pet_weight_calculator)
    ]
    agent = build_agent(tools, mock_llm, "System prompt", debug_mode=False)
    
    assert agent is not None
    
    # We will mock the agent's chat method to prevent actual LLM calls
    agent.chat = MagicMock()
    agent.chat.return_value = MagicMock()
    agent.chat.return_value.__str__.return_value = "Agent text"
    agent.chat.return_value.sources = []
    
    response_text, tools_used = run_agent(agent, "Hello", [])
    
    assert response_text == "Agent text"
    assert isinstance(tools_used, list)
