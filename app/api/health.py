import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "notification-services", "env": settings.ENV}


@router.get("/ready")
async def ready():
    checks = {}

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        logger.error("readiness_db_check_failed", extra={"error": str(exc)})
        checks["database"] = "error"

    if settings.KAFKA_CONSUMER_ENABLED:
        checks["kafka"] = "enabled"
    else:
        checks["kafka"] = "disabled"

    status = "ok" if all(v in ("ok", "disabled", "enabled") for v in checks.values()) else "error"
    http_status = 200 if status == "ok" else 503

    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=http_status,
        content={"status": status, "checks": checks},
    )
