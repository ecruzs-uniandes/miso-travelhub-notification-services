from abc import ABC, abstractmethod


class NotificationSender(ABC):
    @abstractmethod
    async def send(self, recipient: str, subject: str, body: str, metadata: dict) -> dict:
        """Send notification. Returns provider_response dict. Raises on failure."""
        ...
