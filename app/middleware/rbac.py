from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

ALLOWED_ROLES = {"traveler", "hotel_admin", "platform_admin"}

EXEMPT_PATHS = {"/health", "/ready", "/docs", "/openapi.json"}


class RBACMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if (
            path in EXEMPT_PATHS
            or path.endswith("/internal")
            or path.endswith("/admin/test-event")
            or path.endswith("/send-notification")
        ):
            return await call_next(request)

        if not path.startswith("/api/v1/notifications"):
            return await call_next(request)

        user_id = getattr(request.state, "user_id", None)
        role = getattr(request.state, "role", "")

        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"detail": "No autenticado"},
            )

        if role not in ALLOWED_ROLES:
            return JSONResponse(
                status_code=403,
                content={"detail": "No tienes permiso para acceder a este recurso"},
            )

        return await call_next(request)
