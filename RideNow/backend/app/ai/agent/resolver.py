"""
RideNow AI — Contextual Intent & Pronoun Resolver
=================================================
Resolves contextual references and pronouns across turns:
- "it", "there", "that trip", "this ride", "my driver", "how much", "how long"
- Infers omitted parameters from the active ConversationContext
- Dispatches safety confirmations for consequential actions
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.context import (
    ConversationContext,
    get_user_context,
    update_user_context,
    set_pending_action,
    clear_pending_action,
)
from app.ai.tools.registry import execute_tool

logger = logging.getLogger(__name__)


def is_affirmative_confirmation(text: str) -> bool:
    """Returns True if the text is a clear affirmative confirmation."""
    q = text.lower().strip()
    # Strip common punctuation
    q = re.sub(r"[.!?,]+$", "", q).strip()
    affirmative_words = {
        "yes", "confirm", "confirmed", "book it", "book", "haan", "ha", "kar do",
        "kardo", "theek hai", "yes please", "sure", "proceed", "please proceed",
        "confirm booking", "confirm cancel", "ok book it", "okay book it", "yes do it"
    }
    return q in affirmative_words or any(q.startswith(w + " ") for w in ["yes", "confirm", "haan", "proceed"])


def is_cancellation_intent(text: str) -> bool:
    """Returns True if the text expresses cancellation intent."""
    q = text.lower().strip()
    return any(w in q for w in ["cancel it", "cancel ride", "cancel my ride", "cancel this", "ride cancel", "trip cancel", "radd karo"])


def is_driver_status_intent(text: str) -> bool:
    """Returns True if query asks about assigned driver or ETA."""
    q = text.lower().strip()
    return any(w in q for w in [
        "where is my driver", "where is the driver", "driver location",
        "where is driver", "how long until driver", "when will driver arrive",
        "driver kahan hai", "driver kab aayega", "my driver"
    ])


def is_fare_inquiry(text: str) -> bool:
    """Returns True if query asks for fare/price without specifying a new location."""
    q = text.lower().strip()
    if any(w in q for w in ["spend", "spent", "kharcha", "how much did i", "how much have i"]):
        return False
    return any(q == phrase or q.startswith(phrase) for phrase in [
        "how much", "how much is it", "how much was that", "what is the fare",
        "what's the fare", "kitna lagega", "kitne paise", "fare kitna hai",
        "price kitna hai", "how much for this", "how much will it cost"
    ])


def is_safety_concern_intent(text: str) -> bool:
    """Returns True if the text expresses a safety concern."""
    q = text.lower().strip()
    return any(w in q for w in [
        "don't feel safe", "i feel unsafe", "something feels wrong", "i'm scared",
        "not safe", "help me", "i need help", "something is wrong",
        "suspicious", "feels dangerous", "mujhe darr", "darr lag raha",
        "i am scared", "feeling unsafe"
    ])


def is_sos_intent(text: str) -> bool:
    """Returns True if the text is an emergency SOS request."""
    q = text.lower().strip()
    return any(w in q for w in [
        "sos", "emergency", "call police", "i need police",
        "danger", "in danger", "bachao", "madat karo", "help help"
    ])


def is_share_ride_intent(text: str) -> bool:
    """Returns True if the user wants to share their ride/location."""
    q = text.lower().strip()
    return any(w in q for w in [
        "share my ride", "share this trip", "share trip",
        "share location", "share with", "send location to", "tell family",
        "trip share", "share ride link", "location share"
    ])


def is_vehicle_details_intent(text: str) -> bool:
    """Returns True if user wants vehicle/plate details."""
    q = text.lower().strip()
    return any(w in q for w in [
        "show me the car", "vehicle details", "show vehicle",
        "plate number", "car number", "license plate", "what car",
        "which car", "vehicle number", "registration number"
    ])


def is_route_concern_intent(text: str) -> bool:
    """Returns True if user is concerned about the route being wrong."""
    q = text.lower().strip()
    return any(w in q for w in [
        "wrong route", "different route", "not the right route",
        "taking a detour", "going the wrong way", "route deviation",
        "wrong way", "galat rasta", "route galat"
    ])


def is_safety_center_intent(text: str) -> bool:
    """Returns True if user wants to open safety center or check safety status."""
    q = text.lower().strip()
    return any(w in q for w in [
        "safety center", "safety info", "open safety",
        "safety status", "am i safe", "is this ride safe",
        "trusted contacts", "safety help", "safety features"
    ])


async def resolve_contextual_turn(
    query: str,
    current_user,
    db: AsyncSession,
    user_coords: Optional[Tuple[float, float]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Evaluates query against conversation context.
    If query relies on contextual references, resolves and executes the appropriate tool.
    Returns response dict or None if LLM / general processing should take over.
    """
    q = query.lower().strip()
    user_id = current_user.id
    role = getattr(current_user, "role", "passenger")

    ctx = await get_user_context(user_id, role=role)

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Affirmative Confirmation Execution (Pending Action in Context)
    # ─────────────────────────────────────────────────────────────────────────
    if is_affirmative_confirmation(q) and ctx.pending_action:
        action = ctx.pending_action
        data = ctx.pending_action_data or {}

        if action == "BOOK_RIDE":
            # Confirmed booking execution
            res = await execute_tool("book_ride", {"confirmed": True, **data}, current_user, db)
            await clear_pending_action(user_id, role=role)
            tools_executed = [{"tool": "book_ride", "args": {"confirmed": True}, "result": res}]

            if res.get("success"):
                ride_id = res.get("ride_id")
                await update_user_context(user_id, {
                    "active_ride_id": ride_id,
                    "active_ride_status": res.get("status", "REQUESTED"),
                    "driver_id": res.get("driver_id"),
                }, role=role)
                reply = res.get("message") or f"🎉 Your ride #{ride_id} has been confirmed and booked! A driver is being assigned."
                return {
                    "reply": reply,
                    "tools_executed": tools_executed,
                    "suggested_actions": ["Track Live", "View on Map"],
                }
            else:
                return {
                    "reply": res.get("error") or res.get("message") or "Could not complete the booking.",
                    "tools_executed": tools_executed,
                    "suggested_actions": ["Try Again", "Book a Ride"],
                }

        elif action == "CANCEL_RIDE":
            ride_id = data.get("ride_id") or ctx.active_ride_id
            if ride_id:
                res = await execute_tool("cancel_ride", {"ride_id": ride_id, "confirmed": True}, current_user, db)
                await clear_pending_action(user_id, role=role)
                await update_user_context(user_id, {
                    "active_ride_id": None,
                    "active_ride_status": "CANCELLED",
                    "driver_id": None,
                }, role=role)
                tools_executed = [{"tool": "cancel_ride", "args": {"ride_id": ride_id, "confirmed": True}, "result": res}]
                return {
                    "reply": res.get("message") or f"Ride #{ride_id} has been cancelled.",
                    "tools_executed": tools_executed,
                    "suggested_actions": ["Book a New Ride", "View Ride History"],
                }

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Contextual Pronoun: "Book it" / "Book this trip" (when destination is known)
    # ─────────────────────────────────────────────────────────────────────────
    if (q in ["book it", "book this", "book trip", "book ride", "ha book kardo", "book kar do"] or
        (q.startswith("book") and (" it" in q or " this" in q))):
        dest = ctx.destination
        pickup = ctx.pickup or "your current location"
        if dest:
            # Prepare booking with confirmation
            res = await execute_tool("book_ride", {
                "pickup_location": pickup,
                "dropoff_location": dest,
                "confirmed": False,
            }, current_user, db)
            tools_executed = [{"tool": "book_ride", "args": {"dropoff_location": dest, "confirmed": False}, "result": res}]

            if res.get("requires_confirmation"):
                await set_pending_action(user_id, "BOOK_RIDE", {
                    "pickup_location": pickup,
                    "dropoff_location": dest,
                }, role=role)
                return {
                    "reply": res.get("message"),
                    "tools_executed": tools_executed,
                    "suggested_actions": ["Yes, book it", "Cancel"],
                }
            elif res.get("already_active"):
                return {
                    "reply": res.get("message"),
                    "tools_executed": tools_executed,
                    "suggested_actions": ["Track Live", "Cancel Active Ride"],
                }

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Contextual Follow-up: "How much?" / "What is the fare?" (reusing destination)
    # ─────────────────────────────────────────────────────────────────────────
    if is_fare_inquiry(q):
        if ctx.destination:
            dest = ctx.destination
            pickup = ctx.pickup or "your location"
            res = await execute_tool("estimate_fare", {
                "pickup_address": pickup,
                "dropoff_address": dest,
            }, current_user, db)
            tools_executed = [{"tool": "estimate_fare", "args": {"pickup_address": pickup, "dropoff_address": dest}, "result": res}]

            if res.get("success"):
                fare_str = res.get("estimated_fare")
                dist = res.get("distance_km")
                await update_user_context(user_id, {
                    "estimated_fare": float(res.get("estimated_fare", "0").replace("₹", "")),
                    "distance_km": dist,
                }, role=role)
                await set_pending_action(user_id, "BOOK_RIDE", {
                    "pickup_location": pickup,
                    "dropoff_location": dest,
                }, role=role)
                return {
                    "reply": (
                        f"🚕 The estimated fare to **{dest}** is **{fare_str}** ({dist} km).\n"
                        f"- Base Fare: {res.get('base_fare', '₹50.00')}\n"
                        f"- Rate: {res.get('per_km_rate', '₹12.00')}/km\n\n"
                        f"Shall I book this ride for you?"
                    ),
                    "tools_executed": tools_executed,
                    "suggested_actions": ["Yes, book it", "Cancel"],
                }

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Active Ride Awareness: "Where is my driver?" / "How long?"
    # ─────────────────────────────────────────────────────────────────────────
    if is_driver_status_intent(q):
        res = await execute_tool("get_active_ride", {}, current_user, db)
        tools_executed = [{"tool": "get_active_ride", "args": {}, "result": res}]

        if not res.get("has_active_ride"):
            return {
                "reply": "I don't see an active ride for your account right now. Would you like to book one?",
                "tools_executed": tools_executed,
                "suggested_actions": ["Book a Ride", "View Past Rides"],
            }

        await update_user_context(user_id, {
            "active_ride_id": res.get("ride_id"),
            "active_ride_status": res.get("status"),
            "driver_id": res.get("driver_id"),
        }, role=role)

        status = res.get("status")
        driver_id = res.get("driver_id")
        vehicle = res.get("vehicle_model", "RideNow Fleet Unit")
        plate = f" ({res.get('vehicle_number')})" if res.get("vehicle_number") else ""

        if status == "REQUESTED":
            reply = f"Your ride #{res['ride_id']} is requested. We are currently matching the nearest captain to your pickup corridor."
        elif status == "ACCEPTED":
            eta_bit = f" Estimated arrival: ~{res.get('driver_eta_minutes')} mins." if res.get("driver_eta_minutes") else ""
            dist_bit = f" ({res.get('driver_distance_to_pickup_km')} km away)" if res.get("driver_distance_to_pickup_km") else ""
            reply = f"🚗 Captain #{driver_id} is en route in a {vehicle}{plate}{dist_bit}.{eta_bit}"
        elif status == "STARTED":
            reply = f"🏁 Your trip #{res['ride_id']} is currently in progress towards {res['dropoff_location']}. Captain #{driver_id} is driving {vehicle}{plate}."
        else:
            reply = f"Your ride #{res['ride_id']} is currently `{status}`."

        return {
            "reply": reply,
            "tools_executed": tools_executed,
            "suggested_actions": ["View on Map", "Cancel Ride"],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Cancellation Intent with Safety Confirmation Gate: "Cancel it"
    # ─────────────────────────────────────────────────────────────────────────
    if is_cancellation_intent(q):
        res = await execute_tool("get_active_ride", {}, current_user, db)
        if not res.get("has_active_ride"):
            return {
                "reply": "You do not currently have an active ride in progress to cancel.",
                "tools_executed": [{"tool": "get_active_ride", "args": {}, "result": res}],
                "suggested_actions": ["Book a Ride", "View History"],
            }

        ride_id = res["ride_id"]
        # Ask for confirmation before cancelling
        await set_pending_action(user_id, "CANCEL_RIDE", {"ride_id": ride_id}, role=role)
        cancel_check = await execute_tool("cancel_ride", {"ride_id": ride_id, "confirmed": False}, current_user, db)

        return {
            "reply": cancel_check.get("message") or (
                f"⚠️ Are you sure you want to cancel ride #{ride_id} to '{res.get('dropoff_location')}'? "
                "Please reply **'yes'** or **'confirm cancel'** to proceed."
            ),
            "tools_executed": [
                {"tool": "get_active_ride", "args": {}, "result": res},
                {"tool": "cancel_ride", "args": {"ride_id": ride_id, "confirmed": False}, "result": cancel_check},
            ],
            "suggested_actions": ["Yes, cancel ride", "Keep my ride"],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 6. Combined Active Ride + RAG Policy Query
    # Example: "If I cancel my current ride, will I be charged?"
    # ─────────────────────────────────────────────────────────────────────────
    if ("cancel" in q and any(w in q for w in ["charged", "fee", "penalty", "charge", "cost", "fine", "cut"])):
        # 1. Inspect active ride
        active_res = await execute_tool("get_active_ride", {}, current_user, db)
        tools_executed = [{"tool": "get_active_ride", "args": {}, "result": active_res}]

        # 2. Query RAG knowledge
        rag_res = await execute_tool("search_policies_and_faq", {"query": "cancellation fee policy"}, current_user, db)
        tools_executed.append({"tool": "search_policies_and_faq", "args": {"query": "cancellation fee policy"}, "result": rag_res})

        if active_res.get("has_active_ride"):
            ride_status = active_res.get("status")
            ride_id = active_res.get("ride_id")
            policy_excerpt = rag_res.get("context", "Free within 2 minutes of driver matching; ₹30 fee applies thereafter.")
            reply = (
                f"🛡️ **Cancellation Policy for Your Current Ride (#{ride_id}):**\n\n"
                f"- **Current Ride Status:** `{ride_status}`\n"
                f"- **Platform Rule:** {policy_excerpt}\n\n"
                f"If you cancel now, cancellation is free within 2 minutes of matching. If more than 2 minutes have passed, a ₹30 compensation fee may apply."
            )
        else:
            reply = (
                f"🛡️ **RideNow Cancellation Policy:**\n\n"
                f"{rag_res.get('context', 'Cancellation is completely free before driver acceptance and within 2 minutes of matching. A standard ₹30 fee applies after 2 minutes.')}\n\n"
                f"You currently have no active ride, so no fee would apply."
            )

        return {
            "reply": reply,
            "tools_executed": tools_executed,
            "suggested_actions": ["View Active Ride", "Help Center"],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 7. Safety Center Intent: "Am I safe?", "Open safety center"
    # ─────────────────────────────────────────────────────────────────────────
    if is_safety_center_intent(q):
        res = await execute_tool("get_safety_center_tool", {}, current_user, db)
        tools_executed = [{"tool": "get_safety_center_tool", "args": {}, "result": res}]
        if res.get("success"):
            sc = res.get("safety_center", {})
            active_ride = sc.get("active_ride")
            ride_bit = ""
            if active_ride:
                ride_bit = f"\n\n🚗 **Active Ride #{active_ride.get('ride_id')}** — Status: `{active_ride.get('status')}` | Driver: {active_ride.get('driver_name', 'Assigned')} | Vehicle: {active_ride.get('vehicle_model', '')} {active_ride.get('vehicle_number', '')}"
            contacts_count = sc.get("trusted_contacts_count", 0)
            return {
                "reply": (
                    f"🛡️ **RideNow Safety Center**\n\n"
                    f"Your safety shield is **ACTIVE**. You have **{contacts_count}** trusted contact(s) configured.{ride_bit}\n\n"
                    f"Available safety actions: **SOS**, **Share Ride**, **Vehicle Details**, **Report Concern**."
                ),
                "tools_executed": tools_executed,
                "suggested_actions": ["Trigger SOS", "Share My Ride", "Show Vehicle Details"],
            }
        return {
            "reply": "🛡️ Safety Center is active. You can use SOS, share your trip, or report a concern at any time.",
            "tools_executed": tools_executed,
            "suggested_actions": ["Trigger SOS", "Share My Ride"],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 8. SOS Emergency Intent
    # ─────────────────────────────────────────────────────────────────────────
    if is_sos_intent(q):
        res = await execute_tool("trigger_sos_tool", {"trigger_type": "MANUAL_SOS"}, current_user, db)
        tools_executed = [{"tool": "trigger_sos_tool", "args": {"trigger_type": "MANUAL_SOS"}, "result": res}]
        sos = res.get("sos", {})
        disclaimer = res.get("disclaimer") or sos.get("disclaimer", "")
        event_id = sos.get("event_id") or res.get("event_id")
        return {
            "reply": (
                f"🆘 **Emergency SOS Activated** (Event #{event_id})\n\n"
                f"Your safety event has been logged and the RideNow safety team has been alerted.\n\n"
                f"⚠️ **Important:** {disclaimer}\n\n"
                f"For immediate emergency services, please call **112** (India) directly."
            ),
            "tools_executed": tools_executed,
            "suggested_actions": ["Call 112", "Share My Ride", "View Safety Events"],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 9. Safety Concern Reporting
    # ─────────────────────────────────────────────────────────────────────────
    if is_safety_concern_intent(q):
        res = await execute_tool("create_safety_event_tool", {
            "event_type": "USER_REPORTED_CONCERN",
            "severity": "HIGH",
            "description": query,
        }, current_user, db)
        tools_executed = [{"tool": "create_safety_event_tool", "args": {"event_type": "USER_REPORTED_CONCERN"}, "result": res}]
        event_id = res.get("event", {}).get("id") or res.get("id")
        return {
            "reply": (
                f"🛡️ I've recorded your safety concern (Event #{event_id}) and notified the RideNow safety team.\n\n"
                f"If you feel in immediate danger, please call **112** (India) directly.\n\n"
                f"You can also trigger the **SOS** button for maximum priority escalation, or **share your ride** with a trusted contact."
            ),
            "tools_executed": tools_executed,
            "suggested_actions": ["Trigger SOS", "Share My Ride", "Call 112"],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 10. Share Ride Intent
    # ─────────────────────────────────────────────────────────────────────────
    if is_share_ride_intent(q):
        ride_id = ctx.active_ride_id
        if not ride_id:
            active_res = await execute_tool("get_active_ride", {}, current_user, db)
            ride_id = active_res.get("ride_id")
        if ride_id:
            res = await execute_tool("prepare_ride_share_tool", {"ride_id": ride_id}, current_user, db)
            tools_executed = [{"tool": "prepare_ride_share_tool", "args": {"ride_id": ride_id}, "result": res}]
            share = res.get("share", {})
            share_url = share.get("share_url") or res.get("share_url")
            share_text = share.get("share_text") or res.get("share_text")
            ext_sent = share.get("external_messaging_sent", False)
            ext_note = " The link has NOT been sent automatically — please copy and share it manually." if not ext_sent else ""
            return {
                "reply": (
                    f"📍 **Ride Share Link Generated**\n\n"
                    f"Share this link with your trusted contacts to let them track your trip live:\n\n"
                    f"`{share_url}`\n\n"
                    f"{share_text or ''}{ext_note}"
                ),
                "tools_executed": tools_executed,
                "suggested_actions": ["Copy Link", "View Trusted Contacts"],
            }
        return {
            "reply": "You don't have an active ride to share right now. Start a ride first.",
            "tools_executed": [],
            "suggested_actions": ["Book a Ride"],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 11. Vehicle Details Intent
    # ─────────────────────────────────────────────────────────────────────────
    if is_vehicle_details_intent(q):
        ride_id = ctx.active_ride_id
        if not ride_id:
            active_res = await execute_tool("get_active_ride", {}, current_user, db)
            ride_id = active_res.get("ride_id")
        if ride_id:
            res = await execute_tool("get_vehicle_details_tool", {"ride_id": ride_id}, current_user, db)
            tools_executed = [{"tool": "get_vehicle_details_tool", "args": {"ride_id": ride_id}, "result": res}]
            v = res.get("vehicle", {})
            d = res.get("driver", {})
            return {
                "reply": (
                    f"🚗 **Your Ride Vehicle Details**\n\n"
                    f"- **Driver:** {d.get('name', 'Assigned Driver')} | Rating: ⭐ {d.get('rating', 'N/A')}\n"
                    f"- **Vehicle:** {v.get('model', 'N/A')} ({v.get('type', 'Standard')})\n"
                    f"- **Plate Number:** `{v.get('number', 'N/A')}`\n\n"
                    f"Please verify this matches the vehicle at your pickup."
                ),
                "tools_executed": tools_executed,
                "suggested_actions": ["Share Ride", "Report Concern"],
            }
        return {
            "reply": "I don't see an active ride with an assigned driver right now.",
            "tools_executed": [],
            "suggested_actions": ["Book a Ride"],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 12. Route Concern Intent
    # ─────────────────────────────────────────────────────────────────────────
    if is_route_concern_intent(q):
        ride_id = ctx.active_ride_id
        if not ride_id:
            active_res = await execute_tool("get_active_ride", {}, current_user, db)
            ride_id = active_res.get("ride_id")
        if ride_id:
            res = await execute_tool("get_route_deviation_status_tool", {"ride_id": ride_id}, current_user, db)
            tools_executed = [{"tool": "get_route_deviation_status_tool", "args": {"ride_id": ride_id}, "result": res}]
            deviation = res.get("deviation", {})
            is_deviated = deviation.get("is_deviated", False)
            deviation_m = deviation.get("deviation_meters", 0)
            if is_deviated:
                return {
                    "reply": (
                        f"⚠️ **Route Deviation Detected**\n\n"
                        f"Your vehicle appears to be {deviation_m}m off the expected route.\n\n"
                        f"A safety event has been logged. If you feel unsafe, please trigger **SOS** immediately or call **112**."
                    ),
                    "tools_executed": tools_executed,
                    "suggested_actions": ["Trigger SOS", "Share Ride", "Call 112"],
                }
            return {
                "reply": "✅ Your vehicle is currently following the expected route. No deviation detected.",
                "tools_executed": tools_executed,
                "suggested_actions": ["View Route", "Share Ride"],
            }
        return {
            "reply": "You don't have an active ride in progress to check route status for.",
            "tools_executed": [],
            "suggested_actions": ["Book a Ride"],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 13. Phase 14: Safe Fallback for Missing Context & Ambiguous Intents
    # ─────────────────────────────────────────────────────────────────────────
    from app.ai.agent.fallback import detect_missing_context, get_fallback_response, AIConfidenceState
    fallback_key = detect_missing_context(query, ctx)
    if fallback_key:
        return get_fallback_response(fallback_key)

    return None
