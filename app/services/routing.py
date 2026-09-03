import os
from typing import Any, Optional

import requests


OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
OSRM_TIMEOUT_SECONDS = float(os.getenv("OSRM_TIMEOUT_SECONDS", "10"))


def get_route(coords: list[tuple[float, float]]) -> Optional[dict[str, Any]]:
    if len(coords) < 2:
        return None
    encoded = ";".join(f"{lon},{lat}" for lat, lon in coords)
    url = f"{OSRM_BASE_URL.rstrip('/')}/route/v1/driving/{encoded}"
    try:
        response = requests.get(
            url,
            params={"overview": "full", "geometries": "geojson"},
            timeout=OSRM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        routes = payload.get("routes")
        if not routes or "geometry" not in routes[0]:
            return None
        return {
            "geometry": routes[0]["geometry"],
            "distance_m": routes[0].get("distance"),
            "duration_s": routes[0].get("duration"),
        }
    except (requests.RequestException, ValueError, TypeError, TimeoutError):
        return None