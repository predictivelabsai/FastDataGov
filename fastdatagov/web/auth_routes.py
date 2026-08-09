from __future__ import annotations

from fasthtml.common import *
from starlette.requests import Request
from starlette.responses import RedirectResponse

from fastdatagov.auth.service import email_allowed, initial_roles, oauth, sign_out, store_identity
from fastdatagov.config import settings
from fastdatagov.models import UserIdentity
from fastdatagov.web.components import logo, site_head

routes = APIRouter()


def login_page(error: str = "", next_path: str = "/app"):
    configured = settings()
    next_path = next_path if next_path.startswith("/app") else "/app"
    is_dev = configured.auth_mode == "dev" and configured.dev_auth_enabled
    provider = "Microsoft" if configured.auth_mode == "entra" else "Google"
    provider_path = "/auth/entra" if configured.auth_mode == "entra" else "/auth/google"
    return Html(
        site_head("Sign in"),
        Body(
            Div(
                A("← Back to product", href="/", cls="auth-back"),
                Div(
                    logo(),
                    Span("Governed access", cls="eyebrow"),
                    H1("Sign in to your data workspace"),
                    P("Catalog visibility follows your identity and imported source-platform grants."),
                    Div(P(error), cls="auth-error", role="alert") if error else "",
                    Form(
                        Label("Work email", fr="email"),
                        Input(id="email", name="email", type="email", placeholder="you@example.com", required=True, autocomplete="email", autofocus=True),
                        Input(type="hidden", name="next_path", value=next_path),
                        Button("Continue in developer mode", type="submit", cls="button button-primary auth-submit"),
                        method="post", action="/auth/dev",
                    ) if is_dev else A(f"Continue with {provider}", href=f"{provider_path}?next={next_path}", cls="button button-primary auth-submit"),
                    Div(Span(), P("Local developer authentication is enabled. Production deployments use an OpenID Connect provider." if is_dev else f"Authentication is handled through {provider} OpenID Connect."), cls="auth-note"),
                    cls="auth-card",
                ),
                cls="auth-wrap",
            ),
            cls="auth-body",
        ),
    )


@routes("/auth/login", methods=["GET"])
def auth_login(next: str = "/app"):
    configured = settings()
    if configured.auth_mode == "entra" and configured.entra_enabled:
        return RedirectResponse(f"/auth/entra?next={next if next.startswith('/app') else '/app'}", status_code=303)
    if configured.auth_mode == "google" and configured.google_enabled:
        return RedirectResponse(f"/auth/google?next={next if next.startswith('/app') else '/app'}", status_code=303)
    message = ""
    if configured.auth_mode == "entra" and not configured.entra_enabled:
        message = "Microsoft Entra ID is selected but its tenant, client ID, or client secret is not configured."
    if configured.auth_mode == "google" and not configured.google_enabled:
        message = "Google authentication is selected but its client ID or client secret is not configured."
    return login_page(message, next)


@routes("/auth/dev", methods=["POST"])
def auth_dev(sess, email: str = "", next_path: str = "/app"):
    configured = settings()
    email = email.strip().lower()
    if configured.auth_mode != "dev" or not configured.dev_auth_enabled:
        raise HTTPException(404, "Developer authentication is disabled")
    if "@" not in email or not email_allowed(email):
        return login_page("Enter an allowed, valid email address.", next_path)
    display_name = email.split("@", 1)[0].replace(".", " ").replace("_", " ").title()
    store_identity(sess, UserIdentity(f"dev:{email}", email, display_name, ("governance_lead", "steward", "owner", "engineer", "consumer")))
    return RedirectResponse(next_path if next_path.startswith("/app") else "/app", status_code=303)


@routes("/auth/entra", methods=["GET"])
async def auth_entra(request: Request, next: str = "/app"):
    if not settings().entra_enabled or not getattr(oauth, "entra", None):
        return login_page("Microsoft Entra ID is not configured.", next)
    request.session["post_auth_redirect"] = next if next.startswith("/app") else "/app"
    redirect_uri = settings().entra_redirect_uri or str(request.base_url).rstrip("/") + "/auth/callback"
    return await oauth.entra.authorize_redirect(request, redirect_uri)


@routes("/auth/callback", methods=["GET"])
async def auth_callback(request: Request):
    if not settings().entra_enabled or not getattr(oauth, "entra", None):
        return login_page("Microsoft Entra ID is not configured.")
    try:
        token = await oauth.entra.authorize_access_token(request)
    except Exception:  # provider details must not leak into the response
        return login_page("Identity verification failed. Please try again.")
    claims = token.get("userinfo") or {}
    email = (claims.get("email") or claims.get("preferred_username") or "").strip().lower()
    subject = claims.get("oid") or claims.get("sub")
    if not email or not subject or not email_allowed(email):
        return login_page("This verified identity is not permitted to access FastDataGov.")
    roles = tuple(claims.get("roles") or ("consumer",))
    groups = tuple(claims.get("groups") or ())
    roles = tuple(sorted(set(roles) | set(initial_roles(email))))
    store_identity(request.session, UserIdentity(str(subject), email, claims.get("name") or email, roles, groups))
    target = request.session.pop("post_auth_redirect", "/app")
    return RedirectResponse(target if target.startswith("/app") else "/app", status_code=303)


@routes("/auth/google", methods=["GET"])
async def auth_google(request: Request, next: str = "/app"):
    if settings().auth_mode != "google" or not settings().google_enabled or not getattr(oauth, "google", None):
        return login_page("Google authentication is not configured.", next)
    request.session["post_auth_redirect"] = next if next.startswith("/app") else "/app"
    redirect_uri = settings().google_redirect_uri or str(request.base_url).rstrip("/") + "/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@routes("/auth/google/callback", methods=["GET"])
async def auth_google_callback(request: Request):
    if settings().auth_mode != "google" or not settings().google_enabled or not getattr(oauth, "google", None):
        return login_page("Google authentication is not configured.")
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return login_page("Identity verification failed. Please try again.")
    claims = token.get("userinfo") or {}
    email = str(claims.get("email") or "").strip().lower()
    subject = claims.get("sub")
    if not claims.get("email_verified") or not email or not subject or not email_allowed(email):
        return login_page("This verified identity is not permitted to access FastDataGov.")
    store_identity(
        request.session,
        UserIdentity(str(subject), email, claims.get("name") or email, initial_roles(email)),
    )
    target = request.session.pop("post_auth_redirect", "/app")
    return RedirectResponse(target if target.startswith("/app") else "/app", status_code=303)


@routes("/auth/logout", methods=["POST"])
def auth_logout(sess):
    return sign_out(sess)
