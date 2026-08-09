from __future__ import annotations

import logging

from authlib.integrations.starlette_client import OAuth
from fasthtml.common import HTTPException
from starlette.responses import JSONResponse, RedirectResponse

from fastdatagov.config import settings
from fastdatagov.db import connect, fetch_all
from fastdatagov.models import UserIdentity

oauth = OAuth()
log = logging.getLogger(__name__)
KNOWN_ROLES={"consumer","steward","owner","engineer","governance_lead","admin"}
if settings().entra_enabled:
    oauth.register(
        name="entra",
        client_id=settings().entra_client_id,
        client_secret=settings().entra_client_secret,
        server_metadata_url=(
            f"https://login.microsoftonline.com/{settings().entra_tenant_id}/v2.0/"
            ".well-known/openid-configuration"
        ),
        client_kwargs={"scope": "openid email profile"},
    )
if settings().google_enabled:
    oauth.register(
        name="google",
        client_id=settings().google_client_id,
        client_secret=settings().google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def current_identity(session: dict) -> UserIdentity | None:
    raw = session.get("identity")
    if not raw:
        return None
    identity=UserIdentity(
        subject=raw["subject"],
        email=raw["email"],
        name=raw["name"],
        roles=tuple(raw.get("roles") or ("consumer",)),
        groups=tuple(raw.get("groups") or ()),
    )
    return with_role_bindings(identity)


def with_role_bindings(identity: UserIdentity) -> UserIdentity:
    roles={role for role in identity.roles if role in KNOWN_ROLES} or {"consumer"}
    if settings().repository_mode=="postgres":
        try:
            rows=fetch_all("SELECT role FROM fastdatagov.role_bindings WHERE scope_type='global' AND ((principal_type='user' AND principal_key=%s) OR (principal_type='group' AND principal_key=ANY(%s)))",(identity.email,list(identity.groups)))
            roles.update(row["role"] for row in rows)
        except Exception:
            log.exception("Could not resolve persistent role bindings")
    return UserIdentity(identity.subject,identity.email,identity.name,tuple(sorted(roles)),identity.groups)


def persist_user(identity: UserIdentity) -> None:
    if settings().repository_mode!="postgres": return
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("INSERT INTO fastdatagov.users (subject,email,display_name,last_seen_at) VALUES (%s,%s,%s,now()) ON CONFLICT (subject) DO UPDATE SET email=excluded.email,display_name=excluded.display_name,last_seen_at=now()",(identity.subject,identity.email,identity.name)); connection.commit()


def store_identity(session: dict, identity: UserIdentity) -> None:
    persist_user(identity)
    session["identity"] = {
        "subject": identity.subject,
        "email": identity.email,
        "name": identity.name,
        "roles": [role for role in identity.roles if role in KNOWN_ROLES] or ["consumer"],
        "groups": list(identity.groups),
    }


def email_allowed(email: str) -> bool:
    email = email.strip().lower()
    configured = settings()
    if not configured.allowed_domains and not configured.allowed_users:
        return True
    domain = email.rsplit("@", 1)[-1] if "@" in email else ""
    return email in configured.allowed_users or domain in configured.allowed_domains


def initial_roles(email: str) -> tuple[str, ...]:
    if email.strip().lower() in settings().governance_admins:
        return ("admin", "consumer", "engineer", "governance_lead", "owner", "steward")
    return ("consumer",)


def auth_before(req, sess):
    identity = current_identity(sess)
    req.scope["auth"] = identity
    path = req.url.path
    if path.startswith("/app") and not identity:
        return RedirectResponse(f"/auth/login?next={path}", status_code=303)
    if path.startswith("/api/v1") and not identity:
        return JSONResponse({"error": "authentication_required"}, status_code=401)


def require_role(identity: UserIdentity | None, *roles: str) -> None:
    if not identity:
        raise HTTPException(401, "Authentication required")
    if not identity.can(*roles):
        raise HTTPException(403, "This action requires " + " or ".join(roles))


def sign_out(session: dict) -> RedirectResponse:
    session.clear()
    return RedirectResponse("/", status_code=303)
