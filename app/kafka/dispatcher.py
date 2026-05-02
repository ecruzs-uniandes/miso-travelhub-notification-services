import logging
from typing import Callable

from app.schemas.events import EventEnvelope

logger = logging.getLogger(__name__)

_handlers: dict[str, Callable] = {}


def register(event_type: str):
    def decorator(func: Callable):
        _handlers[event_type] = func
        return func
    return decorator


def get_handler(event_type: str) -> Callable | None:
    handler = _handlers.get(event_type)
    if not handler:
        logger.warning("unknown_event_type", extra={"event_type": event_type})
    return handler


def _load_handlers():
    from app.kafka.handlers import booking, payment, user  # noqa: F401


_load_handlers()
