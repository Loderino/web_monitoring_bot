from datetime import datetime
from urllib.parse import urlparse

import pymongo

from db.models import Site, Monitor, Check, User
from constants import MONGO_URI
from utils.decorators import Singleton
from utils.meta import ExceptionHandlingMeta


@Singleton
class DBHandler(metaclass=ExceptionHandlingMeta):
    """
    Singleton Adapter for database.
    """

    def __init__(self):
        parsed_uri = urlparse(MONGO_URI)
        self._client = pymongo.AsyncMongoClient(parsed_uri.hostname, parsed_uri.port, timeoutMS=2000)
        self._db = self._client.monitoring_bot

    async def get_user(self, user_id: int) -> User:
        print(user_id)
        result = await self._db.users.find_one({"_id": user_id})
        print(result)
        if result is None:
            return False
        return User(**result)

    async def add_user(self, user_id: int, crash_n=True, recovery_n=True, weekly_n=True) -> User:
        result = await self._db.users.insert_one({
            "_id": user_id, 
            "site_crash_notifications": crash_n, 
            "site_recovery_notifications": recovery_n,
            "weekly_report_notifications": weekly_n
        })
        if result is None:
            return False
        return User(**result.inserted_id)
    
    async def update_user(self, user_id: int, crash_n=None, recovery_n=None, weekly_n=None):
        if crash_n is not None:
            return (await self._db.users.update_one({"_id": user_id}, {"$set": {"site_crash_notifications": crash_n}})).modified_count
        if recovery_n is not None:
            return (await self._db.users.update_one({"_id": user_id}, {"$set": {"site_recovery_notifications": recovery_n}})).modified_count
        if weekly_n is not None:
            return (await self._db.users.update_one({"_id": user_id}, {"$set": {"weekly_report_notifications": weekly_n}})).modified_count

    async def get_site(self, url: str) -> Site | None:
        """
        Gets a site availability info from database by URL.

        Args:
            url (str): URL of site.

        Returns:
            Site|None: information about site availability or `None` if there is no information about site.
        """
        if (site_record := await self._db.sites.find_one({"url": url})) is not None:
            site_record = Site(**site_record)
        return site_record

    async def update_site(self, url: str, status: int, failures: int) -> None:
        """
        Updates a record about site availability.

        Args:
            url (str): URL of site.
            status (int): Status code.
            failures (int): The number of failed checks in a row.
        """
        await self._db.sites.update_one(
            {"url": url}, {"$set": {"status": status, "consecutive_failures": failures}}
        )

    async def add_site(self, url: str, status: int) -> str:
        """
        Adds a record about site availability to database.

        Args:
            url (str): URL of site.
            status (int): Status code.

        Returns:
            str: Id of new record in database.
        """
        return str((await self._db.sites.insert_one(
            {"url": url, "status": status, "consecutive_failures": 0}
        )).inserted_id)

    async def add_monitor(self, user_id: int, url: str, interval: int) -> str:
        """
        Adds a record about monitoring URL to database.

        Args:
            user_id (int): Telegram user_id.
            url (str): URL to check.
            interval (int): Interval between checks in seconds.
        
        Returns:
            str: Id of new record in database.
        """
        return str((await self._db.monitors.insert_one(
            {"user_id": user_id, "url": url, "interval": interval}
        )).inserted_id)

    async def delete_monitor(self, user_id: int, url: str) -> int:
        """
        Deletes a record about monitoring URL from database.

        Args:
            user_id (int): Telegram user_id.
            url (str): Monitored URL to delete.
        
        Returns:
            int: Number of deleted monitors.
        """
        return (await self._db.monitors.delete_one({"user_id": user_id, "url": url})).deleted_count

    async def update_monitor(self, user_id: int, url: str, interval: int) -> int:
        """
        Updates a record about monitoring URL in database.

        Args:
            user_id (int): Telegram user_id.
            url (str): URL to check.
            interval (int): New interval value between checks in seconds.

        Returns:
            int: Number of modified_monitors.
        """
        return (await self._db.monitors.update_one(
            {"user_id": user_id, "url": url}, {"$set": {"interval": interval}}
        )).modified_count
    
    async def get_monitor_users_by_url(self, url: str) -> list[int]:
        return await self._db.monitors.distinct("user_id", {"url": url})
    async def get_user_monitors_count(self, user_id: int) -> int:
        """
        Calculates the number of user`s monitors.

        Args:
            user_id (int): User id in Telegram.

        Returns:
            int: number of user`s monitors.
        """
        return await self._db.monitors.count_documents({"user_id": user_id})

    async def get_user_monitors(self, user_id: int, skip: int = 0, limit: int = None) -> list[Monitor]:
        """
        Gets all monitors for user.

        Args:
            user_id (int): Telegram user_id.

        Returns:
            list[Monitor]: List of user`s monitors.
        """
        return [Monitor(**monitor_record) for monitor_record in 
                await self._db.monitors.find({"user_id": user_id}, skip=skip, limit=limit).to_list()]
    
    async def check_user_monitors_for_url(self, user_id: int, url: str):
        if await self._db.monitors.find_one({"user_id": user_id, "url": url}):
            return True
        return False

    async def get_monitors_urls_for_tick(self, seconds: int) -> list[str]:
        """
        Finds URLs to check for a specific moment.

        Args:
            seconds(int): The number of seconds that determines which URLs should be checked.

        Returns:
            list[str]: A list of unique URLs to check on specific moment.
        """
        return await self._db.monitors.distinct(
            "url", {"$where": f"({seconds} % this.interval) == 0"}
        )

    async def add_check_record(self, response_info: dict) -> str:
        """
        Adds a record of the URL checking results.

        Args:
            response_info (dict): document with information about url request and response.
        
        Returns:
            str: Id of new record in database.
        """
        return str((await self._db.checks.insert_one(response_info)).inserted_id)

    async def get_check_records(
        self, url: str, beg_date: datetime, end_date: datetime
    ) -> list[Check]:
        """
        Finds in the database all checks records for the specified period.

        Args:
            url (str): URL of checked site.
            beg_date (datetime): Begin of search period.
            end_date (datetime): End of search period.

        Returns:
            list[Check]: List of checks records.
        """
        return [Check(**check_record) for check_record in await self._db.checks.find(
            {"url": url, "timestamp": {"$gte": beg_date, "$lte": end_date}}
        ).to_list()]

if __name__ == "__main__":
    import asyncio

    async def main():
        d = DBHandler()
        print(await d.get_site("https://ya.ru"))
        # await d.add_monitor(123, "http://localhost:8000", 10)
        # await d.add_monitor(1235, "https://ya.ru", 20)
        # await d.delete_monitor(1234, "https://ya.ru")
        # await d.update_monitor(1234, "https://ya.ru", 120)
        # print(
        #     await d.get_check_records(
        #         "http://localhost:8000",
        #         datetime(year=2025, month=1, day=1),
        #         datetime(year=2026, month=1, day=1),
        #     )
        # )

    asyncio.run(main())
