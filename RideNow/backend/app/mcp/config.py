"""
RideNow MCP (Model Context Protocol) Server Configuration
==========================================================
Standard MCP tool definitions and protocol specification.
Reuses definitions directly from app.ai.tools.registry.
"""

from typing import Dict, Any, List
from app.ai.tools.registry import TOOL_DEFINITIONS

MCP_SERVER_NAME = "ridenow-mobility-mcp"
MCP_SERVER_VERSION = "1.0.0"
MCP_PROTOCOL_VERSION = "2024-11-05"

# Expose initial core capabilities via MCP standard inputSchema format
MCP_TOOL_NAMES = {
    "get_active_ride",
    "estimate_fare",
    "get_ride_history",
    "get_user_profile",
    "get_notifications",
    "get_payment_status",
    "get_rating",
    "get_driver_earnings",
    "get_driver_summary",
    "get_route_tip",
    "search_policies_and_faq",
}

MCP_TOOL_SPECS: List[Dict[str, Any]] = []
for tool in TOOL_DEFINITIONS:
    if tool["name"] in MCP_TOOL_NAMES:
        MCP_TOOL_SPECS.append({
            "name": tool["name"],
            "description": tool["description"],
            "inputSchema": tool.get("parameters", {"type": "object", "properties": {}, "required": []}),
            "allowed_roles": tool.get("allowed_roles", ["passenger", "driver"]),
        })
