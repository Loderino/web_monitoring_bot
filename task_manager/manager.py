import asyncio

from db.db_handler import DBHandler
from task_manager import HTTPRequestor
from task_manager.service_status_manager import ServiceStatusManager
from utils.log import get_logger

class TaskManager:
    """Runs the tasks of URL checking for each scheduler tick."""
    _logger = get_logger("TaskManager")
    _requestor = HTTPRequestor()
    _db = DBHandler()
    _status_manager = ServiceStatusManager()

    async def run_task(self, urls: list) -> None:
        """
        Runs the URLs checking task.

        Args:
            urls (list): list of URLs.
        """
        check_url_tasks = [self._requestor.make_request(url) for url in urls]
        responses_data = await asyncio.gather(*check_url_tasks)

        while None in responses_data:
            idx = responses_data.index(None)
            self._logger.warning("Error when making a request to the %s.", urls[idx])
            responses_data.pop(idx)

        add_checks_tasks = [
            self._db.add_check_record(data.prepare_for_database())
            for data in responses_data
        ]
        for i, check_id in enumerate(await asyncio.gather(*add_checks_tasks)):
            if not check_id:
                self._logger.warning("Error writing the check %s to the database.", responses_data[i].prepare_for_database())

        update_sites_statuses_tasks = [
            self._status_manager.process_check_result(data) for data in responses_data
        ]
        await asyncio.gather(*update_sites_statuses_tasks)