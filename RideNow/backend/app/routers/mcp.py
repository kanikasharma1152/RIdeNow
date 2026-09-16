"""
RideNow MCP FastAPI Router
==========================
Exposes standard MCP JSON-RPC 2.0 endpoints for tool discovery and execution.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional

from app.database import get_db
from app.core.security import decode_access_token
from app.repositories.user import get_user_by_id
from app.mcp.server import mcp_server

oauth2_optional = OAuth2PasswordBearer(tokenUrl="/users/login", auto_error=False)

router = APIRouter(
    prefix="/mcp",
    tags=["MCP"],
)


async def get_optional_user(
    token: Optional[str] = Depends(oauth2_optional),
    db: AsyncSession = Depends(get_db),
):
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        return None
    try:
        user = await get_user_by_id(db, int(payload["sub"]))
        return user if (user and user.is_active) else None
    except Exception:
        return None


@router.get("/tools")
async def list_mcp_tools(
    current_user=Depends(get_optional_user),
):
    """List all available MCP tools based on caller role."""
    return {"tools": mcp_server.list_tools(current_user=current_user)}


@router.post("")
async def handle_mcp_rpc(
    request: Request,
    current_user=Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Handle standard JSON-RPC 2.0 MCP requests."""
    payload = await request.json()
    response = await mcp_server.handle_jsonrpc_request(
        payload=payload,
        current_user=current_user,
        db=db,
    )
    return response
