"""Database pool singleton and fleet-safe defaults."""

from types import SimpleNamespace

import fastdatagov.db as database
from fastdatagov.config import Settings


def test_pool_factory_is_process_singleton(monkeypatch):
    created = []

    class FakePool:
        check_connection = staticmethod(lambda connection: None)

        def __init__(self, **kwargs):
            created.append(kwargs)

        def open(self):
            pass

        def close(self):
            pass

    configured = SimpleNamespace(
        database_url="postgresql://unused/fastdatagov",
        database_pool_min=0,
        database_pool_max=3,
        database_pool_timeout=10,
        database_pool_recycle=1800,
        database_pool_max_idle=300,
        database_application_name="fastdatagov",
    )
    database.close_database_pool()
    monkeypatch.setattr(database, "ConnectionPool", FakePool)
    monkeypatch.setattr(database, "settings", lambda: configured)

    assert database.pool() is database.pool()
    assert len(created) == 1
    database.close_database_pool()


def test_shared_database_defaults_are_bounded():
    fields = Settings.model_fields
    assert fields["database_pool_min"].default == 0
    assert fields["database_pool_max"].default == 3
    assert fields["database_pool_timeout"].default == 10
    assert fields["database_application_name"].default == "fastdatagov"
