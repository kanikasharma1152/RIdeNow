"""
AI Safe Fallback States — Phase 14
====================================
Provides structured fallback responses when AI intent is ambiguous,
context is missing, or a tool fails.

Never hallucinate. Never claim to process images when vision unavailable.
Never claim to contact emergency services unless integration confirmed.
"""

from enum import Enum
from typing import Any, Dict, Optional


class AIConfidenceState(str, Enum):
    CONFIDENT = "CONFIDENT"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    UNSUPPORTED = "UNSUPPORTED"
    TOOL_FAILURE = "TOOL_FAILURE"
    TEMPORARY_FAILURE = "TEMPORARY_FAILURE"
    SAFETY_ESCALATION = "SAFETY_ESCALATION"


# Human-readable fallback messages — never exposes internal state
FALLBACK_RESPONSES: Dict[str, str] = {
    "ambiguous_booking": (
        "I'd be happy to book a ride for you! Where would you like to go?"
    ),
    "missing_destination": (
        "I need a destination to book your ride. Where are you heading?"
    ),
    "missing_active_ride": (
        "I don't see any active ride right now. Would you like to book a new ride?"
    ),
    "cancel_no_active_ride": (
        "There's no active ride to cancel right now. "
        "If you'd like to book a new ride, just tell me your destination."
    ),
    "complete_no_active_ride": (
        "I don't see an active ride that can be completed right now."
    ),
    "ambiguous_reference": (
        "I'm not sure what you're referring to. Could you tell me more about what you need?"
    ),
    "vision_unavailable": (
        "I received your image, but I'm not able to process visual content in this conversation. "
        "Please describe what you need in text and I'll help you right away."
    ),
    "tool_failure_fare": (
        "I wasn't able to fetch the fare estimate right now due to a temporary issue. "
        "Please try again in a moment."
    ),
    "tool_failure_location": (
        "I couldn't resolve that location. Could you provide a more specific address or landmark?"
    ),
    "tool_failure_generic": (
        "I ran into a temporary issue completing that action. Please try again in a moment."
    ),
    "groq_unavailable": (
        "My AI assistant is temporarily unavailable. "
        "Please try again in a moment or use the app directly."
    ),
    "rate_limited": (
        "You're sending requests too quickly. Please wait a moment and try again."
    ),
    "missing_how_much_context": (
        "I'd be happy to give you a fare estimate! Which trip are you asking about? "
        "Please tell me your pickup and destination."
    ),
    "missing_driver_context": (
        "I don't see an active ride with an assigned driver right now. "
        "Would you like to book a ride?"
    ),
}


# Patterns that require context to be meaningful
_BOOKING_ALONE_PATTERNS = {
    "book it", "book", "ok book", "okay book", "yes book", "do it",
    "confirm booking", "book the ride", "proceed with booking"
}

_CANCEL_ALONE_PATTERNS = {
    "cancel it", "cancel", "cancel this", "cancel that", "radd karo", "cancel kar do"
}

_FARE_ALONE_PATTERNS = {
    "how much", "what's the fare", "what is the fare", "kitna lagega",
    "how much will it cost", "fare kitna hai", "price kitna hai"
}

_DRIVER_ALONE_PATTERNS = {
    "where is my driver", "driver kahan hai", "where is the driver",
    "how long until driver", "when will driver arrive", "driver eta"
}

_TAKE_ME_PATTERNS = {
    "take me there", "go there", "take me", "drive there"
}

_IMAGE_PATTERNS = {
    "can you see", "what do you see", "look at this", "analyze this image",
    "what is in this", "check this image", "read this image"
}


