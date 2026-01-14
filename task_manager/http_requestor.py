import asyncio
import time

from httpx import (
    AsyncClient,
    ConnectError,
    ConnectTimeout,
    HTTPStatusError,
    Timeout,
)

from constants import REQUEST_TIMEOUT
from task_manager.models import ResponseData, ResponseStatus
from utils.decorators import Singleton
from utils.meta import ExceptionHandlingMeta


@Singleton
class HTTPRequestor(metaclass=ExceptionHandlingMeta):
    """
    A class for asynchronous http requests.
    """

    def __init__(self):
        timeout = Timeout(None, connect=REQUEST_TIMEOUT)
        self._client = AsyncClient(timeout=timeout)

    async def make_request(self, url: str) -> ResponseData:
        """
        Makes a GET request to the URL and returns a response data.

        Args:
            url (str): URL to make get request.

        Returns:
            ResponseData: object with data about response.
        """
        start_time = asyncio.get_event_loop().time()
        timestamp = int(time.time())
        try:
            response = await self._client.get(url, follow_redirects=True)
            response_time = asyncio.get_event_loop().time() - start_time
            response.raise_for_status()
        except ConnectError:
            return ResponseData(
                url=url, status=ResponseStatus.DNS_ERROR, timestamp=timestamp
            )
        except ConnectTimeout:
            return ResponseData(
                url=url, status=ResponseStatus.TIMEOUT, timestamp=timestamp
            )
        except HTTPStatusError:
            return ResponseData(
                url=url,
                status=ResponseStatus.UNAVAILABLE,
                timestamp=timestamp,
                code=response.status_code,
            )
        return ResponseData(
            url=url,
            status=ResponseStatus.OK,
            timestamp=timestamp,
            code=response.status_code,
            response_time=response_time,
        )
