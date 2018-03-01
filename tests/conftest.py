import asyncio

import pytest

from aio_pyorient import ODBClient
from aio_pyorient.local_settings import TEST_DB, TEST_DB_PASSWORD, TEST_USER


@pytest.fixture(scope="module")
def loop(request):
    loop = asyncio.get_event_loop()
    def stop():
        loop.stop()
        loop.close()
    request.addfinalizer(stop)
    return loop

@pytest.fixture(scope="module")
async def client(loop):
    async with ODBClient("localhost", 2424, loop=loop) as client:
        yield client

@pytest.fixture(scope="module")
async def db_client(loop):
    async with ODBClient("localhost", 2424, loop=loop) as client:
        await client.open_db(TEST_DB, TEST_USER, TEST_DB_PASSWORD)
        yield client
