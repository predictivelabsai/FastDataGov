from __future__ import annotations

import logging

from fasthtml.common import Beforeware, Meta, fast_app
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from starlette.responses import PlainTextResponse

from fastdatagov.auth.service import auth_before, current_identity
from fastdatagov.config import settings
from fastdatagov.repository import repository
from fastdatagov.web.api import routes as api_routes
from fastdatagov.web.auth_routes import routes as auth_routes
from fastdatagov.web.landing import landing_page
from fastdatagov.web.routes import routes as app_routes
from fastdatagov.web.security import SecurityHeadersMiddleware

beforeware = Beforeware(
    auth_before,
    skip=[
        r"/static/.*",
        r"/styles\.css",
        r"/app\.js",
        r"/favicon\.ico",
        r"/healthz",
        r"/readyz",
        r"^/$",
        r"/auth/.*",
    ],
)

app, rt = fast_app(
    live=False,
    static_path="static",
    pico=False,
    htmx=True,
    secret_key=settings().app_secret,
    session_cookie="fastdatagov_session",
    same_site="lax",
    sess_https_only=settings().app_env.lower() in {"production", "prod"},
    middleware=(Middleware(TrustedHostMiddleware,allowed_hosts=settings().host_allowlist),Middleware(SecurityHeadersMiddleware)),
    before=beforeware,
    hdrs=(Meta(name="referrer", content="same-origin"),),
)

auth_routes.to_app(app)
app_routes.to_app(app)
api_routes.to_app(app)


async def validation_error(request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error":"invalid_request","message":str(exc)},status_code=400)
    return PlainTextResponse(str(exc),status_code=400)


async def permission_error(request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error":"forbidden","message":str(exc)},status_code=403)
    return PlainTextResponse(str(exc),status_code=403)


app.add_exception_handler(ValueError,validation_error)
app.add_exception_handler(PermissionError,permission_error)


@rt("/", methods=["GET"])
def home(sess):
    return landing_page(current_identity(sess))


@rt("/healthz", methods=["GET"])
def health():
    return JSONResponse({"status": "ok", "service": "fastdatagov"})


@rt("/readyz", methods=["GET"])
def ready():
    try:
        repository().metrics()
        return JSONResponse({"status": "ready", "repository": settings().repository_mode})
    except Exception:
        logging.exception("Readiness check failed")
        return JSONResponse({"status": "not_ready"}, status_code=503)


def run() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    uvicorn.run(app, host=settings().host, port=settings().port)


if __name__ == "__main__":
    run()
