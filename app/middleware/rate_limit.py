import time
from collections import defaultdict

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

RATE_LIMIT = 60
WINDOW = 60

_counters: dict[str, list[float]] = defaultdict(list)

EXEMPT_PATHS = {"/health", "/ready"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        user_id = getattr(request.state, "user_id", None)
        key = user_id or request.client.host if request.client else "unknown"

        now = time.time()
        window_start = now - WINDOW
        hits = [t for t in _counters[key] if t > window_start]
        hits.append(now)
        _counters[key] = hits

        if len(hits) > RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"detail": "Demasiadas solicitudes. Intenta de nuevo en un minuto."},
            )

        return await call_next(request)
