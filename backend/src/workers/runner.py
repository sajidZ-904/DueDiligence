from __future__ import annotations

import asyncio
from typing import Awaitable


def schedule(coro: Awaitable[None]) -> None:
    asyncio.create_task(coro)

