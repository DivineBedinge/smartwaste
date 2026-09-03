from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def schema_text():
    return (ROOT / "test.sql").read_text(encoding="utf-8").lower()


def test_historical_schema_has_required_extensions_and_geospatial_contract():
    sql = schema_text()
    assert "create extension if not exists postgis" in sql
    assert "pg_available_extensions where name = 'vector'" in sql
    assert "geometry(point, 4326)" in sql
    assert "using gist" in sql


def test_historical_schema_has_jsonb_constraints_and_foreign_keys():
    sql = schema_text()
    assert "translation_params jsonb" in sql
    assert "check (status in" in sql
    assert "references users(id)" in sql


def test_report_idempotency_is_scoped_to_owner():
    sql = schema_text()
    assert "uq_reports_user_client_id" in sql
    assert "on reports(user_id, client_id)" in sql
