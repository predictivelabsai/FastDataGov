from __future__ import annotations

import pytest
from pydantic import ValidationError

from fastdatagov.config import Settings


def test_production_accepts_configured_google_oidc():
    configured = Settings(
        APP_ENV="production",
        APP_SECRET="a-production-secret-with-more-than-32-characters",
        AUTH_MODE="google",
        GOOGLE_CLIENT_ID="client-id",
        GOOGLE_CLIENT_SECRET="client-secret",
        BASE_URL="https://datagov.fastsme.com",
        ALLOWED_HOSTS="datagov.fastsme.com",
    )
    assert configured.google_enabled
    assert configured.auth_mode == "google"


def test_production_rejects_unconfigured_identity_provider():
    with pytest.raises(ValidationError, match="configured Entra ID or Google"):
        Settings(
            APP_ENV="production",
            APP_SECRET="a-production-secret-with-more-than-32-characters",
            AUTH_MODE="google",
            BASE_URL="https://datagov.fastsme.com",
            ALLOWED_HOSTS="datagov.fastsme.com",
        )


def test_google_access_lists_extend_generic_access_lists():
    configured = Settings(
        GOOGLE_ALLOWED_DOMAINS="fastsme.com",
        GOOGLE_ALLOWED_EMAILS="owner@example.com",
        GOVERNANCE_ADMIN_EMAILS="lead@example.com",
    )
    assert configured.allowed_domains == {"fastsme.com"}
    assert configured.allowed_users == {"owner@example.com"}
    assert configured.governance_admins == {"lead@example.com"}
