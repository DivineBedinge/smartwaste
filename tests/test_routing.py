from unittest.mock import Mock, patch

from app.services.routing import get_route


@patch.dict("os.environ", {"ROUTING_PROVIDER": "osrm"})
@patch("app.services.routing.requests.get")
def test_osrm_route_validates_response(mock_get):
    response = Mock()
    response.json.return_value = {"routes": [{"geometry": {"type": "LineString", "coordinates": [[9.0,4.0],[9.1,4.1]]}, "distance": 100, "duration": 20}]}
    response.raise_for_status.return_value = None
    mock_get.return_value = response
    route = get_route([(4.0, 9.0), (4.1, 9.1)])
    assert route["distance_m"] == 100
    mock_get.assert_called_once()


@patch.dict("os.environ", {"ROUTING_PROVIDER": "osrm"})
@patch("app.services.routing.requests.get", side_effect=TimeoutError)
def test_osrm_failure_returns_unavailable(mock_get):
    assert get_route([(4.0, 9.0), (4.1, 9.1)]) is None


def test_disabled_provider_never_fabricates_a_route(monkeypatch):
    monkeypatch.setenv("ROUTING_PROVIDER", "disabled")
    assert get_route([(4.0,9.0),(4.1,9.1)]) is None
