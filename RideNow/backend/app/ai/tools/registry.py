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
from app.ai.tools.booking_tools import book_ride_tool
from app.ai.tools.safety_tools import (
    get_ride_safety_events_tool,
    get_my_safety_summary_tool,
    get_safety_center_tool,
    get_active_safety_events_tool,
    create_safety_event_tool,
    trigger_sos_tool,
    get_trusted_contacts_tool,
    create_trusted_contact_tool,
    delete_trusted_contact_tool,
    prepare_ride_share_tool,
    get_driver_live_location_tool,
    get_vehicle_details_tool,
    get_route_deviation_status_tool,
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
from app.ai.tools.mobility_tools import (
    get_demand_forecast_tool,
    get_eta_prediction_tool,
    get_smart_pickup_points_tool,
    get_trip_plan_tool,
    get_user_mobility_summary_tool,
    get_ride_recommendation_tool,
    get_driver_matching_explanation_tool,
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
    {
        "name": "book_ride",
        "description": "Book a new ride for the passenger. When confirmed=false, calculates route and returns fare summary asking user for confirmation. When confirmed=true, creates the trip and initiates driver matching.",
        "parameters": {
            "type": "object",
            "properties": {
                "pickup_location": {"type": "string", "description": "Street address or landmark where passenger will be picked up."},
                "dropoff_location": {"type": "string", "description": "Destination street address or landmark."},
                "confirmed": {"type": "boolean", "description": "Set to true only after passenger explicitly confirms the booking (e.g. 'yes', 'confirm', 'book it').", "default": False},
                "pickup_latitude": {"type": "number", "description": "Optional GPS latitude of pickup."},
                "pickup_longitude": {"type": "number", "description": "Optional GPS longitude of pickup."},
                "dropoff_latitude": {"type": "number", "description": "Optional GPS latitude of dropoff."},
                "dropoff_longitude": {"type": "number", "description": "Optional GPS longitude of dropoff."},
            },
            "required": ["dropoff_location"],
        },
        "allowed_roles": ["passenger"],
    },
    {
        "name": "get_ride_safety_events",
        "description": "Fetch safety events, route notices, or active SOS status for a specific trip by its ride_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "ride_id": {"type": "integer", "description": "The ride ID to check safety events for."}
            },
            "required": ["ride_id"],
        },
        "allowed_roles": ["passenger", "driver", "admin"],
    },
    {
        "name": "get_my_safety_summary",
        "description": "Fetch a summary of safety events and status across the user's recent trips.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "allowed_roles": ["passenger", "driver", "admin"],
    },
    {
        "name": "get_safety_center",
        "description": "Retrieve the user's Safety Command Center overview, including active ride status, driver/vehicle details, trusted contacts, and capability boundaries.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "allowed_roles": ["passenger", "driver", "admin"],
    },
    {
        "name": "get_active_safety_events",
        "description": "Retrieve all open/active safety events or notices involving the user.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "allowed_roles": ["passenger", "driver", "admin"],
    },
    {
        "name": "create_safety_event",
        "description": "Report a safety concern (e.g. ROUTE_DEVIATION, DRIVER_BEHAVIOR, VEHICLE_ISSUE, or GENERAL_CONCERN).",
        "parameters": {
            "type": "object",
            "properties": {
                "event_type": {"type": "string", "description": "Type of event (SAFETY_CONCERN, ROUTE_DEVIATION, PICKUP_MISMATCH, VEHICLE_ISSUE)"},
                "severity": {"type": "string", "description": "Severity: LOW, MEDIUM, HIGH, CRITICAL", "default": "MEDIUM"},
                "description": {"type": "string", "description": "Details of the safety concern"},
                "ride_id": {"type": "integer", "description": "Optional associated ride ID"},
            },
            "required": ["event_type", "description"],
        },
        "allowed_roles": ["passenger", "driver"],
    },
    {
        "name": "trigger_sos",
        "description": "Activate internal emergency SOS safety event. Alert platform command center.",
        "parameters": {
            "type": "object",
            "properties": {
                "note": {"type": "string", "description": "Emergency note or details"},
                "ride_id": {"type": "integer", "description": "Optional active ride ID"},
            },
            "required": [],
        },
        "allowed_roles": ["passenger", "driver"],
    },
    {
        "name": "get_trusted_contacts",
        "description": "Retrieve list of emergency trusted contacts configured by the user.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "allowed_roles": ["passenger", "driver"],
    },
    {
        "name": "create_trusted_contact",
        "description": "Add a new trusted contact for emergency trip sharing and notifications.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Contact full name"},
                "phone": {"type": "string", "description": "Contact phone number with area/country code"},
                "relationship": {"type": "string", "description": "Relationship e.g. Mother, Father, Friend, Partner"},
            },
            "required": ["name", "phone"],
        },
        "allowed_roles": ["passenger", "driver"],
    },
    {
        "name": "delete_trusted_contact",
        "description": "Remove an existing trusted contact by ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "integer", "description": "ID of trusted contact to remove"},
            },
            "required": ["contact_id"],
        },
        "allowed_roles": ["passenger", "driver"],
    },
    {
        "name": "prepare_ride_share",
        "description": "Generate privacy-preserving live tracking link and formatted trip status text to share with family or friends.",
        "parameters": {
            "type": "object",
            "properties": {
                "ride_id": {"type": "integer", "description": "Optional ride ID to share (defaults to current active ride)"},
            },
            "required": [],
        },
        "allowed_roles": ["passenger"],
    },
    {
        "name": "get_driver_live_location",
        "description": "Get real-time GPS coordinates and ETA of assigned driver for active trip.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "allowed_roles": ["passenger"],
    },
    {
        "name": "get_vehicle_details",
        "description": "Retrieve exact vehicle model, license plate number, and driver name for the current active ride.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "allowed_roles": ["passenger"],
    },
    {
        "name": "get_route_deviation_status",
        "description": "Check if current trip vehicle has diverted away from expected planned route corridor.",
        "parameters": {
            "type": "object",
            "properties": {
                "ride_id": {"type": "integer", "description": "Optional ride ID"},
            },
            "required": [],
        },
        "allowed_roles": ["passenger", "driver"],
    },
    {
        "name": "get_demand_forecast",
        "description": "Fetch real-time zone demand level (LOW/MEDIUM/HIGH), demand score, and traffic multiplier for a location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "Street address, area, or landmark name"},
                "latitude": {"type": "number", "description": "Optional GPS latitude"},
                "longitude": {"type": "number", "description": "Optional GPS longitude"},
            },
            "required": [],
        },
        "allowed_roles": ["passenger", "driver", "admin", "public"],
    },
    {
        "name": "get_eta_prediction",
        "description": "Calculate estimated travel duration (minutes) and distance between pickup and dropoff factoring in live traffic congestion.",
        "parameters": {
            "type": "object",
            "properties": {
                "pickup_location": {"type": "string", "description": "Origin location or landmark"},
                "dropoff_location": {"type": "string", "description": "Destination location or landmark"},
                "pickup_latitude": {"type": "number", "description": "Optional pickup GPS latitude"},
                "pickup_longitude": {"type": "number", "description": "Optional pickup GPS longitude"},
                "dropoff_latitude": {"type": "number", "description": "Optional dropoff GPS latitude"},
                "dropoff_longitude": {"type": "number", "description": "Optional dropoff GPS longitude"},
            },
            "required": ["dropoff_location"],
        },
        "allowed_roles": ["passenger", "driver", "admin", "public"],
    },
    {
        "name": "get_smart_pickup_points",
        "description": "Suggest convenient curbside and landmark pickup spots near a location that reduce driver search time and walking effort.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "Location or landmark name"},
                "latitude": {"type": "number", "description": "Optional GPS latitude"},
                "longitude": {"type": "number", "description": "Optional GPS longitude"},
            },
            "required": [],
        },
        "allowed_roles": ["passenger", "driver", "admin", "public"],
    },
    {
        "name": "get_trip_plan",
        "description": "Plan a journey with calculated target departure time (to meet arrival deadline), estimated travel duration, traffic congestion, and fare estimate. Does NOT auto-book.",
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Destination address or landmark"},
                "origin": {"type": "string", "description": "Starting address or landmark (defaults to current location)"},
                "target_arrival_time": {"type": "string", "description": "Desired arrival time (e.g. '8:00 PM', '14:30', '9 AM')"},
                "preferred_departure_time": {"type": "string", "description": "Optional departure time if planning ahead"},
            },
            "required": ["destination"],
        },
        "allowed_roles": ["passenger", "driver", "admin", "public"],
    },
    {
        "name": "get_user_mobility_summary",
        "description": "Retrieve personal travel analytics for the authenticated user, including total spend (INR), completed ride count, top destinations, and preferred travel hours.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "allowed_roles": ["passenger", "driver", "admin"],
    },
    {
        "name": "get_ride_recommendation",
        "description": "Get proactive advice on optimal departure times, peak traffic avoidance, and smart pickup points for a destination.",
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Destination address or landmark"},
                "origin": {"type": "string", "description": "Starting location (defaults to current location)"},
                "target_time": {"type": "string", "description": "Optional planned departure or arrival time"},
            },
            "required": ["destination"],
        },
        "allowed_roles": ["passenger", "driver", "admin", "public"],
    },
    {
        "name": "get_driver_matching_explanation",
        "description": "Explain how RideNow's ML Smart Match algorithm ranks and pairs drivers (distance, congestion ETA, rating, acceptance rate) and check nearby availability.",
        "parameters": {
            "type": "object",
            "properties": {
                "pickup_latitude": {"type": "number", "description": "Optional pickup latitude"},
                "pickup_longitude": {"type": "number", "description": "Optional pickup longitude"},
            },
            "required": [],
        },
        "allowed_roles": ["passenger", "driver", "admin", "public"],
    },
] + COPILOT_TOOL_DEFINITIONS + ADMIN_TOOL_DEFINITIONS

