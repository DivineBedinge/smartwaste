from unittest.mock import Mock, patch

from app.services.routing import get_route


@patch("app.services.routing.requests.get")
def test_osrm_route_validates_response(mock_get):
    response = Mock()
    response.json.return_value = {"routes": [{"geometry": {"type": "LineString"}, "distance": 100, "duration": 20}]}
    response.raise_for_status.return_value = None
    mock_get.return_value = response
    route = get_route([(4.0, 9.0), (4.1, 9.1)])
    assert route["distance_m"] == 100
    mock_get.assert_called_once()


@patch("app.services.routing.requests.get", side_effect=TimeoutError)
def test_osrm_failure_returns_unavailable(mock_get):
    assert get_route([(4.0, 9.0), (4.1, 9.1)]) is None