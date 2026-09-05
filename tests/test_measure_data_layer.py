import pytest

from scripts.measure_data_layer import measure


def test_measurement_refuses_non_test_database(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/smartwaste_db")
    with pytest.raises(RuntimeError):
        measure()
