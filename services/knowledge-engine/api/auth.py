import os
import secrets
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from open_notebook.utils.encryption import get_secret_from_env

_TRUE_VALUES = {"1", "true", "yes", "on"}


def unauthenticated_access_is_explicitly_allowed() -> bool:
    """Return whether passwordless access was deliberately enabled.

    Passwordless operation is intended only for controlled tests or isolated
    local development. It must never be inferred merely from a missing secret.
    """

    raw_value = os.getenv("OPEN_NOTEBOOK_ALLOW_NO_AUTH", "")
    return raw_value.strip().lower() in _TRUE_VALUES


class PasswordAuthMiddleware(BaseHTTPMiddleware):
    """Require bearer-password authentication for API requests.

    Authentication fails closed when ``OPEN_NOTEBOOK_PASSWORD`` is absent.
    Passwordless access is permitted only when
    ``OPEN_NOTEBOOK_ALLOW_NO_AUTH=true`` is set explicitly. Docker secrets are
    supported through ``OPEN_NOTEBOOK_PASSWORD_FILE``.
    """

    def __init__(
        self, app: ASGIApp, excluded_paths: Optional[list[str]] = None
    ) -> None:
        super().__init__(app)
        self.password = get_secret_from_env("OPEN_NOTEBOOK_PASSWORD")
        self.allow_no_auth = unauthenticated_access_is_explicitly_allowed()
        self.excluded_paths: list[str] = excluded_paths or [
            "/",
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not self.password:
            if self.allow_no_auth:
                return await call_next(request)
            return JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        "Authentication is not configured. Set "
                        "OPEN_NOTEBOOK_PASSWORD, or explicitly set "
                        "OPEN_NOTEBOOK_ALLOW_NO_AUTH=true only for an isolated "
                        "test or local-development environment."
                    )
                },
            )

        if request.url.path in self.excluded_paths:
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing authorization header"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            scheme, credentials = auth_header.split(" ", 1)
            if scheme.lower() != "bearer":
                raise ValueError("Invalid authentication scheme")
        except ValueError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authorization header format"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not secrets.compare_digest(
            credentials.encode("utf-8"), self.password.encode("utf-8")
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid password"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
