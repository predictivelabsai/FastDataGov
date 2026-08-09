from __future__ import annotations

import os

os.environ.setdefault("APP_SECRET", "test-secret-that-is-long-enough-for-sessions")
os.environ.setdefault("REPOSITORY_MODE", "demo")
os.environ.setdefault("AUTH_MODE", "dev")
os.environ.setdefault("DEV_AUTH_ENABLED", "true")

import pytest
from starlette.testclient import TestClient

from fastdatagov.main import app
from fastdatagov.repository import DemoRepository, repository


@pytest.fixture(autouse=True)
def reset_demo_repository():
    repo = repository()
    if isinstance(repo, DemoRepository):
        repo.reset()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client(client):
    response = client.post(
        "/auth/dev",
        data={"email": "governance.lead@example.com", "next_path": "/app"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client
