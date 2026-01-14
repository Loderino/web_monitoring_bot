from datetime import datetime, timedelta

from constants import FAILURE_THRESHOLD
from db.db_handler import DBHandler
from db.models import Check
from reporting.models import UptimeStats, WeeklyReport
from task_manager.models import ResponseStatus
from utils.functions import format_duration

class ReportGenerator:
    db = DBHandler()

    def _is_check_successful(self, check: Check) -> bool:
        """
        Determines whether the check is successful.

        Args:
            check (Check): URL check object.

        Returns:
            bool: True if check is successful. False otherwise.
        """
        return check.status == ResponseStatus.OK

    def _get_failure_reason(self, check: Check) -> str:
        """Determines the reason for the failed check

        Args:
            check (Check): URL check object.

        Returns:
            str: Name of the reason for the failed verification.
        """
        match check.status:
            case ResponseStatus.UNAVAILABLE:
                return f"HTTP {check.code}"
            case ResponseStatus.DNS_ERROR:
                return "Connection Error"
            case ResponseStatus.TIMEOUT:
                return "Timeout"
            case _:
                return "Unknown Error"

    def _calculate_downtime_duration(self, checks: list[Check]) -> int:
        """
        Calculates the total unavailability time in seconds.

        Args:
            checks (list[Check]): List of URL checks objects.

        Returns:
            int: total unavailability time in seconds.
        """
        incidents = self._find_incidents(checks)
        return sum(incident["duration"] for incident in incidents)

    async def generate_weekly_report(
        self, url: str, end_date: datetime = None
    ) -> WeeklyReport:
        """
        Generates a report about service availability for a week.

        Args:
            url (str): URL of site.
            end_date (datetime, optional): The date of the last day in the report.
                The report will contain data on inspections 7 days before the specified date. 
                If not set, it will be datetime.now()

        Returns:
            WeeklyReport: An object containing information about URL checks for the week.
        """
        if not end_date:
            end_date = datetime.now()

        start_date = end_date - timedelta(days=7)
        checks = await self.db.get_check_records(url, start_date, end_date)
        stats = self._calculate_uptime_stats(checks)
        incidents = self._find_incidents(checks)
        daily_stats = self._calculate_daily_stats(checks, start_date, end_date)

        return WeeklyReport(
            url=url,
            period_start=start_date,
            period_end=end_date,
            stats=stats,
            incidents=incidents,
            daily_stats=daily_stats,
        )

    def _calculate_uptime_stats(self, checks: list[Check]) -> UptimeStats:
        """
        Calculates uptime/downtime statistics.

        Args:
            checks (list[Check]): List of URL checks objects.

        Returns:
            UptimeStats: An object containing information about uptime statistics.
        """
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

        downtime_duration = self._calculate_downtime_duration(checks)

        # only for successful checks
        response_times = [
            check.response_time
            for check in checks
            if self._is_check_successful(check) and check.response_time
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

    def _find_incidents(self, checks: list[Check]) -> list[dict]:
        """
        Analyzes checks records and detects periods of incidents (periods of site unavailability).

        Args:
            checks (list[Check]): List of URL checks objects.

        Returns:
            list[dict]: List of incidents info objects.
        """
        incidents = []
        current_incident = None
        failures_counter = 0
        incident_start = None

        for check in sorted(checks, key=lambda x: x.timestamp):
            is_successful = self._is_check_successful(check)

            if not is_successful:
                if failures_counter == 0:
                    incident_start = check.timestamp
                failures_counter += 1
            else:
                failures_counter = 0

            if failures_counter >= FAILURE_THRESHOLD and current_incident is None:
                current_incident = {
                    "start_time": incident_start,
                    "end_time": None,
                    "duration": 0,
                    "reason": self._get_failure_reason(check),
                }

            elif is_successful and current_incident is not None:
                current_incident["end_time"] = check.timestamp  # pylint: disable=unsupported-assignment-operation
                current_incident["duration"] = (                # pylint: disable=unsupported-assignment-operation
                    int(
                        (
                            current_incident["end_time"] - current_incident["start_time"] # pylint: disable=unsubscriptable-object
                        ).total_seconds()
                    )
                )
                incidents.append(current_incident)
                current_incident = None

        if current_incident is not None:
            # NOTE граница неоконченного инцидента - время последней записи или текущий момент?
            current_incident["end_time"] = check.timestamp  # datetime.now()           # pylint: disable=undefined-loop-variable
            current_incident["duration"] = int(
                (
                    current_incident["end_time"] - current_incident["start_time"]
                ).total_seconds()
            )
            incidents.append(current_incident)

        return incidents

    def _calculate_daily_stats(
        self, checks: list[Check], start_date: datetime, end_date: datetime
    ) -> list[dict]:
        """
        Calculates short statistics of site availability by day.

        Args:
            checks (list[Check]): List of URL checks object.
            start_date (datetime): First day in range.
            end_date (datetime): Last day in range.

        Returns:
            list[dict]: List of daily stats info.
        """
        daily_stats = []
        current_date = start_date.date()
        end_date_only = end_date.date()

        while current_date <= end_date_only:
            day_checks = [
                check for check in checks if check.timestamp.date() == current_date
            ]

            if day_checks:
                successful = sum(
                    1 for check in day_checks if self._is_check_successful(check)
                )
                total = len(day_checks)
                uptime_percent = (successful / total) * 100 if total > 0 else 0

                response_times = [
                    check.response_time
                    for check in day_checks
                    if self._is_check_successful(check) and check.response_time
                ]
                avg_response_time = (
                    sum(response_times) / len(response_times) if response_times else 0
                )
                # NOTE: Добавлять ли в статистику дни без проверок?
                # else:
                #     # uptime_percent = 0
                #     # avg_response_time = 0
                #     # total = 0

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

    def format_text_report(self, report: WeeklyReport) -> str:
        """
        Formats the weekly report in text format for Telegram

        Args:
            report (WeeklyReport): An object containing information about URL checks for the week.

        Returns:
            str: Week report in Telegram message format.
        """
        text = "📊 **Еженедельный отчет**\n\n"
        text += f"🌐 **Сайт:** {report.url}\n"
        text += f"📅 **Период:** {report.period_start.strftime('%d.%m.%Y')} "\
            f"- {report.period_end.strftime('%d.%m.%Y')}\n\n"

        stats = report.stats
        text += "📈 **Статистика:**\n"
        text += f"• Uptime: {stats.uptime_percentage}%\n"
        text += f"• Всего проверок: {stats.total_checks}\n"
        text += f"• Успешных: {stats.successful_checks}\n"
        text += f"• Неудачных: {stats.failed_checks}\n"

        if stats.downtime_duration > 0:
            downtime_str = format_duration(stats.downtime_duration)
            text += f"• Время недоступности: {downtime_str}\n"

        if stats.average_response_time > 0:
            text += f"• Среднее время ответа: {stats.average_response_time}ms\n"

        if report.incidents:
            text += f"\n🚨 **Инциденты ({len(report.incidents)}):**\n"
            for i, incident in enumerate(
                report.incidents[:5], 1
            ):  # first 5 incidents only
                duration_str = format_duration(incident["duration"])
                text += f"{i}. {incident['start_time'].strftime('%d.%m %H:%M')} " \
                    f"- {duration_str} ({incident['reason']})\n"

        text += "\n📊 **Процент успешных проверок по дням:**\n"
        text += self._create_text_chart(report.daily_stats)

        return text

    def _create_text_chart(self, daily_stats: list[dict]) -> str:
        """
        Creates a text graph of the percentage of successful checks.

        Args:
            daily_stats (list[dict]): List of daily stats info.

        Returns:
            str: visual text form of the graph.
        """
        chart = "\n"

        for day_stat in daily_stats:
            date_str = day_stat["date"].strftime("%d.%m")
            uptime = day_stat["uptime_percentage"]

            green_count = int(uptime // 10)
            red_count = 10 - green_count

            chart += (
                f"{date_str}: "
                f"{'🟢' * green_count}{'🔴' * red_count} "
                f"{uptime}%\n"
            )

        return chart


if __name__ == "__main__":
    import asyncio

    g = ReportGenerator()

    print(
        g.format_text_report(
            asyncio.run(g.generate_weekly_report(url="http://localhost:8000"))
        )
    )
