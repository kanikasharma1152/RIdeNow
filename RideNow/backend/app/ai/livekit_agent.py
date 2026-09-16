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
                return f"Estimated fare for {res.get('distance_km')} kilometers is {res.get('estimated_fare')}. Base fare is 50 rupees plus 12 rupees per kilometer."
            return f"Could not estimate fare: {res.get('message', 'invalid parameters')}"

    tools.append(estimate_fare)

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
        logger.info(f"[VOICE AGENT] state: {evt.old_state} → {evt.new_state}")

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
    # The entrypoint must NOT return immediately or those tasks are cancelled.
    # We await a never-resolving Future so the job stays alive until LiveKit closes it.
    await asyncio.get_event_loop().create_future()


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
        )
    )


if __name__ == "__main__":
    main()
