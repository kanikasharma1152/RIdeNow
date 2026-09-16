"""
RideNow AI — Central Tool Registry (MCP Architecture)
=====================================================
Dispatches AI tool calls to their respective verified functions.
Enforces:
1. Authentication & Role Validation
2. Resource ownership & parameter sanitation
3. Direct execution through existing service layer (NO DIRECT DB ACCESS)
4. Standardized execution traces and output structures
"""

import inspect
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tools.ride_tools import (
    get_active_ride_tool,
    get_ride_history_tool,
    estimate_fare_tool,
    cancel_ride_tool,
)
from app.ai.tools.driver_tools import (
    get_driver_status_tool,
    get_driver_earnings_tool,
)
from app.ai.tools.knowledge_tools import search_policies_and_faq_tool
from app.ai.tools.copilot_tools import COPILOT_TOOL_DEFINITIONS, COPILOT_TOOL_FUNCTIONS
from app.ai.tools.admin_tools import ADMIN_TOOL_DEFINITIONS, ADMIN_TOOL_FUNCTIONS
from app.ai.tools.extra_tools import (
    get_user_profile_tool,
    get_notifications_tool,
    mark_notification_read_tool,
    get_rating_tool,
    get_payment_status_tool,
)

logger = logging.getLogger(__name__)

# Tool metadata and definitions for LLM function calling / prompt descriptions
TOOL_DEFINITIONS = [
    {
        "name": "get_active_ride",
        "description": "Fetch the user's currently active ride in progress (REQUESTED, ACCEPTED, or STARTED), including pickup, dropoff, and live status.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "allowed_roles": ["passenger", "driver"],
    },
    {
        "name": "get_ride_history",
        "description": "Retrieve recent past rides for the user, showing destination, date, status, and fare.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of recent trips to return (default 5)", "default": 5}
            },
            "required": [],
        },
        "allowed_roles": ["passenger", "driver"],
    },
    {
        "name": "estimate_fare",
        "description": "Calculate estimated fare for a trip given either a distance in km, or pickup and dropoff addresses.",
        "parameters": {
            "type": "object",
            "properties": {
                "distance_km": {"type": "number", "description": "Distance in kilometers"},
                "pickup_address": {"type": "string", "description": "Pickup street address or landmark"},
                "dropoff_address": {"type": "string", "description": "Dropoff street address or landmark"},
            },
            "required": [],
        },
        "allowed_roles": ["passenger", "driver", "public"],
    },
    {
        "name": "cancel_ride",
        "description": "Cancel an active ride request. If confirmed=false, returns a safety confirmation prompt. If confirmed=true, cancels the ride.",
        "parameters": {
            "type": "object",
            "properties": {
                "ride_id": {"type": "integer", "description": "The ID of the ride to cancel"},
                "confirmed": {"type": "boolean", "description": "Whether user explicitly confirmed cancellation", "default": False},
            },
            "required": ["ride_id"],
        },
        "allowed_roles": ["passenger"],
    },
    {
        "name": "get_driver_status",
        "description": "Get current driver profile, vehicle details, and whether the driver is online or available.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "allowed_roles": ["driver"],
    },
    {
        "name": "get_driver_earnings",
        "description": "Get driver earnings summary (today, this week, this month, and total earnings).",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "allowed_roles": ["driver"],
    },
    {
        "name": "search_policies_and_faq",
        "description": "Search the official RideNow knowledge base for policy rules, FAQs, cancellation terms, safety guidelines, and driver guides.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Question or policy topic to look up"}
            },
            "required": ["query"],
        },
        "allowed_roles": ["passenger", "driver", "public"],
    },
    {
        "name": "get_user_profile",
        "description": "Get current user profile information including name, email, phone number, and account role.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "allowed_roles": ["passenger", "driver", "admin"],
    },
    {
        "name": "get_notifications",
        "description": "Fetch user's recent notifications and check unread message count.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of recent notifications to retrieve (default 5)", "default": 5}
            },
            "required": [],
        },
        "allowed_roles": ["passenger", "driver", "admin"],
    },
    {
        "name": "mark_notification_read",
        "description": "Mark a specific notification as read or mark all notifications as read.",
        "parameters": {
            "type": "object",
            "properties": {
                "notification_id": {"type": "integer", "description": "Optional ID of a specific notification to mark as read"},
                "mark_all": {"type": "boolean", "description": "Set to true to mark all notifications as read", "default": False},
            },
            "required": [],
        },
        "allowed_roles": ["passenger", "driver", "admin"],
    },
    {
        "name": "get_rating",
        "description": "Check rating statistics. For drivers, returns average rating score and recent reviews. For passengers, returns rating info.",
        "parameters": {
            "type": "object",
            "properties": {
                "ride_id": {"type": "integer", "description": "Optional ride ID to check specific rating"}
            },
            "required": [],
        },
        "allowed_roles": ["passenger", "driver"],
    },
    {
        "name": "get_payment_status",
        "description": "Check fare and payment status for the user's active or most recent ride.",
        "parameters": {
            "type": "object",
            "properties": {
                "ride_id": {"type": "integer", "description": "Optional ride ID to check payment for"}
            },
            "required": [],
        },
        "allowed_roles": ["passenger", "driver"],
    },
] + COPILOT_TOOL_DEFINITIONS + ADMIN_TOOL_DEFINITIONS

