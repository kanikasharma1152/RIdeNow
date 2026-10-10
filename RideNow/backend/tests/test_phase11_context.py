"""
RideNow — Phase 11 + Phase 12 Tests
=====================================
Context-Aware AI + Multimodal Input Validation

Tests cover:
  Phase 11: Conversation context engine, pronoun resolution, follow-up understanding,
            active-ride awareness, confirmation safety gate, cancellation intent.
  Phase 12: Multimodal endpoint (GPS location injection, image validation,
            graceful capability reporting, context cleared on history clear).
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from starlette.testclient import TestClient

from app.main import app
from app.routers.user import get_current_user
from app.ai.agent.context import (
    ConversationContext,
    get_user_context,
    update_user_context,
    clear_user_context,
    set_pending_action,
    clear_pending_action,
)
from app.ai.agent.resolver import (
    is_affirmative_confirmation,
    is_cancellation_intent,
    is_driver_status_intent,
    is_fare_inquiry,
)


# ─────────────────────────────────────────────────────────────────────────────
# Mock user fixtures
# ─────────────────────────────────────────────────────────────────────────────

class MockPassenger:
    id = 999
    name = "Context Test Passenger"
    email = "ctxtest@example.com"
    role = "passenger"
    is_active = True


def override_user():
    return MockPassenger()


# ─────────────────────────────────────────────────────────────────────────────
# Phase 11 — Unit: Intent classifier functions
# ─────────────────────────────────────────────────────────────────────────────

class TestIntentClassifiers:
    """Tests for resolver.py deterministic classifiers."""

    def test_affirmative_words(self):
        assert is_affirmative_confirmation("yes") is True
        assert is_affirmative_confirmation("Yes") is True
        assert is_affirmative_confirmation("confirm") is True
        assert is_affirmative_confirmation("CONFIRM") is True
        assert is_affirmative_confirmation("sure") is True
        assert is_affirmative_confirmation("book it") is True
        assert is_affirmative_confirmation("haan") is True
        assert is_affirmative_confirmation("theek hai") is True
        assert is_affirmative_confirmation("proceed") is True

    def test_non_affirmative_words(self):
        assert is_affirmative_confirmation("no") is False
        assert is_affirmative_confirmation("maybe") is False
        assert is_affirmative_confirmation("how much") is False
        assert is_affirmative_confirmation("cancel") is False
        assert is_affirmative_confirmation("hello") is False
        assert is_affirmative_confirmation("") is False
        # "yes" with trailing whitespace/punctuation normalised
        assert is_affirmative_confirmation("yes!") is True

    def test_cancellation_intent(self):
        assert is_cancellation_intent("cancel my ride") is True
        assert is_cancellation_intent("cancel it") is True
        assert is_cancellation_intent("cancel this") is True
        assert is_cancellation_intent("ride cancel") is True

    def test_non_cancellation_phrases(self):
        assert is_cancellation_intent("book a ride") is False
        assert is_cancellation_intent("where is my driver") is False
        assert is_cancellation_intent("how much is the fare") is False

    def test_driver_status_intent(self):
        assert is_driver_status_intent("where is my driver") is True
        assert is_driver_status_intent("my driver") is True
        assert is_driver_status_intent("where is the driver") is True
        assert is_driver_status_intent("driver location") is True

    def test_fare_inquiry(self):
        assert is_fare_inquiry("how much") is True
        assert is_fare_inquiry("how much is it") is True
        assert is_fare_inquiry("kitna lagega") is True
        assert is_fare_inquiry("what is the fare") is True

    def test_non_fare_inquiry(self):
        assert is_fare_inquiry("book a ride to airport") is False
        assert is_fare_inquiry("cancel my ride") is False


# ─────────────────────────────────────────────────────────────────────────────
# Phase 11 — Unit: ConversationContext model
# ─────────────────────────────────────────────────────────────────────────────

class TestConversationContextModel:
    """Tests the Pydantic model and Redis helper functions."""

    def test_default_context_creation(self):
        ctx = ConversationContext(user_id=1)
        assert ctx.user_id == 1
        assert ctx.role == "passenger"
        assert ctx.destination is None
        assert ctx.pickup is None
        assert ctx.estimated_fare is None
        assert ctx.pending_action is None
        assert ctx.currency == "INR"

    def test_context_model_dump_roundtrip(self):
        ctx = ConversationContext(
            user_id=42,
            destination="Airport",
            estimated_fare=120.50,
            pending_action="BOOK_RIDE",
            pending_action_data={"pickup_location": "Home", "dropoff_location": "Airport"},
        )
        dumped = ctx.model_dump()
        restored = ConversationContext(**dumped)
        assert restored.destination == "Airport"
        assert restored.estimated_fare == 120.50
        assert restored.pending_action == "BOOK_RIDE"
        assert restored.pending_action_data["dropoff_location"] == "Airport"

    @pytest.mark.asyncio
    async def test_get_user_context_returns_fresh_when_empty(self):
        """If Redis has no key, a fresh context is returned."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        with patch("app.ai.agent.context.get_redis_client", return_value=mock_client):
            ctx = await get_user_context(user_id=7777)
        assert ctx.user_id == 7777
        assert ctx.destination is None

    @pytest.mark.asyncio
    async def test_update_user_context_persists_destination(self):
        """update_user_context writes to Redis with correct key."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        mock_client.set = AsyncMock()

        with patch("app.ai.agent.context.get_redis_client", return_value=mock_client):
            ctx = await update_user_context(
                user_id=7777,
                updates={"destination": "Palasia Square"},
            )
        assert ctx.destination == "Palasia Square"
        mock_client.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_pending_action_stores_action(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        mock_client.set = AsyncMock()

        with patch("app.ai.agent.context.get_redis_client", return_value=mock_client):
            ctx = await set_pending_action(
                user_id=7777,
                action="BOOK_RIDE",
                data={"pickup_location": "Home", "dropoff_location": "Palasia Square"},
            )
        assert ctx.pending_action == "BOOK_RIDE"
        assert ctx.pending_action_data["dropoff_location"] == "Palasia Square"

    @pytest.mark.asyncio
    async def test_clear_pending_action_nullifies(self):
        import json
        stored = ConversationContext(
            user_id=7777,
            pending_action="BOOK_RIDE",
            pending_action_data={"dropoff_location": "Palasia"},
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=json.dumps(stored.model_dump(), default=str))
        mock_client.set = AsyncMock()

        with patch("app.ai.agent.context.get_redis_client", return_value=mock_client):
            ctx = await clear_pending_action(user_id=7777)
        assert ctx.pending_action is None
        assert ctx.pending_action_data is None

    @pytest.mark.asyncio
    async def test_clear_user_context_calls_delete(self):
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock()

        with patch("app.ai.agent.context.get_redis_client", return_value=mock_client):
            await clear_user_context(user_id=7777)

        mock_client.delete.assert_called_once_with("conversation_context:user:7777")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 11 — Integration: Chat API endpoint (sync TestClient)
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase11ChatEndpointIntegration:
    """Chat endpoint tests for context-aware behaviour."""

    def setup_method(self):
        app.dependency_overrides[get_current_user] = override_user
        self.client = TestClient(app)

    def teardown_method(self):
        app.dependency_overrides.pop(get_current_user, None)

    # ── Test: Unrelated query does NOT trigger context (returns 200 with reply)
    def test_unrelated_query_passes_through(self):
        response = self.client.post(
            "/chat/message",
            json={"message": "What is the cancellation policy?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert len(data["reply"]) > 0

    # ── Test: Simple fare query returns fare-related response
    def test_fare_query_returns_reply(self):
        response = self.client.post(
            "/chat/message",
            json={"message": "How much for 10 km?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data

    # ── Test: Confirmation alone ("yes") when NO pending action — does NOT crash
    def test_affirmative_with_no_pending_action(self):
        """
        Sending 'yes' with no pending action in context should not crash.
        The resolver skips the confirmation gate and falls through to Groq/fallback.
        """
        response = self.client.post(
            "/chat/message",
            json={"message": "yes"},
        )
        assert response.status_code == 200
        data = response.json()
        # Should return some reply; not an error
        assert "reply" in data

    # ── Test: Context cleared on history clear
    def test_history_clear_succeeds(self):
        response = self.client.delete("/chat/history")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True


# ─────────────────────────────────────────────────────────────────────────────
# Phase 12 — Integration: Multimodal endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase12MultimodalEndpoint:
    """Multimodal input endpoint validation."""

    def setup_method(self):
        app.dependency_overrides[get_current_user] = override_user
        self.client = TestClient(app)

    def teardown_method(self):
        app.dependency_overrides.pop(get_current_user, None)

    # ── Test: GPS coordinates are accepted (no crash)
    def test_gps_location_included_in_request(self):
        response = self.client.post(
            "/chat/message",
            json={
                "message": "Book me a ride",
                "latitude": 22.7196,
                "longitude": 75.8577,
                "input_type": "text",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        # Modality should still be "text" (no image)
        assert data.get("input_modality") in ("text", None)

    # ── Test: Empty message rejected properly (still 200 since validation might be loose)
    def test_empty_message_handled(self):
        response = self.client.post(
            "/chat/message",
            json={"message": "   "},
        )
        # Either returns 200 with a response or 422 validation error — no 500
        assert response.status_code in (200, 422, 400)

    # ── Test: Image too large returns 413
    def test_oversized_image_returns_413(self):
        # Generate a string larger than 14 * 1024 * 1024 characters
        huge_b64 = "A" * (14 * 1024 * 1024 + 1)
        response = self.client.post(
            "/chat/message",
            json={
                "message": "What location is this?",
                "image_base64": huge_b64,
            },
        )
        assert response.status_code == 413

    # ── Test: Vision unsupported — graceful degradation, no crash
    def test_image_with_vision_unsupported_graceful(self):
        """
        When vision provider says 'supported: False', the endpoint should not crash.
        It appends a note to the prompt and continues to the AI agent normally.
        """
        import base64
        tiny_png = base64.b64encode(b"FAKE_IMAGE_DATA").decode()

        mock_provider = AsyncMock()
        mock_provider.analyze_location_image = AsyncMock(return_value={
            "supported": False,
            "message": "Vision analysis is not available with the current model configuration.",
        })

        with patch("app.routers.chat.get_vision_provider", return_value=mock_provider):
            response = self.client.post(
                "/chat/message",
                json={
                    "message": "Where is this location?",
                    "image_base64": tiny_png,
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        # visual_context should reflect the unsupported result
        assert data.get("visual_context") is not None
        assert data["visual_context"].get("supported") is False
        # input_modality should be "multimodal" since image was attached
        assert data.get("input_modality") == "multimodal"

    # ── Test: Image with data URL prefix is handled (frontend sends data:image/...;base64,)
    def test_image_with_data_url_prefix_stripped(self):
        import base64
        tiny_png_b64 = base64.b64encode(b"FAKE_IMAGE_DATA").decode()
        full_data_url = f"data:image/png;base64,{tiny_png_b64}"

        mock_provider = AsyncMock()
        mock_provider.analyze_location_image = AsyncMock(return_value={
            "supported": False,
            "message": "Vision not available.",
        })

        with patch("app.routers.chat.get_vision_provider", return_value=mock_provider):
            response = self.client.post(
                "/chat/message",
                json={
                    "message": "Identify this location.",
                    "image_base64": full_data_url,
                },
            )
        # Should not crash; router must strip the prefix before size check
        assert response.status_code == 200

    # ── Test: input_modality is "text" when no image
    def test_input_modality_text_when_no_image(self):
        response = self.client.post(
            "/chat/message",
            json={"message": "Hello, what can you do?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("input_modality") == "text"

    # ── Test: Correct modality reported when image provided
    def test_input_modality_multimodal_when_image(self):
        import base64
        b64 = base64.b64encode(b"TINY").decode()

        mock_provider = AsyncMock()
        mock_provider.analyze_location_image = AsyncMock(return_value={
            "supported": False,
            "message": "No vision.",
        })

        with patch("app.routers.chat.get_vision_provider", return_value=mock_provider):
            response = self.client.post(
                "/chat/message",
                json={"message": "show me something", "image_base64": b64},
            )
        assert response.status_code == 200
        assert response.json().get("input_modality") == "multimodal"


# ─────────────────────────────────────────────────────────────────────────────
# Phase 11 — Unit: Schema validation
# ─────────────────────────────────────────────────────────────────────────────

class TestChatSchemas:
    """Validate ChatRequest / ChatResponse Pydantic schema extensions."""

    def test_chat_request_accepts_new_fields(self):
        from app.schemas.chat import ChatRequest
        req = ChatRequest(
            message="Book me a ride",
            input_type="text",
            latitude=22.7196,
            longitude=75.8577,
        )
        assert req.latitude == 22.7196
        assert req.longitude == 75.8577
        assert req.image_base64 is None

    def test_chat_response_includes_new_fields(self):
        from app.schemas.chat import ChatResponse
        resp = ChatResponse(
            reply="Hello!",
            tools_executed=[],
            suggested_actions=[],
            visual_context={"supported": False, "message": "no vision"},
            input_modality="multimodal",
        )
        assert resp.input_modality == "multimodal"
        assert resp.visual_context["supported"] is False
