"""
RideNow AI — Intelligent Agent Engine
=====================================
Multi-provider AI agent (Groq primary, OpenAI, Ollama)
with function calling, memory, RAG integration, and a deterministic local fallback
for offline / unconfigured environments.
"""

import asyncio
import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.ai.agent.prompts import get_system_prompt
from app.ai.agent.memory import get_conversation_history, append_message_to_history
from app.ai.tools.registry import (
    execute_tool,
    get_available_tools_for_role,
    TOOL_DEFINITIONS,
)

logger = logging.getLogger(__name__)

# Serialize chat turns per user so overlapping requests cannot merge history.
_user_chat_locks: Dict[int, asyncio.Lock] = {}


def _chat_lock_for(user_id: int) -> asyncio.Lock:
    lock = _user_chat_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_chat_locks[user_id] = lock
    return lock


def _tool_call_key(name: str, arguments: Any) -> Tuple[str, str]:
    return (name, json.dumps(arguments or {}, sort_keys=True, default=str))


def _fallback_from_tools(tools_executed: List[Dict[str, Any]]) -> str:
    """Build a useful reply when the model never produced natural language."""
    if not tools_executed:
        return "I'm sorry, I could not produce a response at this time."

    last = tools_executed[-1]
    result = last.get("result") or {}
    if isinstance(result, dict):
        if "today_earnings" in result and "total_earnings" in result:
            today = result.get("today_earnings", "₹0")
            total = result.get("total_earnings", "₹0")
            completed = result.get("completed_rides", 0)
            return (
                f"Your earnings today are {today} across {completed} completed trip(s) "
                f"(all-time total: {total})."
            )

        for key in ("tip", "message", "context", "estimated_fare"):
            value = result.get(key)
            if value:
                if key == "estimated_fare":
                    dist = result.get("distance_km")
                    dist_bit = f" for {dist} km" if dist is not None else ""
                    return f"Estimated fare{dist_bit} is {value}."
                return str(value)
        if result.get("has_active_ride"):
            return (
                f"Your active ride #{result.get('ride_id')} is currently "
                f"{result.get('status')} from {result.get('pickup_location')} "
                f"to {result.get('dropoff_location')}."
            )
        if result.get("has_active_ride") is False:
            return result.get("message") or "You currently have no active ride in progress."
    return "I completed the requested lookup. Please ask again if you need a short summary."


# ─── Fallback Heuristic Agent (Zero API Key Mode) ─────────────────────────────

