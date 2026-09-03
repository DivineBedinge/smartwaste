import pytest

from database import require_test_database_url


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user:password@localhost/smartwaste_db",
        "postgresql://user:password@localhost/production",
        "postgresql://user:password@localhost/smartwaste",
    ],
)
def test_destructive_database_guard_rejects_non_test_names(url):
    with pytest.raises(RuntimeError):
        require_test_database_url(url)


def test_destructive_database_guard_accepts_explicit_test_name():
    assert require_test_database_url(
        "postgresql://user:password@localhost/smartwaste_test"
    ).endswith("/smartwaste_test")
