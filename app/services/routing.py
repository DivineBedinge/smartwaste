from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import requests


class RoutingUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class RouteResult:
    geometry: dict[str, Any]
    distance_m: float
    duration_s: float
    provider: str


class RoutingProvider(ABC):
    name = "disabled"

    @abstractmethod
    def route(self, coordinates: list[tuple[float, float]]) -> RouteResult: ...


def _validate_coordinates(coordinates: list[tuple[float, float]]) -> None:
    maximum = int(os.getenv("ROUTING_MAX_STOPS", "50"))
    if len(coordinates) < 2 or len(coordinates) > maximum + 1:
        raise ValueError("Nombre de points de routage invalide")
    for latitude, longitude in coordinates:
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("Coordonnées de routage invalides")


class DisabledRoutingProvider(RoutingProvider):
    def route(self, coordinates: list[tuple[float, float]]) -> RouteResult:
        _validate_coordinates(coordinates)
        raise RoutingUnavailable("Itinéraire indisponible")


class OSRMRoutingProvider(RoutingProvider):
    name = "osrm"

    def __init__(self, base_url: str, timeout_seconds: float = 8.0):
        if not base_url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            raise ValueError("URL OSRM non autorisée")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = max(0.1, min(timeout_seconds, 30.0))

    def route(self, coordinates: list[tuple[float, float]]) -> RouteResult:
        _validate_coordinates(coordinates)
        encoded = ";".join(f"{longitude},{latitude}" for latitude, longitude in coordinates)
        try:
            response = requests.get(f"{self.base_url}/route/v1/driving/{encoded}", params={"overview":"full","geometries":"geojson"}, timeout=self.timeout_seconds)
            response.raise_for_status()
            routes = response.json().get("routes")
            candidate = routes[0] if isinstance(routes, list) and routes else None
            geometry = candidate.get("geometry") if isinstance(candidate, dict) else None
            distance = candidate.get("distance") if isinstance(candidate, dict) else None
            duration = candidate.get("duration") if isinstance(candidate, dict) else None
            coordinates_out = geometry.get("coordinates") if isinstance(geometry, dict) else None
            if not isinstance(geometry, dict) or geometry.get("type") != "LineString" or not isinstance(coordinates_out, list) or not 2 <= len(coordinates_out) <= 100000:
                raise RoutingUnavailable("Géométrie de routage invalide")
            if not isinstance(distance,(int,float)) or not isinstance(duration,(int,float)) or distance < 0 or duration < 0:
                raise RoutingUnavailable("Métriques de routage invalides")
            return RouteResult(geometry,float(distance),float(duration),self.name)
        except (requests.RequestException,ValueError,TypeError,KeyError,TimeoutError) as exc:
            raise RoutingUnavailable("Itinéraire indisponible") from exc


def get_routing_provider() -> RoutingProvider:
    if os.getenv("ROUTING_PROVIDER","disabled").strip().lower() == "osrm":
        return OSRMRoutingProvider(os.getenv("OSRM_BASE_URL","https://router.project-osrm.org"),float(os.getenv("OSRM_TIMEOUT_SECONDS","8")))
    return DisabledRoutingProvider()


def get_route(coords: list[tuple[float,float]]) -> dict[str,Any] | None:
    try: result=get_routing_provider().route(coords)
    except (RoutingUnavailable,ValueError): return None
    return {"geometry":result.geometry,"distance_m":result.distance_m,"duration_s":result.duration_s,"provider":result.provider}
