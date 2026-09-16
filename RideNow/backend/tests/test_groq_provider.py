import pytest
from app.ai.llm.provider import BaseLLMProvider
from app.ai.llm.groq_provider import GroqProvider
from app.ai.llm import get_llm_provider
from app.core.config import settings


def test_groq_provider_availability():
    """Verify provider checks for configured api key correctly."""
    provider = GroqProvider()
    # In test environment where GROQ_API_KEY may be placeholder
    if settings.is_llm_configured:
        assert provider.is_available() is True
    else:
        assert provider.is_available() is False


def test_get_llm_provider_factory():
    """Factory returns a valid BaseLLMProvider instance."""
    p = get_llm_provider()
    assert isinstance(p, BaseLLMProvider)
    assert isinstance(p, GroqProvider)


def test_format_tools_schema():
    """Test converting internal TOOL_DEFINITIONS to Groq/OpenAI compatible schema."""
    sample_tools = [
        {
            "name": "estimate_fare",
            "description": "Calculate estimated fare for a trip.",
            "parameters": {
                "type": "object",
                "properties": {
                    "distance_km": {"type": "number"}
                },
                "required": ["distance_km"],
            },
            "allowed_roles": ["passenger", "public"],
        }
    ]
    provider = GroqProvider()
    formatted = provider._format_tools(sample_tools)
    assert len(formatted) == 1
    assert formatted[0]["type"] == "function"
    assert formatted[0]["function"]["name"] == "estimate_fare"
    assert "allowed_roles" not in formatted[0]["function"]
