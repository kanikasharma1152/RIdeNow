"""
RideNow AI — LiveKit Real-Time Voice Agent Worker
==================================================
Powers real-time voice conversations using the SAME AI architecture:
- Cartesia STT (streaming speech-to-text with multilingual en/hi support)
- Groq LLM (llama-3.3-70b-versatile for low-latency reasoning)
- RideNow AI Tools & RAG knowledge base
- Cartesia TTS (ultra-natural low-latency voice synthesis)
- LiveKit WebRTC audio streaming
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any, List

from dotenv import load_dotenv

# Ensure backend root is in sys.path and load environment
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

load_dotenv(os.path.join(BACKEND_ROOT, ".env"))

# On Windows, ProactorEventLoop can cause intermittent 'getaddrinfo failed' DNS resolution bugs in aiohttp.
# Switching to SelectorEventLoopPolicy provides stable socket DNS resolution.
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from app.core.config import settings
from app.database import AsyncSessionLocal
from app.models.user import User
from app.repositories.user import get_user_by_id
from app.ai.agent.prompts import get_system_prompt
from app.ai.tools.registry import (
    execute_tool,
    get_available_tools_for_role,
    TOOL_DEFINITIONS,
)
from app.ai.rag.retriever import retrieve_relevant_knowledge, format_knowledge_context

# LiveKit & Plugin imports
from livekit.agents import JobContext, WorkerOptions, cli, llm, JobProcess
from livekit.agents.voice import AgentSession, Agent
from livekit.plugins import cartesia, groq, silero

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ridenow-voice-agent")


def prewarm(proc: JobProcess) -> None:
    """Pre-load the Silero VAD model so the first user speech has no event-loop blocking delay."""
    logger.info("[VOICE AGENT] prewarm: loading Silero VAD model")
    proc.userdata["vad"] = silero.VAD.load(
        min_speech_duration=0.1,
        min_silence_duration=0.5,
    )
    logger.info("[VOICE AGENT] prewarm: Silero VAD model loaded")


def create_voice_tools(current_user: User) -> List[Any]:
    """
    Build LiveKit function tools that wire directly into the verified RideNow service layer.
    Reuses the same database session, business logic, and security rules.
    """
    tools: List[Any] = []

    # 1. Active Ride Tool
    @llm.function_tool
    async def get_active_ride() -> str:
        """Check the user's currently active ride (REQUESTED, ACCEPTED, or STARTED), including destination and status."""
        async with AsyncSessionLocal() as db:
            res = await execute_tool("get_active_ride", {}, current_user, db)
            if res.get("has_active_ride"):
                fare_str = f", fare is {res.get('fare')} rupees" if res.get("fare") else ""
                return f"You have an active ride #{res['ride_id']} with status {res['status']}. Pickup: {res['pickup_location']}, Dropoff: {res['dropoff_location']}{fare_str}."
            return "You currently do not have any active rides in progress."

    tools.append(get_active_ride)

    # 2. Estimate Fare Tool
    @llm.function_tool
    async def estimate_fare(distance_km: float = 0.0, pickup_address: str = "", dropoff_address: str = "") -> str:
        """Calculate estimated trip fare in INR given distance in km or pickup/dropoff addresses."""
        async with AsyncSessionLocal() as db:
            args: Dict[str, Any] = {}
            if distance_km and distance_km > 0:
                args["distance_km"] = distance_km
            if pickup_address:
                args["pickup_address"] = pickup_address
            if dropoff_address:
                args["dropoff_address"] = dropoff_address
            
            res = await execute_tool("estimate_fare", args, current_user, db)
            if res.get("success"):
                from app.ai.agent.context import update_user_context
                fare_val = float(str(res.get("estimated_fare", "0")).replace("₹", "")) if res.get("estimated_fare") else None
                await update_user_context(current_user.id, {
                    "destination": dropoff_address or None,
                    "pickup": pickup_address or None,
                    "distance_km": res.get("distance_km"),
                    "estimated_fare": fare_val,
                }, role=current_user.role)
                return f"Estimated fare for {res.get('distance_km')} kilometers is {res.get('estimated_fare')}. Base fare is 50 rupees plus 12 rupees per kilometer."
            return f"Could not estimate fare: {res.get('message', 'invalid parameters')}"

    tools.append(estimate_fare)

    # 2b. Book Ride Tool (Voice)
    @llm.function_tool
    async def book_ride(dropoff_location: str = "", pickup_location: str = "", confirmed: bool = False) -> str:
        """Book a ride or request a trip plan. If confirmed is false, calculates fare and asks user to confirm. If confirmed is true, books the ride."""
        async with AsyncSessionLocal() as db:
            from app.ai.agent.context import get_user_context, update_user_context, set_pending_action, clear_pending_action
            ctx = await get_user_context(current_user.id, role=current_user.role)
            final_dropoff = dropoff_location.strip() or ctx.destination
            final_pickup = pickup_location.strip() or ctx.pickup or "your current location"

            if not final_dropoff:
                return "Where would you like to travel? Please tell me your destination."

            res = await execute_tool("book_ride", {
                "pickup_location": final_pickup,
                "dropoff_location": final_dropoff,
                "confirmed": confirmed,
            }, current_user, db)

            if res.get("requires_confirmation"):
                fare_val = float(str(res.get("estimated_fare", "0")).replace("₹", "")) if res.get("estimated_fare") else None
                await set_pending_action(current_user.id, "BOOK_RIDE", {
                    "pickup_location": final_pickup,
                    "dropoff_location": final_dropoff,
                }, role=current_user.role)
                await update_user_context(current_user.id, {
                    "destination": final_dropoff,
                    "pickup": final_pickup,
                    "distance_km": res.get("distance_km"),
                    "estimated_fare": fare_val,
                }, role=current_user.role)
                return f"Estimated fare to {final_dropoff} is {res.get('estimated_fare')} for {res.get('distance_km')} kilometers. Should I confirm and book this ride?"

            if res.get("success"):
                await clear_pending_action(current_user.id, role=current_user.role)
                await update_user_context(current_user.id, {
                    "active_ride_id": res.get("ride_id"),
                    "active_ride_status": res.get("status", "REQUESTED"),
                    "driver_id": res.get("driver_id"),
                }, role=current_user.role)
                return f"Your ride #{res.get('ride_id')} to {res.get('dropoff')} has been confirmed and booked! A driver is being assigned."

            return res.get("error") or res.get("message") or "Unable to book ride."

    tools.append(book_ride)

    # 3. Ride History Tool
    @llm.function_tool
    async def get_ride_history(limit: int = 3) -> str:
        """Retrieve recent past trips showing destination, status, and fare."""
        async with AsyncSessionLocal() as db:
            res = await execute_tool("get_ride_history", {"limit": limit}, current_user, db)
            rides = res.get("rides", [])
            if not rides:
                return "You have no past ride records."
            summaries = []
            for r in rides[:limit]:
                fare_txt = f" for {r.get('fare')} rupees" if r.get("fare") else ""
                summaries.append(f"Trip to {r.get('dropoff')} was {r.get('status')}{fare_txt}")
            return "Your recent trips: " + "; ".join(summaries) + "."

    tools.append(get_ride_history)

    # 4. Cancel Ride Tool (with destructive safety check)
    @llm.function_tool
    async def cancel_ride(ride_id: int, confirmed: bool = False) -> str:
        """Cancel an active ride request. If confirmed is false, prompts the user to confirm. If confirmed is true, cancels the ride."""
        async with AsyncSessionLocal() as db:
            res = await execute_tool("cancel_ride", {"ride_id": ride_id, "confirmed": confirmed}, current_user, db)
            if res.get("requires_confirmation"):
                return res.get("message", f"Are you sure you want to cancel ride #{ride_id}? Please confirm.")
            if res.get("success"):
                return f"Ride #{ride_id} has been successfully cancelled."
            return res.get("message", "Unable to cancel ride.")

    tools.append(cancel_ride)

    # 5. Policy & Knowledge Search Tool (RAG)
    @llm.function_tool
    async def search_policies_and_faq(query: str) -> str:
        """Search the official RideNow knowledge base for cancellation policies, driver rules, payment terms, or FAQs."""
        async with AsyncSessionLocal() as db:
            res = await execute_tool("search_policies_and_faq", {"query": query}, current_user, db)
            if res.get("success") and res.get("results_count", 0) > 0:
                # Return concise answer suitable for voice
                return f"According to official RideNow guidelines: {res.get('context')[:350]}"
            return "No specific policy document matched that query."

    tools.append(search_policies_and_faq)

    # 6. User Profile Tool
    @llm.function_tool
    async def get_user_profile() -> str:
        """Get the current user's profile details including name, email, phone, and account role."""
        async with AsyncSessionLocal() as db:
            res = await execute_tool("get_user_profile", {}, current_user, db)
            if res.get("success"):
                p = res.get("profile", {})
                return f"Profile: {p.get('name', 'User')}, email is {p.get('email', 'not set')}, phone is {p.get('phone', 'not set')}, role is {p.get('role', 'passenger')}."
            return "Could not retrieve user profile."

    tools.append(get_user_profile)

    # 7. Notifications Tool
    @llm.function_tool
    async def get_notifications(unread_only: bool = True) -> str:
        """Check the user's latest dispatch notifications, alerts, or messages."""
        async with AsyncSessionLocal() as db:
            res = await execute_tool("get_notifications", {"unread_only": unread_only}, current_user, db)
            if res.get("success"):
                count = res.get("unread_count", 0)
                items = res.get("notifications", [])
                if not items:
                    return f"You have {count} unread notifications."
                titles = "; ".join([n.get("title", "") for n in items[:3]])
                return f"You have {count} unread notifications. Recent alerts: {titles}."
            return "Could not retrieve notifications."

    tools.append(get_notifications)

    # 8. Rating Tool
    @llm.function_tool
    async def get_rating() -> str:
        """Get user rating or driver performance ratings."""
        async with AsyncSessionLocal() as db:
            res = await execute_tool("get_rating", {}, current_user, db)
            if res.get("success"):
                return f"Rating summary: {res.get('message', 'Rating retrieved.')}."
            return "Could not retrieve rating details."

    tools.append(get_rating)

    # 9. Safety: Safety Center Overview
    @llm.function_tool
    async def get_safety_center() -> str:
        """Get the current safety status, active ride safety info, and available protections."""
        async with AsyncSessionLocal() as db:
            res = await execute_tool("get_safety_center_tool", {}, current_user, db)
            if res.get("success"):
                sc = res.get("safety_center", {})
                contacts_count = sc.get("trusted_contacts_count", 0)
                active_ride = sc.get("active_ride")
                ride_bit = ""
                if active_ride:
                    ride_bit = f" Active ride #{active_ride.get('ride_id')} with driver {active_ride.get('driver_name', 'assigned')}."
                return f"Safety shield is active. You have {contacts_count} trusted contacts configured.{ride_bit} Available actions: SOS, Share Ride, Vehicle Details."
            return "Safety center is active and monitoring your ride."

    tools.append(get_safety_center)

    # 10. Safety: SOS Trigger
    @llm.function_tool
    async def trigger_sos() -> str:
        """Trigger an emergency SOS alert. This logs a critical safety event and notifies the RideNow safety team. It does NOT contact police or ambulance."""
        async with AsyncSessionLocal() as db:
            res = await execute_tool("trigger_sos_tool", {"trigger_type": "VOICE_SOS"}, current_user, db)
            sos = res.get("sos", {})
            event_id = sos.get("event_id") or res.get("event_id", "N/A")
            return (
                f"SOS emergency event #{event_id} has been activated and the safety team has been notified. "
                f"Important: RideNow cannot contact police or ambulance directly. "
                f"Please call one-one-two immediately for emergency services."
            )

    tools.append(trigger_sos)

    # 11. Safety: Share Ride
    @llm.function_tool
    async def prepare_ride_share(ride_id: int = 0) -> str:
        """Generate a shareable live ride tracking link for trusted contacts. The link is NOT automatically sent — user must share it manually."""
        async with AsyncSessionLocal() as db:
            from app.ai.agent.context import get_user_context
            ctx = await get_user_context(current_user.id, role=current_user.role)
            actual_ride_id = ride_id or ctx.active_ride_id
            if not actual_ride_id:
                active_res = await execute_tool("get_active_ride", {}, current_user, db)
                actual_ride_id = active_res.get("ride_id")
            if not actual_ride_id:
                return "You do not have an active ride to share right now."
            res = await execute_tool("prepare_ride_share_tool", {"ride_id": actual_ride_id}, current_user, db)
            share = res.get("share", {})
            share_url = share.get("share_url") or res.get("share_url", "")
            return (
                f"A ride share link has been created. The link is {share_url}. "
                f"Please copy and share it manually with your trusted contacts. "
                f"The link has not been sent automatically."
            )

    tools.append(prepare_ride_share)

    # 12. Safety: Vehicle Details
    @llm.function_tool
    async def get_vehicle_details(ride_id: int = 0) -> str:
        """Get the driver name, vehicle model, and license plate number for the current ride."""
        async with AsyncSessionLocal() as db:
            from app.ai.agent.context import get_user_context
            ctx = await get_user_context(current_user.id, role=current_user.role)
            actual_ride_id = ride_id or ctx.active_ride_id
            if not actual_ride_id:
                active_res = await execute_tool("get_active_ride", {}, current_user, db)
                actual_ride_id = active_res.get("ride_id")
            if not actual_ride_id:
                return "No active ride found with an assigned driver."
            res = await execute_tool("get_vehicle_details_tool", {"ride_id": actual_ride_id}, current_user, db)
            v = res.get("vehicle", {})
            d = res.get("driver", {})
            return (
                f"Your driver is {d.get('name', 'Assigned Driver')} with rating {d.get('rating', 'not available')}. "
                f"The vehicle is a {v.get('model', 'standard vehicle')}, type {v.get('type', 'standard')}, "
                f"with plate number {v.get('number', 'not available')}. "
                f"Please verify this at your pickup point."
            )

    tools.append(get_vehicle_details)

    # 13. Safety: Report Concern
    @llm.function_tool
    async def report_safety_concern(description: str) -> str:
        """Report a safety concern or suspicious activity during a ride. This logs a HIGH severity safety event."""
        async with AsyncSessionLocal() as db:
            res = await execute_tool("create_safety_event_tool", {
                "event_type": "USER_REPORTED_CONCERN",
                "severity": "HIGH",
                "description": description,
            }, current_user, db)
            event = res.get("event", {})
            event_id = event.get("id") or res.get("id", "N/A")
            return (
                f"Safety concern #{event_id} has been logged and the safety team has been alerted. "
                f"If you feel in immediate danger, please trigger SOS or call one-one-two for emergency services."
            )

    tools.append(report_safety_concern)

    # 6. Driver specific tools (only if current_user.role == 'driver')
    if current_user.role == "driver":
        @llm.function_tool
        async def get_driver_summary() -> str:
            """Get driver operational summary: online status, earnings today, and completed trips."""
            async with AsyncSessionLocal() as db:
                res = await execute_tool("get_driver_summary", {}, current_user, db)
                if res.get("success"):
                    return f"Driver summary: You are currently {'online' if res.get('is_online') else 'offline'}. Today's earnings are {res.get('today_earnings')} across {res.get('today_rides')} trips."
                return "Could not load driver summary."

        @llm.function_tool
        async def get_route_tip(pickup_location: str = "your location", dropoff_location: str = "destination") -> str:
            """Get route optimization tip for current navigation context."""
            async with AsyncSessionLocal() as db:
                res = await execute_tool("get_route_tip", {"pickup_location": pickup_location, "dropoff_location": dropoff_location}, current_user, db)
                return res.get("tip", "Route is clear. Proceed via primary arterial roads.")

        tools.extend([get_driver_summary, get_route_tip])

    return tools


