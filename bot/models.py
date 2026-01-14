from dataclasses import dataclass


@dataclass
class NewMonitorTask:
    url: str = None
    interval: int = None
    is_url_expected: bool = False

@dataclass
class ModifyMonitorTask:
    index: int = None
    interval: int = None

