"""
RideNow Admin AI Tools — Phase 7
================================
AI tools accessible exclusively to users with role="admin".
Provides administrative analytics and KPI aggregation through the AI interface.
"""

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics import get_dashboard_analytics, generate_ai_insights


async def get_admin_analytics_tool(
    current_user,
    db: AsyncSession,
    **kwargs,
) -> Dict[str, Any]:
    """
    Get executive platform KPIs: ride count, completion rate, GMV, and active drivers.
    """
    if current_user.role != "admin":
        return {"success": False, "message": "Admin analytics are restricted to system administrators."}

    data = await get_dashboard_analytics(db)
    return data


async def get_admin_insights_tool(
    current_user,
    db: AsyncSession,
    **kwargs,
) -> Dict[str, Any]:
    """
    Generate AI strategic insights and optimization advice for platform operations.
    """
    if current_user.role != "admin":
        return {"success": False, "message": "Admin insights are restricted to system administrators."}

    data = await generate_ai_insights(db)
    return data


ADMIN_TOOL_DEFINITIONS = [
    {
        "name": "get_admin_analytics",
        "description": "Fetch aggregate platform performance metrics: total rides, GMV, completion rate, and driver availability.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "allowed_roles": ["admin"],
    },
    {
        "name": "get_admin_insights",
        "description": "Generate AI strategic operational recommendations from platform metrics.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "allowed_roles": ["admin"],
    },
]

ADMIN_TOOL_FUNCTIONS = {
    "get_admin_analytics": get_admin_analytics_tool,
    "get_admin_insights": get_admin_insights_tool,
}
