"""
RideNow AI — LLM Provider Factory
=================================
Exposes get_llm_provider() to instantiate the active LLM provider.
"""

from typing import Optional
from app.core.config import settings
from app.ai.llm.provider import BaseLLMProvider
from app.ai.llm.groq_provider import GroqProvider


def get_llm_provider(name: Optional[str] = None) -> BaseLLMProvider:
    """
    Factory function returning the configured LLM provider.
    Defaults to Groq.
    """
    provider_name = (name or settings.LLM_PROVIDER).lower()

    if provider_name == "groq":
        return GroqProvider()

    # Default fallback to GroqProvider
    return GroqProvider()
