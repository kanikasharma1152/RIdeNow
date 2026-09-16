"""
RideNow MCP Client
==================
Async MCP client used by the AI Agent and external components to invoke MCP tools.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.mcp.server import mcp_server


class MCPClient:
    """
    Client interface for calling RideNow MCP tools.
    """

    def __init__(self, server=mcp_server):
        self.server = server

    def list_available_tools(self, current_user=None) -> List[Dict[str, Any]]:
        """List tools available for the current user session."""
        return self.server.list_tools(current_user=current_user)

    async def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        current_user,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Execute a tool via MCP and return unmarshaled tool output."""
        response = await self.server.call_tool(
            tool_name=name,
            arguments=arguments,
            current_user=current_user,
            db=db,
        )
        return response.get("data") or response


mcp_client = MCPClient()
