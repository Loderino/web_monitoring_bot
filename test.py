import asyncio

from scheduler import Scheduler
from utils.classes import Observer


class TestObserver(Observer):
    async def notify(self, url):
        print(url, "перестал быть доступным")


async def run_services():
    obs = TestObserver()
    scheduler = Scheduler()
    scheduler._manager._status_manager.subscribe(obs)
    await asyncio.sleep(100)


def main():
    asyncio.run(run_services())


if __name__ == "__main__":
    main()