async def entrypoint(ctx: JobContext):
    """
    LiveKit Agent Job entrypoint.
    Triggered whenever a participant connects to a RideNow voice room.
    """
    logger.info(f"Connecting to voice room: {ctx.room.name}")
    await ctx.connect()

    # Wait for the client participant to join
    participant = await ctx.wait_for_participant()
    logger.info(f"Participant joined: identity={participant.identity}, name={participant.name}")

    # Extract user identity from participant metadata or identity string (e.g. 'user-1')
    user_id = 1
    user_role = "passenger"
    user_name = participant.name or "Commander"

    if participant.metadata:
        try:
            meta = json.loads(participant.metadata)
            user_id = int(meta.get("user_id", user_id))
            user_role = meta.get("role", user_role)
            user_name = meta.get("name", user_name)
        except Exception as e:
            logger.warning(f"Could not parse participant metadata: {e}")
    elif participant.identity and participant.identity.startswith("user-"):
        try:
            user_id = int(participant.identity.split("-")[1])
        except Exception:
            pass

    # Fetch user model from DB
    current_user = None
    try:
        async with AsyncSessionLocal() as db:
            current_user = await get_user_by_id(db, user_id)
    except Exception as e:
        logger.warning(f"Database lookup for user {user_id} failed: {e}")

    if not current_user:
        current_user = User(id=user_id, name=user_name, email=f"{user_id}@test.com", phone="9999999999", password_hash="", role=user_role)

    logger.info(f"Configuring voice agent for {current_user.name} (Role: {current_user.role})")

    # Build tools scoped to this user
    voice_tools = create_voice_tools(current_user)

    # Instructions tailored for concise voice conversation
    voice_system_prompt = (
        f"You are Nova, the RideNow Intelligent Voice Assistant speaking with {current_user.name} ({current_user.role}). "
        "You are speaking over a live real-time audio phone line. "
        "Keep all responses concise, friendly, and natural (1 to 2 short sentences). "
        "Never use markdown, asterisks, bullet points, or tables since they cannot be spoken aloud. "
        "Speak amounts naturally, for example 'fifty rupees' or 'two hundred twenty rupees'. "
        "When the user asks about rides, fares, earnings, or policies, always call the appropriate tool. "
        "If the user speaks in Hindi or Hinglish, understand them and reply in natural friendly conversational Hinglish or English. "
        "If the user wants to cancel a ride, confirm with them before executing the cancellation."
    )

    # Initialize low-latency voice pipeline components
    cartesia_key = settings.CARTESIA_API_KEY
    groq_key = settings.GROQ_API_KEY

    # Cartesia STT (speech-to-text) with multilingual streaming
    stt_plugin = cartesia.STT(
        api_key=cartesia_key,
        model=settings.CARTESIA_STT_MODEL,
        language="en",
    )

    # Silero VAD — use prewarmed instance from prewarm_fnc if available (avoids 1-2 s event-loop block)
    vad_plugin = ctx.proc.userdata.get("vad") or silero.VAD.load(
        min_speech_duration=0.1,
        min_silence_duration=0.5,
    )

    # Groq LLM (openai/gpt-oss-120b for low-latency reasoning via Groq)
    llm_plugin = groq.LLM(
        model=settings.GROQ_MODEL,
        api_key=groq_key,
        temperature=0.2,
    )

    # Cartesia TTS (ultra-natural low-latency voice generation)
    tts_plugin = cartesia.TTS(
        api_key=cartesia_key,
        voice=settings.CARTESIA_VOICE_ID,
        model=settings.CARTESIA_MODEL,
        sample_rate=24000,
    )

    # Create AgentSession — allow_interruptions removed (deprecated in 1.8.x; default is True)
    session = AgentSession(
        stt=stt_plugin,
        vad=vad_plugin,
        llm=llm_plugin,
        tts=tts_plugin,
    )

    # Create Voice Agent with tools and instructions
    agent = Agent(
        instructions=voice_system_prompt,
        tools=voice_tools,
    )

    # Register event handlers for structured log output
    @session.on("agent_state_changed")
    def on_state_changed(evt) -> None:
        logger.info(f"[VOICE AGENT] state: {evt.old_state} -> {evt.new_state}")

    @session.on("user_input_transcribed")
    def on_transcript(evt) -> None:
        if evt.is_final:
            logger.info(f"[VOICE AGENT] user said: {evt.transcript!r}")

    # FIXED: session.start() is a coroutine — MUST be awaited
    logger.info("[VOICE AGENT] AgentSession starting")
    await session.start(agent, room=ctx.room)
    logger.info("[VOICE AGENT] AgentSession started")

    # Build greeting text for this user's role
    first_name = current_user.name.split()[0]
    greeting_text = (
        f"Hello {first_name}! Nova Voice Core is online. How can I help with your ride today?"
        if current_user.role == "passenger"
        else f"Hello Commander {first_name}. Driver Voice Copilot is active. What can I check for you?"
    )

    # FIXED: session.say() returns SpeechHandle — 'now=True' is NOT a valid kwarg.
    # Awaiting the SpeechHandle waits until playout completes.
    logger.info("[VOICE AGENT] greeting started")
    await session.say(greeting_text)
    logger.info("[VOICE AGENT] greeting completed — waiting for user")
    # AgentSession runs its own background tasks (audio forwarding, VAD, LLM loop).
    # Wait until the session closes (e.g. participant disconnects) or shutdown is called.
    close_event = asyncio.Event()

    @session.on("close")
    def on_session_close(evt):
        logger.info(f"[VOICE AGENT] AgentSession closed ({getattr(evt, 'reason', 'normal')}), exiting entrypoint")
        close_event.set()

    ctx.add_shutdown_callback(lambda: close_event.set())

    await close_event.wait()
    logger.info("[VOICE AGENT] Entrypoint finished cleanly")


def main():
    """Start the RideNow Voice Worker process."""
    print("=" * 60)
    print("  RIDENOW AI — LIVEKIT REAL-TIME VOICE AGENT")
    print("=" * 60)
    print(f"  LiveKit Server: {settings.LIVEKIT_URL}")
    print(f"  Groq LLM Model: {settings.GROQ_MODEL}")
    print(f"  Cartesia Voice: {settings.CARTESIA_VOICE_ID}")
    print(f"  Cartesia TTS:   {settings.CARTESIA_MODEL}")
    print(f"  Cartesia STT:   {settings.CARTESIA_STT_MODEL}")
    print("=" * 60)

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            ws_url=settings.LIVEKIT_URL,
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
            agent_name="",
            num_idle_processes=0,
            load_threshold=1.0,
        )
    )


if __name__ == "__main__":
    main()
