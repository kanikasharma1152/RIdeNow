import json
import logging
import httpx

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

GEOCODE_CACHE_TTL = 86400  # 24 hours
ROUTE_CACHE_TTL = 3600     # 1 hour


async def geocode_address(address: str):
    clean_addr = address.strip().lower()
    cache_key = f"geo:{clean_addr}"

    # Check cache first
    try:
        redis = get_redis_client()
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as exc:
        logger.debug(f"Redis cache lookup failed for geocode '{clean_addr}': {exc}")

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 1,
    }
    headers = {
        "User-Agent": "RideNow/1.0"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            params=params,
            headers=headers,
            timeout=10.0,
        )

    response.raise_for_status()
    data = response.json()

    if not data:
        raise ValueError(f"Unable to find location: {address}")

    coords = {
        "latitude": float(data[0]["lat"]),
        "longitude": float(data[0]["lon"]),
    }

    # Store in cache
    try:
        await redis.set(cache_key, json.dumps(coords), ex=GEOCODE_CACHE_TTL)
    except Exception as exc:
        logger.debug(f"Redis cache write failed: {exc}")

    return coords


async def calculate_route_distance(
    pickup_latitude: float,
    pickup_longitude: float,
    dropoff_latitude: float,
    dropoff_longitude: float,
):
    cache_key = f"route:{pickup_latitude:.4f},{pickup_longitude:.4f}->{dropoff_latitude:.4f},{dropoff_longitude:.4f}"

    # Check cache first
    try:
        redis = get_redis_client()
        cached = await redis.get(cache_key)
        if cached:
            return float(cached)
    except Exception as exc:
        logger.debug(f"Redis cache lookup failed for route: {exc}")

    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{pickup_longitude},{pickup_latitude};"
        f"{dropoff_longitude},{dropoff_latitude}"
    )
    params = {"overview": "false"}

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            params=params,
            timeout=10.0,
        )

    response.raise_for_status()
    data = response.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError("Unable to calculate route")

    distance_meters = data["routes"][0]["distance"]
    dist_km = round(distance_meters / 1000, 2)

    # Store in cache
    try:
        await redis.set(cache_key, str(dist_km), ex=ROUTE_CACHE_TTL)
    except Exception as exc:
        logger.debug(f"Redis cache write failed: {exc}")

    return dist_km