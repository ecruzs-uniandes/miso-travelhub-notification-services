import time
from unittest.mock import AsyncMock, patch

import pytest


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        from app.resilience.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_cb", failure_threshold=3, recovery_timeout=30)
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_successful_call(self):
        from app.resilience.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_success", failure_threshold=3, recovery_timeout=30)
        result = await cb.call(AsyncMock(return_value="ok"))
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self):
        from app.resilience.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_open", failure_threshold=3, recovery_timeout=30)

        async def failing():
            raise Exception("error")

        for _ in range(3):
            with pytest.raises(Exception):
                await cb.call(failing)

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_circuit_raises_immediately(self):
        from app.resilience.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_reject", failure_threshold=1, recovery_timeout=30)

        async def failing():
            raise Exception("error")

        with pytest.raises(Exception):
            await cb.call(failing)

        with pytest.raises(RuntimeError, match="abierto"):
            await cb.call(AsyncMock(return_value="ok"))

    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self):
        import time
        from app.resilience.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_half_open", failure_threshold=1, recovery_timeout=0.001)

        async def failing():
            raise Exception("error")

        with pytest.raises(Exception):
            await cb.call(failing)

        time.sleep(0.01)  # wait past recovery_timeout
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_closes_after_success_in_half_open(self):
        import time
        from app.resilience.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_close", failure_threshold=1, recovery_timeout=0.001)

        async def failing():
            raise Exception("error")

        with pytest.raises(Exception):
            await cb.call(failing)

        time.sleep(0.01)  # wait past recovery_timeout → becomes HALF_OPEN
        result = await cb.call(AsyncMock(return_value="recovered"))
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED
