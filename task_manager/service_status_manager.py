from constants import FAILURE_THRESHOLD
from db.db_handler import DBHandler
from task_manager.models import ResponseData, Notification
from utils.classes import Observer
from utils.decorators import Singleton
from utils.enums import ResponseStatus, SiteStatus
from utils.log import get_logger


@Singleton
class ServiceStatusManager:
    """
    Singleton websites status manager.
    Decides on the availability or unavailability of the site and sends notifications to observers.
    """

    _logger = get_logger("ServiceStatusManager")
    def __init__(self):
        self.db = DBHandler()
        self.observers: list[Observer] = []

    def subscribe(self, observer: Observer) -> None:
        """
        Subscribe observer to notifications.

        Args:
            observer (Observer): the object in which the notify method is implemented.
        """
        self.observers.append(observer)

    def unsubscribe(self, observer: Observer) -> None:
        """
        Unsubscribe observer from notifications

        Args:
            observer (Observer): the object that was subscribed.
        """
        if observer in self.observers:
            self.observers.remove(observer)

    async def _notify_observers(self, notification: Notification):
        """
        Notifies all observers of an event.

        Args:
            notification (Notification): The notification object, which means that the site has changed its status
        """
        for observer in self.observers:
            self._logger.info("Observer %s was notified with %s", observer.name, notification)
            await observer.notify(notification)

    async def process_check_result(self, check_info: ResponseData) -> None:
        """
        Process the checking result and update the site availability status.

        Args:
            check_info (ResponseData): Information about request to URL.
        """
        site = await self.db.get_site(check_info.url)
        if not site:
            if not await self.db.add_site(check_info.url, SiteStatus.AVAILABLE.value):
                self._logger.warning("Error writing the site %s to the database.", check_info.url)
                return
            site = await self.db.get_site(check_info.url)

        current_status = site.status
        failures = site.consecutive_failures

        if check_info.status == ResponseStatus.OK:
            if current_status == SiteStatus.UNAVAILABLE or failures > 0:
                await self.db.update_site(check_info.url, SiteStatus.AVAILABLE.value, 0)
                await self._notify_observers(Notification(check_info.url, SiteStatus.AVAILABLE))
        else:
            failures += 1
            if failures >= FAILURE_THRESHOLD:
                new_status = SiteStatus.UNAVAILABLE
            else:
                new_status = current_status
            await self.db.update_site(check_info.url, new_status.value, failures)

            if (
                current_status == SiteStatus.AVAILABLE
                and new_status == SiteStatus.UNAVAILABLE
            ):
                await self._notify_observers(Notification(check_info.url, SiteStatus.UNAVAILABLE))
