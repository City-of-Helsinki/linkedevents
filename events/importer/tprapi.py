import asyncio
import aiohttp
import logging
import sys

# Per module logger
logger = logging.getLogger(__name__)

content = []
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    "User-Agent": "Mozilla/5.0"
}


async def fetch(url, session):
    response = await session.request(method="GET", url=url, headers=headers)
    response.raise_for_status()
    json_response = await response.json()
    return json_response


async def process_json(json, page_no) -> None:
    content.append(json['results'])


async def main(allow_errors=False):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for page_no in range(1, 100):
            url = "https://palvelukartta.turku.fi/api/v2/unit/?page=%s" % page_no
            try:
                json = await fetch(url, session)
                tasks.append(process_json(json, page_no))
            except (
                aiohttp.ClientError,
                aiohttp.http_exceptions.HttpProcessingError,
            ) as err:
                if allow_errors == True:
                    # Error handling goes here.
                    # err.status, err.message etc.
                    logger.warn('Unit: %s reported: %s' %
                                (page_no, err.status))
                else:
                    pass
        await asyncio.gather(*tasks)
    return content


def async_main(x=None):
    # Works for both 3.6 and 3.7 Python versions.
    if sys.version_info >= (3, 7, 0):
        # 3.7+ support.
        return asyncio.run(main(x))
    else:
        # 3.6+ support.
        futures = [main(x)]
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.wait(futures))
        return content
