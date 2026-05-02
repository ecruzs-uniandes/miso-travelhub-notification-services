import logging

from fastapi import Request, Response
from jose import jwt
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)

EXEMPT_PATHS = {"/health", "/ready", "/docs", "/openapi.json"}


class JWTDecodeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in EXEMPT_PATHS or request.url.path.endswith("/internal"):
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            try:
                claims = jwt.decode(
                    token,
                    key="",
                    algorithms=["RS256"],
                    options={"verify_signature": False, "verify_exp": False},
                )
                request.state.user_id = claims.get("sub")
                request.state.role = claims.get("role", "")
                request.state.claims = claims
            except Exception as exc:
                logger.warning("jwt_decode_failed", extra={"error": str(exc)})
                request.state.user_id = None
                request.state.role = ""
                request.state.claims = {}
        else:
            request.state.user_id = None
            request.state.role = ""
            request.state.claims = {}

        return await call_next(request)
