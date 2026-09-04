import pytest

from app.services.geo import haversine_meters, validate_bbox, validate_coordinate


def test_coordinates_and_douala_bounds_are_validated():
    validate_coordinate(4.05,9.70,douala_only=True)
    with pytest.raises(ValueError): validate_coordinate(95,9.7)
    with pytest.raises(ValueError): validate_coordinate(5.0,9.7,douala_only=True)


def test_bbox_is_ordered_and_bounded():
    assert validate_bbox(4.0,9.6,4.2,9.9).east == 9.9
    with pytest.raises(ValueError): validate_bbox(4.2,9.6,4.0,9.9)


def test_haversine_distance_is_an_estimate_not_a_route():
    distance=haversine_meters((4.05,9.70),(4.06,9.70))
    assert 1100 < distance < 1120
