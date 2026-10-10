"""
RideNow — Location Intelligence Service
=======================================
Combines:
- NLP location query resolution
- Candidate geocoding via Nominatim
- Multimodal visual location extraction via VisionProvider
- Disambiguation for ambiguous landmarks
"""

import logging
import re
from typing import Dict, Any, List, Optional
import httpx

from app.services.google_map import geocode_address
from app.ai.llm.vision_provider import get_vision_provider

logger = logging.getLogger(__name__)

# Common landmarks & transit hubs in major Indian cities for disambiguation assistance
CITY_LANDMARKS = {
    "airport": ["Devi Ahilyabai Holkar Airport, Indore", "Raja Bhoj Airport, Bhopal", "Kempegowda International Airport, Bengaluru"],
    "station": ["Indore Junction Railway Station", "Bhopal Junction Railway Station", "Rani Kamlapati Railway Station"],
    "railway station": ["Indore Junction Railway Station", "Bhopal Junction Railway Station", "Krantivira Sangolli Rayanna (Bengaluru City) Station"],
}


async def search_location_candidates(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Search location candidates with Nominatim OpenStreetMap.
    Returns list of {"name": ..., "latitude": ..., "longitude": ..., "display_name": ...}
    """
    clean_q = query.strip()
    if not clean_q:
        return []

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": clean_q,
        "format": "json",
        "limit": limit,
        "addressdetails": 1,
    }
    headers = {"User-Agent": "RideNow-LocationIntelligence/1.0"}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            candidates = []
            for item in data:
                candidates.append({
                    "name": item.get("display_name", "").split(",")[0],
                    "display_name": item.get("display_name", ""),
                    "latitude": float(item["lat"]),
                    "longitude": float(item["lon"]),
                    "type": item.get("type", "landmark"),
                })
            return candidates
    except Exception as exc:
        logger.warning(f"Nominatim candidate search failed for '{query}': {exc}")

    # Fallback to single geocode
    try:
        coords = await geocode_address(clean_q)
        return [{
            "name": clean_q,
            "display_name": clean_q,
            "latitude": coords["latitude"],
            "longitude": coords["longitude"],
            "type": "location",
        }]
    except Exception:
        return []


def check_ambiguity(location_name: str) -> Optional[List[str]]:
    """
    Detect if a location name is overly generic (e.g. 'airport', 'railway station')
    and returns disambiguation options if ambiguous.
    """
    loc_lower = location_name.lower().strip()
    for key, options in CITY_LANDMARKS.items():
        if loc_lower == key or loc_lower == f"the {key}":
            return options
    return None


async def analyze_visual_location(
    image_base64: str,
    query: Optional[str] = None,
    user_latitude: Optional[float] = None,
    user_longitude: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Process image using VisionProvider and combine with GPS coordinates.
    """
    provider = get_vision_provider()
    return await provider.analyze_location_image(
        image_base64=image_base64,
        query=query,
        user_latitude=user_latitude,
        user_longitude=user_longitude,
    )