async def _local_intent_fallback(
    query: str,
    current_user,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Intelligent rule-based fallback when no external LLM API key is configured.
    Recognizes common queries (fare estimates, active ride status, trip history,
    cancellations, driver earnings, and policy questions) and calls the real tool directly.
    """
    q = query.lower().strip()
    tools_executed = []

    # 0. Check for pending booking confirmation ("yes", "confirm", "book it", "haan", "kar do")
    from app.ai.tools.booking_tools import get_pending_booking
    is_confirm = any(q == w or q.startswith(w) for w in ["yes", "confirm", "book it", "haan", "kar do", "theek hai", "yes please", "sure"])
    if is_confirm:
        pending = await get_pending_booking(current_user.id)
        if pending:
            res = await execute_tool("book_ride", {"confirmed": True}, current_user, db)
            tools_executed.append({"tool": "book_ride", "args": {"confirmed": True}, "result": res})
            if res.get("success"):
                reply = res.get("message") or f"Your ride #{res.get('ride_id')} has been booked! A driver is being assigned."
                return {"reply": reply, "tools_executed": tools_executed, "suggested_actions": ["Track Live", "View on Map"]}
            else:
                return {"reply": res.get("error") or res.get("message") or "Could not book the ride.", "tools_executed": tools_executed, "suggested_actions": ["Try Again", "Book a Ride"]}

    # 0b. Natural language ride booking requests (English, Hindi, Hinglish)
    # E.g. "book a ride to airport", "mujhe railway station jana hai", "bhai station tak ride book kar de"
    booking_match = re.search(r"(?:book\s+(?:a\s+)?ride\s+(?:to|for)\s+|mujhe\s+(.+?)\s+ja?na\s+hai|bhai\s+(.+?)\s+tak\s+ride\s+book)", q)
    if "book" in q and ("ride" in q or "taxi" in q or "cab" in q) or "jana hai" in q or "jaana hai" in q:
        dest = None
        # Extract destination
        to_idx = q.find(" to ")
        if to_idx != -1:
            dest = q[to_idx + 4:].strip()
        elif "jana hai" in q or "jaana hai" in q:
            clean = re.sub(r"^(?:mujhe|bhai|please)\s+", "", q)
            dest = re.sub(r"\s+(?:tak|ko)?\s+ja?na\s+hai.*$", "", clean).strip()

        if dest:
            from app.ai.agent.context import update_user_context, set_pending_action
            await update_user_context(current_user.id, {"destination": dest}, role=current_user.role)
            # First calculate fare and ask for confirmation
            res = await execute_tool("book_ride", {"dropoff_location": dest, "confirmed": False}, current_user, db)
            tools_executed.append({"tool": "book_ride", "args": {"dropoff_location": dest, "confirmed": False}, "result": res})
            if res.get("requires_confirmation"):
                fare_val = float(str(res.get("estimated_fare", "0")).replace("₹", "")) if res.get("estimated_fare") else None
                await set_pending_action(current_user.id, "BOOK_RIDE", {
                    "dropoff_location": dest,
                    "distance_km": res.get("distance_km"),
                    "estimated_fare": fare_val,
                }, role=current_user.role)
                await update_user_context(current_user.id, {
                    "distance_km": res.get("distance_km"),
                    "estimated_fare": fare_val,
                }, role=current_user.role)
                return {"reply": res.get("message"), "tools_executed": tools_executed, "suggested_actions": ["Yes, book it", "Cancel"]}
            elif res.get("already_active"):
                return {"reply": res.get("message"), "tools_executed": tools_executed, "suggested_actions": ["Track Live", "Cancel Active Ride"]}
            elif res.get("error"):
                return {"reply": res.get("error"), "tools_executed": tools_executed, "suggested_actions": ["Estimate fare for 10 km", "Book a Ride"]}

    # 0c. Trip Planning and Departure Time query
    # E.g. "plan trip to airport", "reach railway station by 8 PM", "when should I leave for airport"
    if "plan" in q and ("trip" in q or "ride" in q) or "reach" in q and ("by" in q or "at" in q) or "when should i leave" in q or "pahunchna hai" in q or "kab nikalna" in q:
        dest = None
        target_time = None
        by_m = re.search(r"reach\s+(.+?)\s+by\s+([0-9\:]+\s*(?:am|pm)?)", q)
        if by_m:
            dest = by_m.group(1).strip()
            target_time = by_m.group(2).strip()
        else:
            to_m = re.search(r"(?:to|for)\s+([^,]+?)(?:\s+(?:by|at)\s+([0-9\:]+\s*(?:am|pm)?)|$)", q)
            if to_m:
                dest = to_m.group(1).strip()
                target_time = to_m.group(2).strip() if to_m.group(2) else None

        if not dest and ("airport" in q or "station" in q):
            dest = "Airport" if "airport" in q else "Railway Station"

        if dest:
            plan_res = await execute_tool("get_trip_plan", {"destination": dest, "target_arrival_time": target_time}, current_user, db)
            tools_executed.append({"tool": "get_trip_plan", "args": {"destination": dest, "target_arrival_time": target_time}, "result": plan_res})
            if plan_res.get("success"):
                pickups = plan_res.get("smart_pickup_points", [])
                rec_point = pickups[0]["name"] if pickups else "Main Gate"
                reply = (
                    f"🗺️ **Predictive Trip Plan to {plan_res['destination']['address']}:**\n\n"
                    f"- 🕒 **Recommended Departure:** **{plan_res['recommended_departure_time']}** "
                    f"(Latest: {plan_res['latest_departure_time']})\n"
                    f"- 🎯 **Target Arrival:** {plan_res['target_arrival_time']}\n"
                    f"- ⏱️ **Total Estimated Travel:** {plan_res['total_duration_minutes']} mins "
                    f"(Trip: {plan_res['trip_eta_minutes']} mins, Driver Arrival: {plan_res['driver_pickup_eta_minutes']} mins)\n"
                    f"- 🚦 **Traffic & Demand:** `{plan_res['demand_level']}` (Congestion: {plan_res['congestion_factor']}x)\n"
                    f"- 💰 **Estimated Fare:** ₹{plan_res['fare_range']['min']} – ₹{plan_res['fare_range']['max']}\n"
                    f"- 📍 **Recommended Boarding Point:** {rec_point}\n\n"
                    f"*{plan_res['recommendation_summary']}*\n\n"
                    f"Would you like me to book this ride when you're ready to leave?"
                )
                return {"reply": reply, "tools_executed": tools_executed, "suggested_actions": ["Book this ride", "Best pickup point"]}

    # 0d. Personalized Mobility Summary & Spend query
    # E.g. "how much did I spend", "my spend", "total spend", "mobility summary", "kitna kharcha hua"
    if any(w in q for w in ["spend", "spent", "kharcha", "how much did i", "my summary", "mobility summary", "travel summary"]):
        summary_res = await execute_tool("get_user_mobility_summary", {}, current_user, db)
        tools_executed.append({"tool": "get_user_mobility_summary", "args": {}, "result": summary_res})
        if summary_res.get("success"):
            top_d = summary_res.get("top_destinations", [])
            top_d_str = ", ".join(f"{d['destination']} ({d['trips']} trips)" for d in top_d) if top_d else "No frequent destinations yet"
            reply = (
                f"📊 **Your Mobility Analytics & Spend Summary:**\n\n"
                f"- 💰 **Lifetime Spend:** **₹{summary_res['total_spend_inr']}** across {summary_res['total_completed_rides']} completed trip(s)\n"
                f"- 📅 **Past 30 Days Spend:** **₹{summary_res['monthly_spend_inr']}** ({summary_res['monthly_rides']} trip(s))\n"
                f"- 🏷️ **Average Fare:** ₹{summary_res['average_fare_inr']}\n"
                f"- 📍 **Top Destinations:** {top_d_str}\n"
                f"- ⏰ **Preferred Travel Window:** {summary_res['preferred_travel_window']}\n\n"
                f"*Data aggregated strictly from your verified ride receipts.*"
            )
            return {"reply": reply, "tools_executed": tools_executed, "suggested_actions": ["View Ride History", "Plan a Trip"]}

    # 0e. Smart Pickup Points query
    # E.g. "best pickup", "where to get picked up", "smart pickup", "pickup spot"
    if any(w in q for w in ["best pickup", "pickup point", "smart pickup", "where to be picked up", "kahan se ride", "pickup spot"]):
        loc = None
        for key in ["for ", "at ", "near "]:
            if key in q:
                loc = q.split(key)[-1].strip()
                break
        pickup_res = await execute_tool("get_smart_pickup_points", {"location": loc}, current_user, db)
        tools_executed.append({"tool": "get_smart_pickup_points", "args": {"location": loc}, "result": pickup_res})
        if pickup_res.get("success"):
            options = pickup_res.get("all_pickup_options", [])
            lines = [f"📍 **Smart Pickup Points for {pickup_res['reference_location']}:**\n"]
            for opt in options:
                rec_badge = " ⭐ *(Recommended)*" if opt.get("is_recommended") else ""
                lines.append(f"- **{opt['name']}**{rec_badge} — {opt['walking_distance_meters']}m walk ({opt['walking_time_minutes']} min)")
                lines.append(f"  *Benefit: {opt['benefit']}*")
            return {"reply": "\n".join(lines), "tools_executed": tools_executed, "suggested_actions": ["Book a Ride", "Plan a Trip"]}

    # 0f. Driver Matching Explanation query
    # E.g. "how are drivers matched", "how do you match drivers", "matching algorithm"
    if any(w in q for w in ["how are drivers matched", "how do you match", "matching logic", "matching algorithm", "driver assign"]):
        match_res = await execute_tool("get_driver_matching_explanation", {}, current_user, db)
        tools_executed.append({"tool": "get_driver_matching_explanation", "args": {}, "result": match_res})
        if match_res.get("success"):
            lines = ["⚡ **RideNow ML Smart Match Architecture:**\n"]
            for sig in match_res.get("matching_criteria", []):
                lines.append(f"- **{sig['signal']} ({sig['weight_pct']}%):** {sig['description']}")
            lines.append(f"\n*{match_res.get('explainability_summary')}*")
            return {"reply": "\n".join(lines), "tools_executed": tools_executed, "suggested_actions": ["Book a Ride", "View Active Ride"]}

    # 1. Fare estimate query
    # E.g. "how much for 15 km" or "estimate fare 20km"
    dist_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:km|kilometers|kilometres)", q)
    if "fare" in q or "cost" in q or "price" in q or "estimate" in q or dist_match:
        if dist_match:
            dist = float(dist_match.group(1))
            res = await execute_tool("estimate_fare", {"distance_km": dist}, current_user, db)
            tools_executed.append({"tool": "estimate_fare", "args": {"distance_km": dist}, "result": res})
            from app.ai.agent.context import update_user_context
            fare_val = float(str(res.get("estimated_fare", "0")).replace("₹", "")) if res.get("estimated_fare") else None
            await update_user_context(current_user.id, {"distance_km": dist, "estimated_fare": fare_val}, role=current_user.role)
            reply = (
                f"🚕 **Fare Estimate for {dist} km:**\n\n"
                f"- **Base Fare:** {res.get('base_fare', '₹50.00')}\n"
                f"- **Per Km Rate:** {res.get('per_km_rate', '₹12.00')}\n"
                f"- **Total Estimated Fare:** **{res.get('estimated_fare', f'₹{50 + dist*12}')}**\n\n"
                f"*Fare is calculated using RideNow standard transparent pricing.*"
            )
            return {"reply": reply, "tools_executed": tools_executed, "suggested_actions": ["Book this ride", "Check cancellation policy"]}

    # 2. Active ride query
    if any(w in q for w in ["active ride", "current ride", "where is my ride", "ride status", "driver status", "my trip"]):
        res = await execute_tool("get_active_ride", {}, current_user, db)
        tools_executed.append({"tool": "get_active_ride", "args": {}, "result": res})
        if res.get("has_active_ride"):
            from app.ai.agent.context import update_user_context
            await update_user_context(current_user.id, {
                "active_ride_id": res.get("ride_id"),
                "active_ride_status": res.get("status"),
                "driver_id": res.get("driver_id"),
                "pickup": res.get("pickup_location"),
                "destination": res.get("dropoff_location"),
            }, role=current_user.role)
            fare_str = f"- **Fare:** ₹{res['fare']}\n" if res.get("fare") else ""
            reply = (
                f"🚗 **Active Ride #{res['ride_id']}**\n\n"
                f"- **Status:** `{res['status']}`\n"
                f"- **Pickup:** {res['pickup_location']}\n"
                f"- **Dropoff:** {res['dropoff_location']}\n"
                f"- **Distance:** {res.get('distance_km', 'N/A')} km\n"
                f"{fare_str}\n"
                f"Your vehicle is tracked live on your dashboard map."
            )
            return {"reply": reply, "tools_executed": tools_executed, "suggested_actions": ["View on Map", "Cancel Ride"]}
        else:
            return {
                "reply": "You currently don't have any active rides in progress. Would you like to book one now?",
                "tools_executed": tools_executed,
                "suggested_actions": ["Book a ride", "View past rides"],
            }

    # 3. Ride cancellation query
    if "cancel" in q and ("ride" in q or "trip" in q):
        # Check active ride first
        active_res = await execute_tool("get_active_ride", {}, current_user, db)
        if not active_res.get("has_active_ride"):
            return {
                "reply": "You don't have an active ride to cancel right now.",
                "tools_executed": [],
                "suggested_actions": ["Book a ride", "View ride history"],
            }

        ride_id = active_res["ride_id"]
        is_confirmed = any(w in q for w in ["confirm", "yes", "sure", "please proceed"])
        cancel_res = await execute_tool("cancel_ride", {"ride_id": ride_id, "confirmed": is_confirmed}, current_user, db)
        tools_executed.append({"tool": "cancel_ride", "args": {"ride_id": ride_id, "confirmed": is_confirmed}, "result": cancel_res})

        if cancel_res.get("requires_confirmation"):
            return {
                "reply": cancel_res["message"],
                "tools_executed": tools_executed,
                "suggested_actions": ["Confirm Cancel", "Keep My Ride"],
            }
        elif cancel_res.get("success"):
            return {
                "reply": f"✅ {cancel_res['message']}",
                "tools_executed": tools_executed,
                "suggested_actions": ["Book another ride", "Go to Dashboard"],
            }
        else:
            return {"reply": f"❌ {cancel_res.get('message', 'Unable to cancel ride.')}", "tools_executed": tools_executed}

    # 4. Ride history query
    if any(w in q for w in ["history", "past rides", "previous rides", "recent rides", "my rides"]):
        res = await execute_tool("get_ride_history", {"limit": 3}, current_user, db)
        tools_executed.append({"tool": "get_ride_history", "args": {"limit": 3}, "result": res})
        rides = res.get("rides", [])
        if not rides:
            return {"reply": "You haven't completed any rides yet.", "tools_executed": tools_executed, "suggested_actions": ["Book your first ride"]}

        lines = ["📜 **Your Recent Trips:**\n"]
        for r in rides:
            fare_label = f" (₹{r['fare']})" if r.get("fare") else ""
            lines.append(f"- **Trip #{r['ride_id']}** to *{r['dropoff']}* — `{r['status']}`{fare_label}")
        return {"reply": "\n".join(lines), "tools_executed": tools_executed, "suggested_actions": ["View Full History", "Book a ride"]}

    # 5. Driver earnings query
    if current_user.role == "driver" and any(w in q for w in ["earning", "payout", "income", "money", "stats"]):
        res = await execute_tool("get_driver_earnings", {}, current_user, db)
        tools_executed.append({"tool": "get_driver_earnings", "args": {}, "result": res})
        if res.get("success"):
            reply = (
                f"💰 **Driver Earnings Overview:**\n\n"
                f"- **Today:** {res.get('today_earnings', '₹0')}\n"
                f"- **This Week:** {res.get('week_earnings', '₹0')}\n"
                f"- **This Month:** {res.get('month_earnings', '₹0')}\n"
                f"- **All-Time Total:** {res.get('total_earnings', '₹0')}\n"
                f"- **Completed Trips:** {res.get('completed_rides', 0)}"
            )
            return {"reply": reply, "tools_executed": tools_executed, "suggested_actions": ["Go to Earnings Page", "Toggle Status"]}
        else:
            return {
                "reply": res.get("message") or "Unable to retrieve earnings at this moment.",
                "tools_executed": tools_executed,
                "suggested_actions": ["Go to Earnings Page"],
            }

    # 6. Profile query
    if any(w in q for w in ["profile", "my account", "who am i", "my details", "my name", "my phone"]):
        res = await execute_tool("get_user_profile", {}, current_user, db)
        tools_executed.append({"tool": "get_user_profile", "args": {}, "result": res})
        if res.get("success"):
            reply = (
                f"👤 **Account Profile:**\n\n"
                f"- **Name:** {res['name']}\n"
                f"- **Email:** {res['email']}\n"
                f"- **Phone:** {res['phone']}\n"
                f"- **Role:** `{res['role'].upper()}`\n\n"
                f"You can manage your contact details anytime from the Profile section."
            )
            return {"reply": reply, "tools_executed": tools_executed, "suggested_actions": ["Go to Profile", "Check ride history"]}

    # 7. Notifications query
    if "notification" in q or "alerts" in q or "broadcast" in q:
        if "mark" in q or "read" in q:
            res = await execute_tool("mark_notification_read", {"mark_all": True}, current_user, db)
            tools_executed.append({"tool": "mark_notification_read", "args": {"mark_all": True}, "result": res})
            return {"reply": "✅ All your notifications have been marked as read.", "tools_executed": tools_executed, "suggested_actions": ["View notifications"]}
        res = await execute_tool("get_notifications", {"limit": 5}, current_user, db)
        tools_executed.append({"tool": "get_notifications", "args": {"limit": 5}, "result": res})
        if res.get("success"):
            notifs = res.get("notifications", [])
            unread = res.get("unread_count", 0)
            if not notifs:
                return {"reply": "🔔 You have no notifications right now. Everything is up to date!", "tools_executed": tools_executed}
            lines = [f"🔔 **You have {unread} unread alert{'s' if unread != 1 else ''}:**\n"]
            for n in notifs:
                status_mark = "🔵" if not n.get("is_read") else "⚪"
                lines.append(f"{status_mark} **{n['title']}**: {n['message']}")
            return {"reply": "\n".join(lines), "tools_executed": tools_executed, "suggested_actions": ["Mark all as read"]}

    # 8. Rating query
    if "rating" in q or "rate" in q or "review" in q or "stars" in q:
        res = await execute_tool("get_rating", {}, current_user, db)
        tools_executed.append({"tool": "get_rating", "args": {}, "result": res})
        if current_user.role == "driver" and res.get("success"):
            reply = (
                f"⭐ **Driver Performance & Ratings:**\n\n"
                f"- **Average Rating:** **{res.get('average_rating')} / 5.0**\n"
                f"- **Total Reviews:** {res.get('total_ratings')}\n"
            )
            return {"reply": reply, "tools_executed": tools_executed}
        else:
            return {
                "reply": "⭐ **RideNow Ratings System:**\n\nPassengers can rate completed trips from 1 to 5 stars and leave optional feedback to maintain top-tier service quality.",
                "tools_executed": tools_executed,
                "suggested_actions": ["View completed rides", "Rate recent ride"],
            }

    # 9. Payment query
    if any(w in q for w in ["payment", "refund", "fare paid", "paid", "upi", "cash"]):
        res = await execute_tool("get_payment_status", {}, current_user, db)
        tools_executed.append({"tool": "get_payment_status", "args": {}, "result": res})
        if res.get("success") and res.get("ride_id"):
            reply = (
                f"💳 **Payment Status for Ride #{res['ride_id']}:**\n\n"
                f"- **Fare:** ₹{res.get('fare', '0.00')}\n"
                f"- **Ride Status:** `{res.get('status')}`\n"
                f"- **Payment Settled:** {'Yes ✅' if res.get('payment_settled') else 'Pending Cash / UPI Settlement ⏳'}\n"
                f"- **Methods Supported:** Cash, UPI, and Digital Wallets"
            )
            return {"reply": reply, "tools_executed": tools_executed, "suggested_actions": ["Settle payment", "View ride details"]}

    # 10. General conversational intents
    if "joke" in q:
        return {
            "reply": "Why did the GPS break up with the map? Because it took a wrong turn in the relationship! 🚕💨",
            "tools_executed": [],
            "suggested_actions": ["Tell me another", "Estimate fare for 10 km"],
        }
    if any(w in q for w in ["who are you", "what are you", "what can you do", "help me"]):
        return {
            "reply": (
                f"Hello {current_user.name}! I am **Nova**, RideNow's Intelligent Mobility AI.\n\n"
                "Here is what I can do for you:\n"
                "- 🚕 **Fare Estimation**: Calculate transparent pricing for any distance or address.\n"
                "- 📍 **Active Ride Tracking**: Live telemetry, driver status, and route corridor.\n"
                "- 📜 **Ride History**: Summary of previous journeys and receipts.\n"
                "- 🛡️ **Safety & Cancellation**: Exact platform policies without guesswork.\n"
                "- 🔔 **Notifications & Profile**: Manage alerts and account details.\n"
                "- 💰 **Driver Copilot**: Live earnings telemetry and navigation tips.\n\n"
                "What would you like to check?"
            ),
            "tools_executed": [],
            "suggested_actions": ["Where is my ride?", "Estimate fare for 15 km", "What is the cancellation policy?"],
        }

    # 11. Policy or FAQ search (RAG)
    rag_res = await execute_tool("search_policies_and_faq", {"query": query}, current_user, db)
    tools_executed.append({"tool": "search_policies_and_faq", "args": {"query": query}, "result": rag_res})
    if rag_res.get("success") and rag_res.get("results_count", 0) > 0:
        return {
            "reply": f"Here is what our official documentation says regarding your question:\n\n{rag_res['context']}",
            "tools_executed": tools_executed,
            "suggested_actions": ["Book a ride", "Help with another topic"],
        }

    # Generic friendly fallback
    return {
        "reply": (
            f"Hello {current_user.name}! I am Nova, your RideNow Intelligent Mobility Assistant.\n\n"
            "I can assist you with:\n"
            "- **Active ride tracking** (\"Where is my ride?\")\n"
            "- **Fare estimates** (\"Estimate fare for 12 km\")\n"
            "- **Trip history** (\"Show my recent trips\")\n"
            "- **Platform policies & safety** (\"What is the cancellation fee?\")\n"
            "- **Driver operations** (\"What are my earnings today?\")\n\n"
            "How can I help you right now?"
        ),
        "tools_executed": tools_executed,
        "suggested_actions": ["What is my ride status?", "Estimate fare for 10 km", "What is the cancellation policy?"],
    }



# ─── Groq LLM Provider with Native Function Calling ──────────────────────────

async def _call_groq_agent(
    query: str,
    current_user,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Invoke Groq with native function calling and conversation memory.
    Executes a multi-turn tool loop: initial call → tool execution → synthesis.
    """
    from app.ai.llm import get_llm_provider

    provider = get_llm_provider()
    if not provider.is_available():
        raise ValueError("Groq is not configured — falling back to local agent.")

    from app.ai.agent.context import (
        get_user_context,
        update_user_context,
        set_pending_action,
        clear_pending_action,
    )

    ctx = await get_user_context(current_user.id, role=current_user.role)
    system_prompt = get_system_prompt(current_user.name, current_user.role)

    # Augment system prompt with active conversation context
    ctx_hints = []
    if ctx.destination:
        ctx_hints.append(f"Destination discussed: '{ctx.destination}'")
    if ctx.pickup:
        ctx_hints.append(f"Pickup discussed: '{ctx.pickup}'")
    if ctx.estimated_fare:
        ctx_hints.append(f"Estimated fare: ₹{ctx.estimated_fare} ({ctx.distance_km} km)")
    if ctx.active_ride_id:
        ctx_hints.append(f"User has an active ride: #{ctx.active_ride_id} (Status: {ctx.active_ride_status})")
    if ctx.pending_action:
        ctx_hints.append(f"Pending unconfirmed action: {ctx.pending_action}")

    if ctx_hints:
        system_prompt += "\n\nACTIVE CONVERSATION CONTEXT:\n- " + "\n- ".join(ctx_hints)

    history = await get_conversation_history(current_user.id, max_turns=5)
    tools_available = get_available_tools_for_role(current_user.role)

    # History is persisted before this call so the current user turn is already last.
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    if not history or history[-1].get("role") != "user" or history[-1].get("content") != query:
        messages.append({"role": "user", "content": query})

    tools_executed = []
    seen_results: Dict[Tuple[str, str], Dict[str, Any]] = {}
    # Enforce hard iteration limit of 5 rounds maximum
    max_rounds = min(5, max(1, int(getattr(settings, "AGENT_MAX_ITERATIONS", 5))))
    response: Dict[str, Any] = {"content": "", "tool_calls": []}

    for _ in range(max_rounds):
        response = await provider.generate_response(messages, tools=tools_available)
        tool_calls = response.get("tool_calls") or []

        if not tool_calls:
            break

        assistant_msg: Dict[str, Any] = {
            "role": "assistant",
            "content": response.get("content") or "",
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["arguments"], default=str),
                    },
                }
                for tc in tool_calls
            ],
        }
        messages.append(assistant_msg)

        executed_new_tool = False
        for tc in tool_calls:
            key = _tool_call_key(tc["name"], tc.get("arguments"))
            if key in seen_results:
                result = seen_results[key]
            else:
                result = await execute_tool(tc["name"], tc.get("arguments") or {}, current_user, db)
                seen_results[key] = result
                tools_executed.append(
                    {"tool": tc["name"], "args": tc.get("arguments") or {}, "result": result}
                )
                executed_new_tool = True

                # Synchronize tool outcomes into structured ConversationContext
                tname = tc["name"]
                targs = tc.get("arguments") or {}
                if tname == "book_ride":
                    if result.get("requires_confirmation"):
                        await set_pending_action(current_user.id, "BOOK_RIDE", targs, role=current_user.role)
                        await update_user_context(current_user.id, {
                            "destination": targs.get("dropoff_location") or ctx.destination,
                            "pickup": targs.get("pickup_location") or ctx.pickup,
                            "distance_km": result.get("distance_km"),
                            "estimated_fare": float(str(result.get("estimated_fare", "0")).replace("₹", "")),
                        }, role=current_user.role)
                    elif result.get("success"):
                        await clear_pending_action(current_user.id, role=current_user.role)
                        await update_user_context(current_user.id, {
                            "active_ride_id": result.get("ride_id"),
                            "active_ride_status": result.get("status", "REQUESTED"),
                            "driver_id": result.get("driver_id"),
                        }, role=current_user.role)
                elif tname == "estimate_fare" and result.get("success"):
                    fare_val = float(str(result.get("estimated_fare", "0")).replace("₹", "")) if result.get("estimated_fare") else None
                    await update_user_context(current_user.id, {
                        "destination": targs.get("dropoff_address") or ctx.destination,
                        "pickup": targs.get("pickup_address") or ctx.pickup,
                        "distance_km": result.get("distance_km"),
                        "estimated_fare": fare_val,
                    }, role=current_user.role)
                elif tname == "get_active_ride":
                    if result.get("has_active_ride"):
                        await update_user_context(current_user.id, {
                            "active_ride_id": result.get("ride_id"),
                            "active_ride_status": result.get("status"),
                            "driver_id": result.get("driver_id"),
                            "pickup": result.get("pickup_location"),
                            "destination": result.get("dropoff_location"),
                        }, role=current_user.role)
                    else:
                        await update_user_context(current_user.id, {
                            "active_ride_id": None,
                            "active_ride_status": None,
                            "driver_id": None,
                        }, role=current_user.role)
                elif tname == "cancel_ride" and result.get("success"):
                    await clear_pending_action(current_user.id, role=current_user.role)
                    await update_user_context(current_user.id, {
                        "active_ride_id": None,
                        "active_ride_status": "CANCELLED",
                        "driver_id": None,
                    }, role=current_user.role)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": tc["name"],
                    "content": json.dumps(result, default=str),
                }
            )

        if not executed_new_tool:
            try:
                response = await provider.generate_response(messages, tools=None)
            except Exception as exc:
                logger.warning(f"Final tool-loop synthesis failed: {exc}")
            break
    else:
        if response.get("tool_calls"):
            try:
                response = await provider.generate_response(messages, tools=None)
            except Exception as exc:
                logger.warning(f"Max-iteration synthesis failed: {exc}")

    final_content = (response.get("content") or "").strip()
    if not final_content:
        final_content = _fallback_from_tools(tools_executed)

    # Sanitize final response: remove any internal action/tool leaks if model emitted raw text
    final_content = re.sub(r'^(?:svg)?Action:\s*[a-zA-Z0-9_]+\s*\n?', '', final_content, flags=re.MULTILINE).strip()

    # Derive suggested actions from which tools ran
    suggested_actions: List[str] = []
    tool_names = [t["tool"] for t in tools_executed]
    if "book_ride" in tool_names:
        booking_succ = any(t["tool"] == "book_ride" and t.get("result", {}).get("success") for t in tools_executed)
        suggested_actions = ["Track Live", "View on Map"] if booking_succ else ["Yes, book it", "Cancel"]
    elif "get_active_ride" in tool_names:
        suggested_actions = ["View on Map", "Cancel Ride"]
    elif "get_ride_history" in tool_names:
        suggested_actions = ["Book a Ride", "View Full History"]
    elif "estimate_fare" in tool_names:
        suggested_actions = ["Book this Ride", "Check Cancellation Policy"]
    elif "get_driver_earnings" in tool_names:
        suggested_actions = ["Go to Earnings Page", "Toggle Online Status"]
    elif "get_trip_plan" in tool_names:
        suggested_actions = ["Book This Plan", "Best Pickup Point"]
    elif "get_user_mobility_summary" in tool_names:
        suggested_actions = ["View Ride History", "Plan a Trip"]
    elif "get_smart_pickup_points" in tool_names:
        suggested_actions = ["Book from here", "Plan a Trip"]
    elif "get_demand_forecast" in tool_names:
        suggested_actions = ["Plan a Trip", "Estimate fare for 10 km"]
    elif "get_driver_matching_explanation" in tool_names:
        suggested_actions = ["Book a Ride", "View Active Ride"]
    else:
        suggested_actions = ["What is my ride status?", "Estimate fare for 10 km", "Cancellation policy?"]

    return {
        "reply": final_content,
        "tools_executed": tools_executed,
        "suggested_actions": suggested_actions,
    }


