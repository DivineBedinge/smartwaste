import pytest

from app.services.gps_retention import purge_old_positions


class Cursor:
    rowcount = 3

    def execute(self, query, params):
        self.query = query
        self.params = params

    def close(self):
        pass


class Connection:
    def __init__(self):
        self.cursor_instance = Cursor()
        self.commits = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1


def test_purge_is_idempotent_sql_cleanup():
    conn = Connection()
    assert purge_old_positions(conn, 30) == 3
    assert conn.cursor_instance.params == (30,)
    assert conn.commits == 1


def test_retention_must_be_positive():
    with pytest.raises(ValueError):
        purge_old_positions(Connection(), 0)