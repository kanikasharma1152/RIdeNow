from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="User's query, prompt, or command")
    input_type: Optional[str] = Field("text", description="Input modality: text, voice, image, location, or multimodal")
    image_base64: Optional[str] = Field(None, description="Optional base64 image data for visual location identification")
    latitude: Optional[float] = Field(None, description="Optional user GPS latitude")
    longitude: Optional[float] = Field(None, description="Optional user GPS longitude")


class ToolExecutionTrace(BaseModel):
    tool: str
    args: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    reply: str
    tools_executed: List[ToolExecutionTrace] = []
    suggested_actions: List[str] = []
    visual_context: Optional[Dict[str, Any]] = None
    input_modality: Optional[str] = "text"