# ─── Main Chat Processing Entry Point ─────────────────────────────────────────

async def process_chat_message(
    message: str,
    current_user,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Main entry point for processing a chat message.
    Tries configured LLM provider (Groq); gracefully falls back to the
    deterministic local agent if the provider key is not set or a network
    error occurs.
    """
    clean_msg = message.strip()
    if not clean_msg:
        return {"reply": "Please enter a question or command.", "tools_executed": [], "suggested_actions": []}

    from app.ai.llm import get_llm_provider
    from app.ai.agent.resolver import resolve_contextual_turn

    async with _chat_lock_for(current_user.id):
        # Persist the user turn first so concurrent requests cannot concatenate it.
        await append_message_to_history(current_user.id, "user", clean_msg)

        # 1. Attempt structured contextual turn resolution (pronoun resolution, 'how much', 'book it', 'where is my driver', 'cancel it', confirmation gate)
        try:
            contextual_res = await resolve_contextual_turn(clean_msg, current_user, db)
            if contextual_res is not None:
                await append_message_to_history(current_user.id, "assistant", contextual_res["reply"])
                return contextual_res
        except Exception as exc:
            logger.warning(f"Contextual turn resolution error: {exc}")

        provider = get_llm_provider()
        result: Optional[Dict[str, Any]] = None

        if provider.is_available():
            try:
                result = await _call_groq_agent(clean_msg, current_user, db)
            except Exception as exc:
                logger.warning(f"Groq LLM call failed ({exc}), falling back to deterministic agent.")
        else:
            logger.info("Groq not configured — using deterministic local fallback.")

        if result is None:
            result = await _local_intent_fallback(clean_msg, current_user, db)

        await append_message_to_history(current_user.id, "assistant", result["reply"])
        return result
