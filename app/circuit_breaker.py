import asyncio
import logging
import time
from typing import Any, Callable


logger = logging.getLogger(__name__)


class ServiceUnavailableError(Exception):
    pass


class CircuitBreaker:

    CLOSED = "closed"
    OPEN = "open"
    RECOVERING = "recovering"

    def __init__(
        self,
        max_failures: int = 3,
        reset_after: float = 10,
        service_name: str = "service"
    ):
        self.max_failures = max_failures
        self.reset_after = reset_after
        self.service_name = service_name

        self.current_failures = 0
        self.current_state = self.CLOSED
        self.last_error_time = None

        self._recovery_lock = asyncio.Lock()

    @property
    def state(self) -> str:

        if self.current_state == self.OPEN:
            if self.last_error_time:
                elapsed = time.monotonic() - self.last_error_time

                if elapsed >= self.reset_after:
                    self.current_state = self.RECOVERING
                    logger.info(
                        "[%s] moving to recovery mode",
                        self.service_name
                    )

        return self.current_state.upper()

    async def execute(self, operation: Callable, *args, **kwargs) -> Any:

        if self.state == "OPEN":
            raise ServiceUnavailableError(
                f"{self.service_name} temporarily blocked"
            )

        if self.current_state == self.RECOVERING:
            async with self._recovery_lock:
                return await self._attempt_execution(operation, *args, **kwargs)

        return await self._attempt_execution(operation, *args, **kwargs)

    async def _attempt_execution(self, operation: Callable, *args, **kwargs):

        try:
            result = await operation(*args, **kwargs)

            if self.current_state != self.CLOSED:
                logger.info(
                    "[%s] service healthy again",
                    self.service_name
                )

            self.current_failures = 0
            self.current_state = self.CLOSED
            self.last_error_time = None

            return result

        except Exception as error:

            self.current_failures += 1
            self.last_error_time = time.monotonic()

            logger.warning(
                "[%s] request failed (%d/%d)",
                self.service_name,
                self.current_failures,
                self.max_failures
            )

            if self.current_failures >= self.max_failures:
                self.current_state = self.OPEN

                logger.error(
                    "[%s] breaker opened",
                    self.service_name
                )

            raise error

    def reset(self):

        self.current_failures = 0
        self.current_state = self.CLOSED
        self.last_error_time = None