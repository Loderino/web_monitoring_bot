from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class UptimeStats:
    total_checks: int
    successful_checks: int
    failed_checks: int
    uptime_percentage: float
    downtime_duration: int
    average_response_time: float
    max_response_time: int
    min_response_time: int


@dataclass
class WeeklyReport:
    url: str
    period_start: datetime
    period_end: datetime
    stats: UptimeStats
    incidents: list[dict[str, Any]]
    daily_stats: list[dict[str, Any]]