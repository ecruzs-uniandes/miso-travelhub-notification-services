import asyncio
import logging
import time
from enum import Enum
from typing import Callable

from app.config import settings

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int | None = None,
        recovery_timeout: int | None = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold or settings.CB_FAILURE_THRESHOLD
        self.recovery_timeout = recovery_timeout or settings.CB_RECOVERY_TIMEOUT
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if self._last_failure_time and (
                time.monotonic() - self._last_failure_time >= self.recovery_timeout
            ):
                self._state = CircuitState.HALF_OPEN
                logger.info("circuit_breaker_half_open", extra={"cb_name": self.name})
        return self._state

    async def call(self, func: Callable, *args, **kwargs):
        state = self.state

        if state == CircuitState.OPEN:
            raise RuntimeError(f"Circuit breaker '{self.name}' está abierto")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise exc

    def _on_success(self):
        self._failure_count = 0
        if self._state != CircuitState.CLOSED:
            logger.info("circuit_breaker_closed", extra={"cb_name": self.name})
        self._state = CircuitState.CLOSED

    def _on_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.error(
                "circuit_breaker_opened",
                extra={"cb_name": self.name, "failures": self._failure_count},
            )


_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name)
    return _breakers[name]
