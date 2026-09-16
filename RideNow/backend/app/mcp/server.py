"""
RideNow MCP Server Implementation
=================================
JSON-RPC 2.0 compliant Model Context Protocol handler.
Provides tools/list and tools/call methods securely connected to existing RideNow services.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.config import (
    MCP_SERVER_NAME,
    MCP_SERVER_VERSION,
    MCP_PROTOCOL_VERSION,
    MCP_TOOL_SPECS,
)
from app.ai.tools.registry import execute_tool

logger = logging.getLogger(__name__)


class MCPServer:
    """
    Model Context Protocol (MCP) Server for RideNow.
    Exposes validated tool endpoints over standard JSON-RPC protocol.
    """

    def __init__(self):
        self.server_name = MCP_SERVER_NAME
        self.server_version = MCP_SERVER_VERSION
        self.protocol_version = MCP_PROTOCOL_VERSION

    def list_tools(self, current_user=None) -> List[Dict[str, Any]]:
        """
        List all tools available to the given user based on their authenticated role.
        """
        user_role = getattr(current_user, "role", "public") if current_user else "public"
        available = []
        for tool in MCP_TOOL_SPECS:
            allowed = tool.get("allowed_roles", [])
            if "public" in allowed or user_role in allowed:
                available.append({
                    "name": tool["name"],
                    "description": tool["description"],
                    "inputSchema": tool["inputSchema"],
                })
        return available

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        current_user,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Execute an MCP tool request through RideNow's existing verified service layer.
        Reuses all business logic, role checks, and ownership constraints.
        """
        # 1. Verify tool exists in MCP specs
        spec = next((t for t in MCP_TOOL_SPECS if t["name"] == tool_name), None)
        if not spec:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Tool '{tool_name}' not found on MCP server."}],
            }

        # 2. Verify role authorization
        user_role = getattr(current_user, "role", "public") if current_user else "public"
        allowed_roles = spec.get("allowed_roles", [])
        if "public" not in allowed_roles and user_role not in allowed_roles:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Permission denied: '{tool_name}' requires one of {allowed_roles} roles."}],
            }

        # 3. Dispatch to verified existing RideNow tools registry
        try:
            result = await execute_tool(
                tool_name=tool_name,
                tool_args=arguments or {},
                current_user=current_user,
                db=db,
            )

            is_error = False
            if isinstance(result, dict) and result.get("success") is False:
                is_error = True

            return {
                "isError": is_error,
                "content": [{"type": "text", "text": json.dumps(result, default=str, ensure_ascii=False)}],
                "data": result,
            }
        except Exception as exc:
            logger.error(f"[MCP] Error executing {tool_name}: {exc}", exc_info=True)
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"MCP execution failure: {str(exc)}"}],
            }

    async def handle_jsonrpc_request(
        self,
        payload: Dict[str, Any],
        current_user,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Process standard JSON-RPC 2.0 MCP request.
        """
        req_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params") or {}

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": self.protocol_version,
                    "serverInfo": {
                        "name": self.server_name,
                        "version": self.server_version,
                    },
                    "capabilities": {
                        "tools": {"listChanged": False},
                    },
                },
            }

        elif method == "tools/list":
            tools = self.list_tools(current_user=current_user)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": tools},
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments") or {}
            result = await self.call_tool(
                tool_name=tool_name,
                arguments=arguments,
                current_user=current_user,
                db=db,
            )
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result,
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not found",
                },
            }


# Singleton server instance
mcp_server = MCPServer()
