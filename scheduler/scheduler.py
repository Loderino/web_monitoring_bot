from apscheduler.schedulers.asyncio import AsyncIOScheduler

from constants import TICK_DURATION
from db.db_handler import DBHandler
from task_manager import TaskManager
from utils.log import get_logger


class Scheduler:
    """
    A class for scheduling tasks.
    """
    _logger = get_logger("Scheduler")
    _scheduler = AsyncIOScheduler()
    _manager = TaskManager()
    _db = DBHandler()

    def __init__(self):
        """
        Initializes the scheduler.
        Starts the scheduler and adds a job for each tick.
        """
        self.ticks = 0
        self._scheduler.add_job(
            self._tick, "interval", seconds=TICK_DURATION, max_instances=30
        )
        self._scheduler.start()

    async def _urls_per_tick(self) -> list[str]:
        """Generates lists of URLs to check on each tick.

        Returns:
            list[str]: list of URLs.
        """
        self.ticks += 1
        urls = await self._db.get_monitors_urls_for_tick(self.ticks * TICK_DURATION)
        if urls is None:
            self._logger.error("Error getting the url list for the current tick")
            return []
        return urls

    async def _tick(self) -> None:
        """
        A handler for each tick. Initializes the verification of web services by URLs specific to each tick.
        """
        urls = await self._urls_per_tick()
        self._logger.debug("Tick with urls %s", urls)
        await self._manager.run_task(urls)