TOOL_FUNCTIONS = {
    "get_active_ride": get_active_ride_tool,
    "get_ride_history": get_ride_history_tool,
    "estimate_fare": estimate_fare_tool,
    "cancel_ride": cancel_ride_tool,
    "get_driver_status": get_driver_status_tool,
    "get_driver_earnings": get_driver_earnings_tool,
    "search_policies_and_faq": search_policies_and_faq_tool,
    "get_user_profile": get_user_profile_tool,
    "get_notifications": get_notifications_tool,
    "mark_notification_read": mark_notification_read_tool,
    "get_rating": get_rating_tool,
    "get_payment_status": get_payment_status_tool,
    **COPILOT_TOOL_FUNCTIONS,
    **ADMIN_TOOL_FUNCTIONS,
}


def get_available_tools_for_role(role: str) -> List[Dict[str, Any]]:
    """Return tool schemas filtered by the user's role."""
    return [
        t for t in TOOL_DEFINITIONS
        if "public" in t["allowed_roles"] or role in t["allowed_roles"]
    ]


async def execute_tool(
    tool_name: str,
    tool_args: Dict[str, Any],
    current_user,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Safely executes a registered tool.
    Validates permissions, injects current_user and db session, and handles exceptions.
    """
    func = TOOL_FUNCTIONS.get(tool_name)
    if not func:
        logger.warning(f"Unknown tool requested: {tool_name}")
        return {"success": False, "error": f"Tool '{tool_name}' is not recognized."}

    # Find tool definition
    defn = next((t for t in TOOL_DEFINITIONS if t["name"] == tool_name), None)
    if defn:
        allowed = defn.get("allowed_roles", [])
        if "public" not in allowed and (not current_user or current_user.role not in allowed):
            logger.warning(f"Unauthorized tool execution: {tool_name} by role {getattr(current_user, 'role', 'anonymous')}")
            return {
                "success": False,
                "error": f"Permission denied: {tool_name} is only available to {allowed}.",
            }

    try:
        # Prepare parameters according to what the function accepts.
        # Groq/OpenAI pass flattened JSON arguments; some tools historically
        # expected a single `args` dict. Support both without crashing.
        sig = inspect.signature(func)
        accepts_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        kwargs = dict(tool_args or {})

        if "args" in sig.parameters and "args" not in kwargs:
            kwargs["args"] = dict(tool_args or {})

        if "current_user" in sig.parameters:
            kwargs["current_user"] = current_user
        if "db" in sig.parameters:
            kwargs["db"] = db

        if not accepts_var_keyword:
            kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}

        res = await func(**kwargs)
        return res
    except Exception as exc:
        logger.error(f"Error executing tool '{tool_name}': {exc}", exc_info=True)
        return {"success": False, "error": "Tool execution failed."}
