from datetime import datetime
from dataclasses import dataclass
from utils.enums import SiteStatus, ResponseStatus

@dataclass
class Site:
    """Object of site record in db."""
    _id: str
    url: str
    status: SiteStatus
    consecutive_failures: int

    def __post_init__(self):
        self._id = str(self._id)
        self.status = SiteStatus(self.status)

@dataclass
class Monitor:
    """Object of monitor record in db."""
    _id: str
    user_id: int
    url: str
    interval: int
    def __post_init__(self):
        self._id = str(self._id)

@dataclass
class Check:
    """Object of check record in db."""
    _id: str
    url: str
    status: ResponseStatus
    timestamp: datetime
    code: int | None = None
    response_time: float | None = None
    def __post_init__(self):
        self._id = str(self._id)
        self.status = ResponseStatus(self.status)

@dataclass
class User:
    """Object of check record in db."""
    _id: str
    site_crash_notifications: bool
    site_recovery_notifications: bool
    weekly_report_notifications: bool