from fastapi import FastAPI

from app.middleware.jwt_decode import JWTDecodeMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.rbac import RBACMiddleware


def setup_middleware(app: FastAPI) -> None:
    # Order matters: last added = first executed
    app.add_middleware(RBACMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(JWTDecodeMiddleware)
