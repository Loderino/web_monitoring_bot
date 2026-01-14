from dataclasses import dataclass
from datetime import datetime

from utils.enums import ResponseStatus, SiteStatus

@dataclass
class ResponseData:
    """Response data model."""

    url: str
    status: ResponseStatus
    timestamp: int
    code: int | None = None
    response_time: float | None = None

    def prepare_for_database(self) -> dict:
        """
        Converts an object to a format acceptable for writing to a database.

        Returns:
            dict: response data information.
        """
        document = {
            "url": self.url,
            "status": self.status.value,
            "timestamp": datetime.fromtimestamp(self.timestamp),
        }
        if self.code:
            document["code"] = self.code
        if self.response_time:
            document["response_time"] = self.response_time
        return document

@dataclass
class Notification:
    url: str
    status: SiteStatus
