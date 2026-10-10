"""
RideNow — Multimodal Vision API Router
======================================
Provides visual location intelligence:
- Image landmark & signage extraction
- Visual location understanding combined with GPS telemetry
- Clean capability reporting when vision models are not present
"""

import base64
import logging
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel

from app.routers.user import get_current_user
from app.services.location_intelligence import analyze_visual_location

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/vision",
    tags=["Vision & Multimodal"],
)


class VisionAnalyzeRequest(BaseModel):
    image_base64: str
    query: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@router.post(
    "/analyze-location",
    summary="Analyze visual photo for location landmarks",
    description="Processes uploaded image with location intelligence and GPS context.",
)
async def analyze_location(
    image: Optional[UploadFile] = File(None),
    query: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    current_user=Depends(get_current_user),
):
    """Multipart form endpoint for image uploads."""
    if not image:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image file is required for visual location analysis.",
        )

    try:
        content = await image.read()
        if len(content) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Image size exceeds maximum allowed limit of 10MB.",
            )

        image_b64 = base64.b64encode(content).decode("utf-8")
        result = await analyze_visual_location(
            image_base64=image_b64,
            query=query,
            user_latitude=latitude,
            user_longitude=longitude,
        )
        return {"success": True, **result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error in analyze_location: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process image for visual location.",
        )


@router.post(
    "/analyze-location-json",
    summary="Analyze base64 photo for location landmarks",
    description="JSON payload endpoint for direct base64 image data.",
)
async def analyze_location_json(
    payload: VisionAnalyzeRequest,
    current_user=Depends(get_current_user),
):
    try:
        result = await analyze_visual_location(
            image_base64=payload.image_base64,
            query=payload.query,
            user_latitude=payload.latitude,
            user_longitude=payload.longitude,
        )
        return {"success": True, **result}
    except Exception as exc:
        logger.error(f"Error in analyze_location_json: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process image for visual location.",
        )
