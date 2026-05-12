import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(tags=["device"])


@router.get("/notifications/register-device")
async def register_device():
    return "Endpoint works ok"