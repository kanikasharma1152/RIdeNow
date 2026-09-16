"""
RideNow AI — Modular LLM Provider Base
======================================
Defines the abstract interface for all AI model providers (Groq, OpenAI, etc.).
Decouples the AI agent logic from any specific vendor SDK.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the provider is properly configured with an API key."""
        pass

    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """
        Generate a response given a list of messages and optional tool definitions.
        
        Returns:
            {
                "content": Optional[str],
                "tool_calls": [
                    {
                        "id": str,
                        "name": str,
                        "arguments": dict
                    }
                ]
            }
        """
        pass
