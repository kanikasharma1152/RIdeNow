from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User's query or prompt")


class ToolExecutionTrace(BaseModel):
    tool: str
    args: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    reply: str
    tools_executed: List[ToolExecutionTrace] = []
    suggested_actions: List[str] = []
