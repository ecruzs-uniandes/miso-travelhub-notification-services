import logging

from fastapi import Request, Response
from jose import jwt
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)

EXEMPT_PATHS = {"/health", "/ready", "/docs", "/openapi.json"}


class JWTDecodeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in EXEMPT_PATHS or path.endswith("/internal") or path.endswith("/admin/test-event"):
            return await call_next(request)

        # Default: no auth claims set
        request.state.user_id = None
        request.state.role = ""
        request.state.claims = {}

        # When traffic comes through API Gateway, GCP replaces "Authorization" with
        # a service OIDC token and moves the original user JWT to
        # "X-Forwarded-Authorization". Read X-Forwarded-Authorization first; fall
        # back to Authorization for direct calls (bypass gateway).
        token = None
        for header in ("X-Forwarded-Authorization", "Authorization"):
            value = request.headers.get(header, "")
            if value.startswith("Bearer "):
                token = value[7:]
                break

        if token:
            try:
                claims = jwt.decode(
                    token,
                    key="",
                    algorithms=["RS256"],
                    options={"verify_signature": False, "verify_exp": False, "verify_aud": False},
                )
                request.state.user_id = claims.get("sub")
                request.state.role = claims.get("role", "")
                request.state.claims = claims
            except Exception as exc:
                logger.warning("jwt_decode_failed", extra={"error": str(exc)})

        return await call_next(request)
