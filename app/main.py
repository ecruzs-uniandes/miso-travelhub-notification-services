import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.internal import router as internal_router
from app.api.public import router as public_router
from app.config import settings
from app.middleware.chain import setup_middleware
from app.utils.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TravelHub Notification Services",
    version="1.0.0",
    docs_url="/docs" if settings.ENV != "prod" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_middleware(app)

app.include_router(health_router)
app.include_router(public_router, prefix="/api/v1")
app.include_router(internal_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    logger.info("notification_services_starting", extra={"env": settings.ENV})

    if settings.KAFKA_CONSUMER_ENABLED:
        from app.kafka.consumer import consumer_loop
        asyncio.create_task(consumer_loop())
        logger.info("kafka_consumer_started")
    else:
        logger.warning("kafka_consumer_disabled", extra={"env": settings.ENV})


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("notification_services_stopping")
