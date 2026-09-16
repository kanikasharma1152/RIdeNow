"""
RideNow AI — Groq LLM Provider
===============================
Primary LLM provider implementation for RideNow using Groq's high-speed inference.
Supports:
- OpenAI-compatible tool/function calling
- Async streaming/chat completions
- Robust error handling and fallback detection
"""

import json
import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.ai.llm.provider import BaseLLMProvider

logger = logging.getLogger(__name__)


class GroqProvider(BaseLLMProvider):
    """Groq API provider implementation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self._client = None

    def is_available(self) -> bool:
        """True if API key is present and not a dummy placeholder."""
        if not self.api_key:
            return False
        if self.api_key.startswith("your-") or "placeholder" in self.api_key.lower():
            return False
        return True

    def _get_client(self):
        if self._client is None:
            if not self.is_available():
                raise ValueError("Groq API key is not configured.")
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=self.api_key)
        return self._client

    def _format_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format our internal tool schema to Groq/OpenAI function calling schema."""
        groq_tools = []
        for t in tools:
            groq_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                },
            })
        return groq_tools

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """
        Invoke Groq chat completion with optional tool calls.
        """
        if not self.is_available():
            raise ValueError("Groq provider is not available (missing or invalid API key).")

        client = self._get_client()
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            formatted_tools = self._format_tools(tools)
            if formatted_tools:
                kwargs["tools"] = formatted_tools
                kwargs["tool_choice"] = "auto"

        FALLBACK_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
        models_to_try = [self.model] + [m for m in FALLBACK_MODELS if m != self.model]

        last_exc = None
        for candidate_model in models_to_try:
            kwargs["model"] = candidate_model
            try:
                response = await client.chat.completions.create(**kwargs)
                if candidate_model != self.model:
                    logger.warning(f"Groq model '{self.model}' was unavailable; successfully switched to '{candidate_model}'.")
                    self.model = candidate_model

                choice = response.choices[0]
                msg = choice.message

                parsed_tool_calls = []
                if getattr(msg, "tool_calls", None):
                    for tc in msg.tool_calls:
                        raw_args = tc.function.arguments
                        try:
                            args_dict = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        except Exception:
                            args_dict = {}

                        parsed_tool_calls.append({
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": args_dict,
                        })

                return {
                    "content": msg.content or "",
                    "tool_calls": parsed_tool_calls,
                    "role": "assistant",
                }
            except Exception as exc:
                err_str = str(exc)
                if "model_not_found" in err_str or "does not exist" in err_str:
                    logger.warning(f"Groq model '{candidate_model}' not found; trying fallback model.")
                    last_exc = exc
                    continue
                logger.error(f"Groq completion error with model '{candidate_model}': {exc}")
                raise exc

        if last_exc:
            raise last_exc
