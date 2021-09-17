import requests
import asyncio
import aiohttp
import logging
import math
import json
import sys

# Per module logger
logger = logging.getLogger(__name__)

headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    "User-Agent": "Mozilla/5.0"
}


async def fetch(session, url, id) -> dict:
    async with session.get(url) as response:
        data = await response.read()
        json_response = json.loads(data)
        result = json_response.get('results', None)
        if result:
            return result
        else:
            err_result = json_response.get('detail', None)
            if err_result:
                raise Exception(
                    "Palvelukartta unit reported: '%s' for page: %s" % (err_result, id))
            # If the API ever changes error handling in the future, notify about it.
            raise Exception(
                "Palvelukartta unit: '%s' request did not fail, but API parsing was incorrect. API has changed?" % id)


async def main(unit_pages) -> dict:
    async with aiohttp.ClientSession() as session:

        tasks = []
        for page_no in range(1, unit_pages):
            URL = 'https://palvelukartta.turku.fi/api/v2/unit/?page=%s' % page_no
            tasks.append(fetch(session, URL, page_no))
        try:
            res = await asyncio.gather(*tasks, return_exceptions=False)
            return res
        except Exception as e:
            logger.warn(e)
            await asyncio.sleep(1)


def async_main(retry_count=3) -> dict:
    # Currently works in 3.6 Python
    # Works for both 3.6 and 3.7 Python versions.
    
    # Fetch page_count by calculating page_size 'count'
    # by dividing it with default value 20 (servicemap).
    url = "https://palvelukartta.turku.fi/api/v2/unit"

    try:
        fetch = requests.get(url, headers=headers)
        response = fetch.json()
        calc = math.modf(response['count'] / 20)
        
        if calc[0] != float(0):
            page_count = int(calc[1]+1)
        else:
            page_count = int(calc[1])
    except Exception as e:
         raise Exception(
            "Something went wrong in the 'page count' pre-processing phase of TPRAPI: %s" % e)

    for connection_retries in range(retry_count):
        if sys.version_info >= (3, 8, 0):
            res = asyncio.run(main(unit_pages=page_count))
            if res:
                return res
        else:
            # 3.6+ support.
            loop = asyncio.get_event_loop()
            task = loop.create_task(main(unit_pages=page_count))
            a = loop.run_until_complete(task)
            task.cancel()
            if a:
                return a
    logger.warn("Retry limit exceeded! Giving up...")
