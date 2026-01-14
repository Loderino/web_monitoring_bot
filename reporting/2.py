import io
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont


class ChartGenerator:
    def __init__(self):
        # Настройки для графиков
        plt.style.use("seaborn-v0_8")
        self.colors = {
            "success": "#2ecc71",
            "failure": "#e74c3c",
            "warning": "#f39c12",
            "background": "#ecf0f1",
            "text": "#2c3e50",
        }

    async def generate_uptime_chart(self, report) -> io.BytesIO:
        """График uptime по дням недели"""
        fig, ax = plt.subplots(figsize=(12, 6))

        dates = [stat["date"] for stat in report.daily_stats]
        uptimes = [stat["uptime_percentage"] for stat in report.daily_stats]

        # Основной график
        ax.plot(
            dates,
            uptimes,
            color=self.colors["success"],
            linewidth=3,
            marker="o",
            markersize=8,
        )
        ax.fill_between(dates, uptimes, alpha=0.3, color=self.colors["success"])

        # Настройки осей
        ax.set_ylim(0, 100)
        ax.set_ylabel("Uptime %", fontsize=12, fontweight="bold")
        ax.set_title(f"Uptime за неделю - {report.url}", fontsize=14, fontweight="bold")

        # Форматирование дат
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        ax.xaxis.set_major_locator(mdates.DayLocator())
        plt.xticks(rotation=45)

        # Добавляем горизонтальные линии для ориентира
        ax.axhline(y=99, color="red", linestyle="--", alpha=0.5, label="99% SLA")
        ax.axhline(y=95, color="orange", linestyle="--", alpha=0.5, label="95% SLA")

        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        # Сохраняем в BytesIO
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="PNG", dpi=300, bbox_inches="tight")
        img_buffer.seek(0)
        plt.close()

        return img_buffer

    async def generate_response_time_chart(self, report) -> io.BytesIO:
        """График времени ответа"""
        fig, ax = plt.subplots(figsize=(12, 6))

        dates = [stat["date"] for stat in report.daily_stats]
        response_times = [stat["average_response_time"] for stat in report.daily_stats]

        # Убираем нулевые значения для лучшей визуализации
        filtered_data = [(d, rt) for d, rt in zip(dates, response_times) if rt > 0]
        if not filtered_data:
            # Если нет данных, создаем пустой график
            ax.text(
                0.5,
                0.5,
                "Нет данных о времени ответа",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=16,
            )
        else:
            dates_filtered, times_filtered = zip(*filtered_data)

            ax.plot(
                dates_filtered,
                times_filtered,
                color=self.colors["warning"],
                linewidth=3,
                marker="s",
                markersize=6,
            )
            ax.fill_between(
                dates_filtered, times_filtered, alpha=0.3, color=self.colors["warning"]
            )

            # Настройки осей
            ax.set_ylabel("Время ответа (мс)", fontsize=12, fontweight="bold")
            ax.set_title(
                f"Время ответа за неделю - {report.url}", fontsize=14, fontweight="bold"
            )

            # Форматирование дат
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
            plt.xticks(rotation=45)

        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="PNG", dpi=300, bbox_inches="tight")
        img_buffer.seek(0)
        plt.close()

        return img_buffer

    async def generate_incidents_timeline(self, report) -> io.BytesIO:
        """Временная линия инцидентов"""
        fig, ax = plt.subplots(figsize=(14, 8))

        if not report.incidents:
            ax.text(
                0.5,
                0.5,
                "Инцидентов не обнаружено 🎉",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=18,
                color=self.colors["success"],
            )
        else:
            # Создаем временную линию
            y_pos = 0
            colors_list = [self.colors["failure"], self.colors["warning"]]

            for i, incident in enumerate(report.incidents):
                start = incident["start_time"]
                end = incident["end_time"] if incident["end_time"] else datetime.now()
                duration = incident["duration"]

                # Рисуем полосу инцидента
                ax.barh(
                    y_pos,
                    (end - start).total_seconds() / 3600,
                    left=mdates.date2num(start),
                    height=0.6,
                    color=colors_list[i % len(colors_list)],
                    alpha=0.7,
                )

                # Добавляем подпись
                duration_str = self._format_duration(duration)
                ax.text(
                    mdates.date2num(start) + (end - start).total_seconds() / 7200,
                    y_pos,
                    f'{incident["reason"]}\n{duration_str}',
                    ha="center",
                    va="center",
                    fontsize=10,
                    fontweight="bold",
                )

                y_pos += 1

            # Настройки осей
            ax.set_ylim(-0.5, len(report.incidents) - 0.5)
            ax.set_ylabel("Инциденты", fontsize=12, fontweight="bold")
            ax.set_xlabel("Время", fontsize=12, fontweight="bold")
            ax.set_title(
                f"Временная линия инцидентов - {report.url}",
                fontsize=14,
                fontweight="bold",
            )

            # Форматирование временной оси
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M"))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
            plt.xticks(rotation=45)

        plt.tight_layout()

        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="PNG", dpi=300, bbox_inches="tight")
        img_buffer.seek(0)
        plt.close()

        return img_buffer

    async def generate_status_heatmap(self, report) -> io.BytesIO:
        """Тепловая карта статусов по часам и дням"""
        fig, ax = plt.subplots(figsize=(16, 8))

        # Создаем матрицу 7x24 (дни x часы)
        heatmap_data = np.zeros((7, 24))

        # Получаем детальные данные из БД (нужно будет добавить этот метод)
        # Пока создадим примерную карту на основе daily_stats
        for i, day_stat in enumerate(report.daily_stats):
            uptime = day_stat["uptime_percentage"]
            # Заполняем все часы дня одним значением (упрощение)
            heatmap_data[i, :] = uptime

        # Создаем heatmap
        im = ax.imshow(heatmap_data, cmap="RdYlGn", aspect="auto", vmin=0, vmax=100)

        # Настройки осей
        ax.set_xticks(range(24))
        ax.set_xticklabels([f"{i:02d}:00" for i in range(24)])
        ax.set_yticks(range(7))
        ax.set_yticklabels(["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"])

        ax.set_xlabel("Час дня", fontsize=12, fontweight="bold")
        ax.set_ylabel("День недели", fontsize=12, fontweight="bold")
        ax.set_title(
            f"Карта доступности по часам - {report.url}", fontsize=14, fontweight="bold"
        )

        # Добавляем colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label("Uptime %", fontsize=12, fontweight="bold")

        plt.tight_layout()

        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="PNG", dpi=300, bbox_inches="tight")
        img_buffer.seek(0)
        plt.close()

        return img_buffer

    async def generate_summary_dashboard(self, report) -> io.BytesIO:
        """Сводная панель с несколькими графиками"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

        # График 1: Uptime по дням
        dates = [stat["date"] for stat in report.daily_stats]
        uptimes = [stat["uptime_percentage"] for stat in report.daily_stats]

        ax1.plot(dates, uptimes, color=self.colors["success"], linewidth=2, marker="o")
        ax1.fill_between(dates, uptimes, alpha=0.3, color=self.colors["success"])
        ax1.set_title("Uptime по дням", fontweight="bold")
        ax1.set_ylabel("Uptime %")
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))

        # График 2: Время ответа
        response_times = [
            stat["average_response_time"]
            for stat in report.daily_stats
            if stat["average_response_time"] > 0
        ]
        if response_times:
            ax2.bar(
                range(len(response_times)),
                response_times,
                color=self.colors["warning"],
                alpha=0.7,
            )
            ax2.set_title("Время ответа", fontweight="bold")
            ax2.set_ylabel("мс")
        else:
            ax2.text(
                0.5,
                0.5,
                "Нет данных",
                ha="center",
                va="center",
                transform=ax2.transAxes,
            )

        # График 3: Круговая диаграмма статистики
        stats = report.stats
        labels = ["Успешные", "Неудачные"]
        sizes = [stats.successful_checks, stats.failed_checks]
        colors = [self.colors["success"], self.colors["failure"]]

        ax3.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%", startangle=90)
        ax3.set_title("Соотношение проверок", fontweight="bold")

        # График 4: Статистика инцидентов
        if report.incidents:
            incident_durations = [
                inc["duration"] / 3600 for inc in report.incidents
            ]  # в часах
            incident_labels = [f"#{i+1}" for i in range(len(incident_durations))]

            ax4.bar(
                incident_labels,
                incident_durations,
                color=self.colors["failure"],
                alpha=0.7,
            )
            ax4.set_title("Длительность инцидентов", fontweight="bold")
            ax4.set_ylabel("Часы")
        else:
            ax4.text(
                0.5,
                0.5,
                "Инцидентов нет 🎉",
                ha="center",
                va="center",
                transform=ax4.transAxes,
                fontsize=14,
                color=self.colors["success"],
            )

        # Общий заголовок
        fig.suptitle(f"Сводный отчет - {report.url}", fontsize=16, fontweight="bold")
        plt.tight_layout()

        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="PNG", dpi=300, bbox_inches="tight")
        img_buffer.seek(0)
        plt.close()

        return img_buffer

    async def generate_ascii_chart(self, report) -> str:
        """ASCII график для простых случаев"""
        chart = f"📊 ASCII График Uptime - {report.url}\n"
        chart += "=" * 50 + "\n"

        max_uptime = max([stat["uptime_percentage"] for stat in report.daily_stats])

        for stat in report.daily_stats:
            date_str = stat["date"].strftime("%d.%m")
            uptime = stat["uptime_percentage"]

            # Создаем ASCII бар
            bar_length = int((uptime / 100) * 30)
            bar = "█" * bar_length + "░" * (30 - bar_length)

            chart += f"{date_str}: |{bar}| {uptime:5.1f}%\n"

        chart += "=" * 50 + "\n"
        chart += f"Средний uptime: {sum([s['uptime_percentage'] for s in report.daily_stats]) / len(report.daily_stats):.1f}%"

        return chart

    def _format_duration(self, seconds: int) -> str:
        """Форматировать длительность"""
        if seconds < 60:
            return f"{seconds}с"
        elif seconds < 3600:
            return f"{seconds // 60}м"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}ч {minutes}м"


class ReportGeneratorWithCharts:
    def __init__(self, db_handler):
        self.db_handler = db_handler
        self.chart_generator = ChartGenerator()

    async def generate_visual_report(
        self, monitor_id: str, chart_type: str = "summary"
    ):
        """Генерировать отчет с графиками"""
        # Используем базовый ReportGenerator для получения данных
        base_generator = ReportGenerator(self.db_handler)
        report = await base_generator.generate_weekly_report(monitor_id)

        # Генерируем нужный тип графика
        chart_methods = {
            "uptime": self.chart_generator.generate_uptime_chart,
            "response_time": self.chart_generator.generate_response_time_chart,
            "incidents": self.chart_generator.generate_incidents_timeline,
            "heatmap": self.chart_generator.generate_status_heatmap,
            "summary": self.chart_generator.generate_summary_dashboard,
            "ascii": self.chart_generator.generate_ascii_chart,
        }

        if chart_type not in chart_methods:
            raise ValueError(f"Unknown chart type: {chart_type}")

        if chart_type == "ascii":
            chart_data = await chart_methods[chart_type](report)
            return {"report": report, "chart_type": "text", "chart_data": chart_data}
        else:
            chart_buffer = await chart_methods[chart_type](report)
            return {"report": report, "chart_type": "image", "chart_data": chart_buffer}

    async def generate_all_charts(self, monitor_id: str) -> Dict[str, Any]:
        """Генерировать все типы графиков для монитора"""
        base_generator = ReportGenerator(self.db_handler)
        report = await base_generator.generate_weekly_report(monitor_id)

        charts = {}

        # Генерируем все графики
        chart_types = ["uptime", "response_time", "incidents", "heatmap", "summary"]

        for chart_type in chart_types:
            try:
                chart_buffer = await getattr(
                    self.chart_generator, f"generate_{chart_type}_chart"
                )(report)
                charts[chart_type] = chart_buffer
            except Exception as e:
                print(f"Error generating {chart_type} chart: {e}")
                charts[chart_type] = None

        # ASCII график отдельно
        try:
            charts["ascii"] = await self.chart_generator.generate_ascii_chart(report)
        except Exception as e:
            print(f"Error generating ASCII chart: {e}")
            charts["ascii"] = None

        return {"report": report, "charts": charts}

    async def generate_comparison_chart(self, monitor_ids: List[str]) -> io.BytesIO:
        """Сравнительный график для нескольких мониторов"""
        fig, ax = plt.subplots(figsize=(14, 8))

        base_generator = ReportGenerator(self.db_handler)
        colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"]

        for i, monitor_id in enumerate(monitor_ids[:6]):  # Максимум 6 мониторов
            try:
                report = await base_generator.generate_weekly_report(monitor_id)

                dates = [stat["date"] for stat in report.daily_stats]
                uptimes = [stat["uptime_percentage"] for stat in report.daily_stats]

                # Извлекаем домен из URL для подписи
                domain = (
                    report.url.replace("https://", "")
                    .replace("http://", "")
                    .split("/")[0]
                )

                ax.plot(
                    dates,
                    uptimes,
                    color=colors[i],
                    linewidth=2,
                    marker="o",
                    label=domain,
                    markersize=6,
                )

            except Exception as e:
                print(f"Error processing monitor {monitor_id}: {e}")

        ax.set_ylim(0, 100)
        ax.set_ylabel("Uptime %", fontsize=12, fontweight="bold")
        ax.set_xlabel("Дата", fontsize=12, fontweight="bold")
        ax.set_title("Сравнение Uptime за неделю", fontsize=14, fontweight="bold")

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        ax.xaxis.set_major_locator(mdates.DayLocator())
        plt.xticks(rotation=45)

        ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="PNG", dpi=300, bbox_inches="tight")
        img_buffer.seek(0)
        plt.close()

        return img_buffer


# Дополнительный класс для экспорта отчетов
class ReportExporter:
    def __init__(self, db_handler):
        self.db_handler = db_handler

    async def export_to_csv(self, monitor_id: str, period_days: int = 7) -> io.StringIO:
        """Экспорт данных в CSV"""
        import csv
        from io import StringIO

        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        checks = await self.db_handler.get_checks_by_period(
            monitor_id, start_date, end_date
        )

        output = StringIO()
        writer = csv.writer(output)

        # Заголовки
        writer.writerow(
            [
                "Timestamp",
                "Status Code",
                "Response Time (ms)",
                "Success",
                "Error Message",
                "URL",
            ]
        )

        # Данные
        for check in checks:
            writer.writerow(
                [
                    check["timestamp"].isoformat(),
                    check.get("status_code", ""),
                    check.get("response_time", ""),
                    "Yes" if self._is_check_successful(check) else "No",
                    check.get("error_message", ""),
                    check.get("url", ""),
                ]
            )

        output.seek(0)
        return output

    async def export_to_json(
        self, monitor_id: str, period_days: int = 7
    ) -> io.StringIO:
        """Экспорт данных в JSON"""
        import json
        from io import StringIO

        base_generator = ReportGenerator(self.db_handler)
        report = await base_generator.generate_weekly_report(monitor_id)

        # Конвертируем dataclass в dict
        export_data = {
            "monitor_id": report.monitor_id,
            "url": report.url,
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "stats": {
                "total_checks": report.stats.total_checks,
                "successful_checks": report.stats.successful_checks,
                "failed_checks": report.stats.failed_checks,
                "uptime_percentage": report.stats.uptime_percentage,
                "downtime_duration": report.stats.downtime_duration,
                "average_response_time": report.stats.average_response_time,
                "max_response_time": report.stats.max_response_time,
                "min_response_time": report.stats.min_response_time,
            },
            "incidents": [
                {
                    "start_time": inc["start_time"].isoformat(),
                    "end_time": (
                        inc["end_time"].isoformat() if inc["end_time"] else None
                    ),
                    "duration": inc["duration"],
                    "reason": inc["reason"],
                }
                for inc in report.incidents
            ],
            "daily_stats": [
                {
                    "date": stat["date"].isoformat(),
                    "uptime_percentage": stat["uptime_percentage"],
                    "total_checks": stat["total_checks"],
                    "average_response_time": stat["average_response_time"],
                }
                for stat in report.daily_stats
            ],
        }

        output = StringIO()
        json.dump(export_data, output, indent=2, ensure_ascii=False)
        output.seek(0)
        return output

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


# Пример использования всех компонентов
class ComprehensiveReportSystem:
    def __init__(self, db_handler):
        self.db_handler = db_handler
        self.report_generator = ReportGenerator(db_handler)
        self.chart_generator = ReportGeneratorWithCharts(db_handler)
        self.exporter = ReportExporter(db_handler)

    async def get_full_report_package(self, monitor_id: str) -> Dict[str, Any]:
        """Получить полный пакет отчетов"""
        # Базовый отчет
        text_report = await self.report_generator.generate_weekly_report(monitor_id)

        # Все графики
        visual_reports = await self.chart_generator.generate_all_charts(monitor_id)

        # Экспорт данных
        csv_data = await self.exporter.export_to_csv(monitor_id)
        json_data = await self.exporter.export_to_json(monitor_id)

        return {
            "text_report": text_report,
            "visual_reports": visual_reports,
            "exports": {"csv": csv_data, "json": json_data},
        }

    async def get_user_summary(self, user_id: str) -> Dict[str, Any]:
        """Сводка по всем мониторам пользователя"""
        monitors = await self.db_handler.get_user_monitors(user_id)

        summary = {
            "total_monitors": len(monitors),
            "healthy_monitors": 0,
            "unhealthy_monitors": 0,
            "monitors_data": [],
        }

        for monitor in monitors:
            try:
                report = await self.report_generator.generate_weekly_report(
                    monitor["_id"]
                )

                is_healthy = report.stats.uptime_percentage >= 99.0
                if is_healthy:
                    summary["healthy_monitors"] += 1
                else:
                    summary["unhealthy_monitors"] += 1

                summary["monitors_data"].append(
                    {
                        "monitor_id": monitor["_id"],
                        "url": monitor["url"],
                        "uptime": report.stats.uptime_percentage,
                        "incidents_count": len(report.incidents),
                        "status": "healthy" if is_healthy else "unhealthy",
                    }
                )

            except Exception as e:
                print(f"Error processing monitor {monitor['_id']}: {e}")
                summary["unhealthy_monitors"] += 1

        return summary
