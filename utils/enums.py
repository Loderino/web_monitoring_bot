from enum import Enum


class ResponseStatus(Enum):
    """Possible response statuses"""

    OK = 0
    TIMEOUT = 1
    DNS_ERROR = 2
    UNAVAILABLE = 3


class SiteStatus(Enum):
    """Possible site statuses"""

    UNAVAILABLE = 0
    AVAILABLE = 1