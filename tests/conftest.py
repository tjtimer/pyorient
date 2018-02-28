import asyncio

import pytest

from aio_pyorient import ODBClient


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