TOOL_FUNCTIONS = {
    "get_active_ride": get_active_ride_tool,
    "get_ride_history": get_ride_history_tool,
    "estimate_fare": estimate_fare_tool,
    "cancel_ride": cancel_ride_tool,
    "book_ride": book_ride_tool,
    "get_driver_status": get_driver_status_tool,
    "get_driver_earnings": get_driver_earnings_tool,
    "search_policies_and_faq": search_policies_and_faq_tool,
    "get_user_profile": get_user_profile_tool,
    "get_notifications": get_notifications_tool,
    "mark_notification_read": mark_notification_read_tool,
    "get_rating": get_rating_tool,
    "get_payment_status": get_payment_status_tool,
    "get_ride_safety_events": get_ride_safety_events_tool,
    "get_my_safety_summary": get_my_safety_summary_tool,
    "get_safety_center": get_safety_center_tool,
    "get_safety_center_tool": get_safety_center_tool,
    "get_active_safety_events": get_active_safety_events_tool,
    "get_active_safety_events_tool": get_active_safety_events_tool,
    "create_safety_event": create_safety_event_tool,
    "create_safety_event_tool": create_safety_event_tool,
    "trigger_sos": trigger_sos_tool,
    "trigger_sos_tool": trigger_sos_tool,
    "get_trusted_contacts": get_trusted_contacts_tool,
    "get_trusted_contacts_tool": get_trusted_contacts_tool,
    "create_trusted_contact": create_trusted_contact_tool,
    "create_trusted_contact_tool": create_trusted_contact_tool,
    "delete_trusted_contact": delete_trusted_contact_tool,
    "delete_trusted_contact_tool": delete_trusted_contact_tool,
    "prepare_ride_share": prepare_ride_share_tool,
    "prepare_ride_share_tool": prepare_ride_share_tool,
    "get_driver_live_location": get_driver_live_location_tool,
    "get_driver_live_location_tool": get_driver_live_location_tool,
    "get_vehicle_details": get_vehicle_details_tool,
    "get_vehicle_details_tool": get_vehicle_details_tool,
    "get_route_deviation_status": get_route_deviation_status_tool,
    "get_route_deviation_status_tool": get_route_deviation_status_tool,
    "get_demand_forecast": get_demand_forecast_tool,
    "get_eta_prediction": get_eta_prediction_tool,
    "get_smart_pickup_points": get_smart_pickup_points_tool,
    "get_trip_plan": get_trip_plan_tool,
    "get_user_mobility_summary": get_user_mobility_summary_tool,
    "get_ride_recommendation": get_ride_recommendation_tool,
    "get_driver_matching_explanation": get_driver_matching_explanation_tool,
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
