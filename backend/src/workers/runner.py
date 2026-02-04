from __future__ import annotations

import asyncio
from typing import Awaitable


def schedule(coro: Awaitable[None]) -> None:
    async def run_in_thread() -> None:
        await asyncio.to_thread(asyncio.run, coro)

    asyncio.create_task(run_in_thread())

