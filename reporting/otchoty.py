import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


@dataclass
class UptimeStats:
    total_checks: int
    successful_checks: int
    failed_checks: int
    uptime_percentage: float
    downtime_duration: int  # секунды
    average_response_time: float
    max_response_time: int
    min_response_time: int


@dataclass
class WeeklyReport:
    monitor_id: str
    url: str
    period_start: datetime
    period_end: datetime
    stats: UptimeStats
    incidents: List[Dict[str, Any]]
    daily_stats: List[Dict[str, Any]]


class ReportGenerator:
    def __init__(self, db_handler):
        self.db_handler = db_handler

    async def generate_weekly_report(
        self, monitor_id: str, end_date: Optional[datetime] = None
    ) -> WeeklyReport:
        """Генерировать еженедельный отчет для монитора"""
        if not end_date:
            end_date = datetime.now()

        start_date = end_date - timedelta(days=7)

        # Получаем информацию о мониторе
        monitor = await self.db_handler.get_monitor(monitor_id)
        if not monitor:
            raise ValueError(f"Monitor {monitor_id} not found")

        # Получаем все проверки за неделю
        checks = await self.db_handler.get_checks_by_period(
            monitor_id, start_date, end_date
        )

        # Вычисляем статистику
        stats = self._calculate_uptime_stats(checks)

        # Находим инциденты (периоды недоступности)
        incidents = self._find_incidents(checks)

        # Статистика по дням
        daily_stats = self._calculate_daily_stats(checks, start_date, end_date)

        return WeeklyReport(
            monitor_id=monitor_id,
            url=monitor["url"],
            period_start=start_date,
            period_end=end_date,
            stats=stats,
            incidents=incidents,
            daily_stats=daily_stats,
        )

    async def generate_multiple_reports(self, user_id: str) -> List[WeeklyReport]:
        """Генерировать отчеты для всех мониторов пользователя"""
        monitors = await self.db_handler.get_user_monitors(user_id)
        reports = []

        for monitor in monitors:
            try:
                report = await self.generate_weekly_report(monitor["_id"])
                reports.append(report)
            except Exception as e:
                print(f"Error generating report for monitor {monitor['_id']}: {e}")

        return reports

    def _calculate_uptime_stats(self, checks: List[Dict[str, Any]]) -> UptimeStats:
        """Вычислить статистику uptime/downtime"""
        if not checks:
            return UptimeStats(0, 0, 0, 0.0, 0, 0.0, 0, 0)

        total_checks = len(checks)
        successful_checks = sum(
            1 for check in checks if self._is_check_successful(check)
        )
        failed_checks = total_checks - successful_checks

        uptime_percentage = (
            (successful_checks / total_checks) * 100 if total_checks > 0 else 0
        )

        # Время недоступности
        downtime_duration = self._calculate_downtime_duration(checks)

        # Статистика времени ответа (только для успешных проверок)
        response_times = [
            check.get("response_time", 0)
            for check in checks
            if self._is_check_successful(check) and check.get("response_time")
        ]

        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            min_response_time = min(response_times)
        else:
            avg_response_time = max_response_time = min_response_time = 0

        return UptimeStats(
            total_checks=total_checks,
            successful_checks=successful_checks,
            failed_checks=failed_checks,
            uptime_percentage=round(uptime_percentage, 2),
            downtime_duration=downtime_duration,
            average_response_time=round(avg_response_time, 2),
            max_response_time=max_response_time,
            min_response_time=min_response_time,
        )

    def _find_incidents(self, checks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Найти инциденты (периоды недоступности)"""
        incidents = []
        current_incident = None

        for check in sorted(checks, key=lambda x: x["timestamp"]):
            is_successful = self._is_check_successful(check)

            if not is_successful and current_incident is None:
                # Начало инцидента
                current_incident = {
                    "start_time": check["timestamp"],
                    "end_time": None,
                    "duration": 0,
                    "reason": self._get_failure_reason(check),
                }

            elif is_successful and current_incident is not None:
                # Конец инцидента
                current_incident["end_time"] = check["timestamp"]
                current_incident["duration"] = int(
                    (
                        current_incident["end_time"] - current_incident["start_time"]
                    ).total_seconds()
                )
                incidents.append(current_incident)
                current_incident = None

        # Если инцидент не закончился
        if current_incident is not None:
            current_incident["end_time"] = datetime.now()
            current_incident["duration"] = int(
                (
                    current_incident["end_time"] - current_incident["start_time"]
                ).total_seconds()
            )
            incidents.append(current_incident)

        return incidents

    def _calculate_daily_stats(
        self, checks: List[Dict[str, Any]], start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Вычислить статистику по дням"""
        daily_stats = []
        current_date = start_date.date()
        end_date_only = end_date.date()

        while current_date <= end_date_only:
            # Фильтруем проверки за текущий день
            day_checks = [
                check for check in checks if check["timestamp"].date() == current_date
            ]

            if day_checks:
                successful = sum(
                    1 for check in day_checks if self._is_check_successful(check)
                )
                total = len(day_checks)
                uptime_percent = (successful / total) * 100 if total > 0 else 0

                # Среднее время ответа за день
                response_times = [
                    check.get("response_time", 0)
                    for check in day_checks
                    if self._is_check_successful(check) and check.get("response_time")
                ]
                avg_response_time = (
                    sum(response_times) / len(response_times) if response_times else 0
                )
            else:
                uptime_percent = 0
                avg_response_time = 0
                total = 0

            daily_stats.append(
                {
                    "date": current_date,
                    "uptime_percentage": round(uptime_percent, 1),
                    "total_checks": total,
                    "average_response_time": round(avg_response_time, 2),
                }
            )

            current_date += timedelta(days=1)

        return daily_stats

    def _calculate_downtime_duration(self, checks: List[Dict[str, Any]]) -> int:
        """Вычислить общее время недоступности в секундах"""
        incidents = self._find_incidents(checks)
        return sum(incident["duration"] for incident in incidents)

    def _is_check_successful(self, check: Dict[str, Any]) -> bool:
        """Определить, успешна ли проверка"""
        if check.get("timeout", False):
            return False
        if check.get("connection_error", False):
            return False

        status_code = check.get("status_code")
        if status_code and status_code >= 400:
            return False

        return True

    def _get_failure_reason(self, check: Dict[str, Any]) -> str:
        """Получить причину неудачи"""
        if check.get("timeout"):
            return "Timeout"
        if check.get("connection_error"):
            return "Connection Error"

        status_code = check.get("status_code")
        if status_code:
            return f"HTTP {status_code}"

        return "Unknown Error"

    def format_text_report(self, report: WeeklyReport) -> str:
        """Форматировать отчет в текстовый вид для Telegram"""
        text = f"📊 **Еженедельный отчет**\n\n"
        text += f"🌐 **Сайт:** {report.url}\n"
        text += f"📅 **Период:** {report.period_start.strftime('%d.%m.%Y')} - {report.period_end.strftime('%d.%m.%Y')}\n\n"

        # Основная статистика
        stats = report.stats
        text += f"📈 **Статистика:**\n"
        text += f"• Uptime: {stats.uptime_percentage}%\n"
        text += f"• Всего проверок: {stats.total_checks}\n"
        text += f"• Успешных: {stats.successful_checks}\n"
        text += f"• Неудачных: {stats.failed_checks}\n"

        if stats.downtime_duration > 0:
            downtime_str = self._format_duration(stats.downtime_duration)
            text += f"• Время недоступности: {downtime_str}\n"

        if stats.average_response_time > 0:
            text += f"• Среднее время ответа: {stats.average_response_time}ms\n"

        # Инциденты
        if report.incidents:
            text += f"\n🚨 **Инциденты ({len(report.incidents)}):**\n"
            for i, incident in enumerate(
                report.incidents[:5], 1
            ):  # Показываем только первые 5
                duration_str = self._format_duration(incident["duration"])
                text += f"{i}. {incident['start_time'].strftime('%d.%m %H:%M')} - {duration_str} ({incident['reason']})\n"

        # Текстовый график по дням
        text += f"\n📊 **График по дням:**\n"
        text += self._create_text_chart(report.daily_stats)

        return text

    def _format_duration(self, seconds: int) -> str:
        """Форматировать длительность в читаемый вид"""
        if seconds < 60:
            return f"{seconds}с"
        elif seconds < 3600:
            return f"{seconds // 60}м {seconds % 60}с"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}ч {minutes}м"

    def _create_text_chart(self, daily_stats: List[Dict[str, Any]]) -> str:
        """Создать текстовый график доступности"""
        chart = ""
        for day_stat in daily_stats:
            date_str = day_stat["date"].strftime("%d.%m")
            uptime = day_stat["uptime_percentage"]

            # Создаем визуальную полоску
            if uptime >= 99:
                bar = "🟢" * 10
            elif uptime >= 95:
                bar = "🟢" * 8 + "🟡" * 2
            elif uptime >= 90:
                bar = "🟢" * 7 + "🟡" * 2 + "🔴" * 1
            elif uptime >= 50:
                bar = "🟢" * 5 + "🟡" * 3 + "🔴" * 2
            else:
                bar = "🟢" * 2 + "🟡" * 2 + "🔴" * 6

            chart += f"{date_str}: {bar} {uptime}%\n"

        return chart
