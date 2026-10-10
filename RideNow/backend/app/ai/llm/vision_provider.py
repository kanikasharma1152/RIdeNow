"""
RideNow AI — Multimodal Vision Provider Abstraction
===================================================
Provides a decoupled interface for visual location understanding.
Architecture:
  VisionProvider (ABC)
      ↓
  GroqVisionProvider (Checks available vision models on Groq)
      ↓
  FallbackVisionProvider (Graceful capability detection, no fabricated results)
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class BaseVisionProvider(ABC):
    """Abstract interface for multimodal vision analysis."""

    @abstractmethod
    def is_available(self) -> bool:
        """True if vision model is configured and ready."""
        pass

    @abstractmethod
    async def analyze_location_image(
        self,
        image_base64: str,
        query: Optional[str] = None,
        user_latitude: Optional[float] = None,
        user_longitude: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Analyze image for visual location landmarks/clues.
        Returns structured dict with visual_clues, candidate_locations, confidence.
        """
        pass


class GroqVisionProvider(BaseVisionProvider):
    """
    Groq Vision implementation.
    Checks whether vision models are available in the Groq account.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.vision_model: Optional[str] = None
        self._checked_models = False

    def is_available(self) -> bool:
        if not self.api_key or self.api_key.startswith("your-"):
            return False
        return True

    async def _detect_vision_model(self) -> Optional[str]:
        """Check if any vision model is accessible on this Groq account."""
        if self._checked_models:
            return self.vision_model

        if not self.is_available():
            self._checked_models = True
            return None

        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=self.api_key)
            model_list = await client.models.list()
            candidates = [m.id for m in model_list.data if "vision" in m.id.lower()]
            if candidates:
                self.vision_model = candidates[0]
                logger.info(f"Groq vision model detected: {self.vision_model}")
            else:
                self.vision_model = None
                logger.info("No vision models available on active Groq account.")
        except Exception as exc:
            logger.warning(f"Failed to check Groq vision models: {exc}")
            self.vision_model = None

        self._checked_models = True
        return self.vision_model

    async def analyze_location_image(
        self,
        image_base64: str,
        query: Optional[str] = None,
        user_latitude: Optional[float] = None,
        user_longitude: Optional[float] = None,
    ) -> Dict[str, Any]:
        vision_model = await self._detect_vision_model()
        if not vision_model:
            # Fall back to structured capability response — DO NOT fabricate results
            gps_info = f" ({user_latitude:.4f}, {user_longitude:.4f})" if user_latitude and user_longitude else ""
            return {
                "supported": False,
                "confidence": 0.0,
                "visual_clues": [],
                "candidate_locations": [],
                "needs_confirmation": True,
                "message": (
                    f"I received your photo! Direct image landmark recognition is not enabled on the current AI model tier. "
                    f"However, I can use your current GPS location{gps_info} or you can tell me the destination address directly."
                ),
            }

        # If a real vision model exists on Groq, invoke it safely
        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=self.api_key)
            prompt = (
                "You are RideNow's location intelligence agent. Analyze this image to identify the physical location. "
                "Extract any visible signs, building names, street names, landmarks, or transit stations. "
                f"User context: {query or 'Identify pickup location'}. "
                "Respond with concise findings."
            )

            response = await client.chat.completions.create(
                model=vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                        ],
                    }
                ],
                max_tokens=300,
            )
            analysis = response.choices[0].message.content or ""
            return {
                "supported": True,
                "confidence": 0.8,
                "visual_clues": [analysis],
                "candidate_locations": [],
                "needs_confirmation": True,
                "message": f"Based on the photo: {analysis}",
            }
        except Exception as exc:
            logger.error(f"Groq vision inference error: {exc}")
            return {
                "supported": False,
                "confidence": 0.0,
                "visual_clues": [],
                "candidate_locations": [],
                "needs_confirmation": True,
                "message": "Unable to process the image at this moment. Please enter your location manually.",
            }


_vision_provider_instance = None

def get_vision_provider() -> BaseVisionProvider:
    global _vision_provider_instance
    if _vision_provider_instance is None:
        _vision_provider_instance = GroqVisionProvider()
    return _vision_provider_instance