def detect_missing_context(query: str, ctx) -> Optional[str]:
    """
    Checks if query requires context that is missing.
    Returns a fallback_key string or None if context is sufficient.

    ctx: ConversationContext instance
    """
    q = query.lower().strip()

    # Strip punctuation for matching
    import re
    q_clean = re.sub(r"[.!?,]+$", "", q).strip()

    # Standalone booking without destination
    if (
        q_clean in _BOOKING_ALONE_PATTERNS
        or any(q_clean.endswith(p) for p in ("book it", "book", "book this"))
        or any(q_clean.startswith(p) for p in ("book it", "book ", "okay book", "ok book", "yes book"))
    ):
        has_destination = (
            getattr(ctx, "destination", None) or
            getattr(ctx, "dropoff_location", None)
        )
        if not has_destination:
            return "ambiguous_booking"

    # Standalone cancel without active ride
    if q_clean in _CANCEL_ALONE_PATTERNS or any(q_clean.startswith(p) for p in _CANCEL_ALONE_PATTERNS):
        has_active_ride = bool(getattr(ctx, "active_ride_id", None))
        has_pending = bool(getattr(ctx, "pending_action", None))
        if not has_active_ride and not has_pending:
            return "cancel_no_active_ride"

    # Fare inquiry without route context
    if (q_clean in _FARE_ALONE_PATTERNS or any(q_clean.startswith(p) for p in _FARE_ALONE_PATTERNS)) and not any(w in q_clean for w in ["spend", "spent", "kharcha", "how much did i", "how much have i"]):
        # If the query itself specifies a distance (e.g. "how much for 15 km"), destination, or route, let the agent resolve it
        has_distance_in_query = bool(re.search(r"\d+\s*(?:km|kilometers|kilometres|miles)", q_clean))
        has_route_in_query = any(w in q_clean for w in [" to ", " from ", "for "]) and not (q_clean in ("how much for this", "how much for that"))
        if not has_distance_in_query and not (has_route_in_query and len(q_clean.split()) > 4):
            has_fare = getattr(ctx, "fare_estimate", None)
            has_destination = getattr(ctx, "destination", None) or getattr(ctx, "dropoff_location", None)
            if not has_fare and not has_destination:
                return "missing_how_much_context"

    # "Take me there" without destination
    if any(q_clean == p or q_clean.startswith(p) for p in _TAKE_ME_PATTERNS):
        has_destination = getattr(ctx, "destination", None) or getattr(ctx, "dropoff_location", None)
        if not has_destination:
            return "missing_destination"

    # Driver location without active ride
    if any(q_clean.startswith(p) for p in _DRIVER_ALONE_PATTERNS) or q_clean in _DRIVER_ALONE_PATTERNS:
        has_active_ride = bool(getattr(ctx, "active_ride_id", None))
        if not has_active_ride:
            return "missing_driver_context"

    # Image-related queries
    if any(p in q_clean for p in _IMAGE_PATTERNS):
        return "vision_unavailable"

    return None


def get_fallback_response(
    fallback_key: str,
    state: AIConfidenceState = AIConfidenceState.NEEDS_CLARIFICATION,
    extra_context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns a structured fallback response dict compatible with the AI reply format.
    """
    message = FALLBACK_RESPONSES.get(fallback_key, FALLBACK_RESPONSES["ambiguous_reference"])
    if extra_context:
        message = f"{message}\n\n{extra_context}"

    suggested_actions = {
        "ambiguous_booking": ["Book a Ride", "Check Fare"],
        "missing_destination": ["Book a Ride"],
        "missing_active_ride": ["Book a Ride", "View Ride History"],
        "cancel_no_active_ride": ["Book a Ride"],
        "vision_unavailable": [],
        "tool_failure_fare": ["Try Again", "Book a Ride"],
        "tool_failure_location": ["Try Again"],
        "missing_how_much_context": ["Book a Ride", "Check Fare"],
        "missing_driver_context": ["Book a Ride"],
    }.get(fallback_key, ["Try Again"])

    return {
        "reply": message,
        "confidence_state": state.value,
        "fallback_used": True,
        "tools_executed": [],
        "suggested_actions": suggested_actions,
    }
