from __future__ import annotations

import redis.asyncio as redis


def create_redis(dsn: str) -> "redis.Redis":
    return redis.from_url(
        dsn,
        encoding="utf-8",
        decode_responses=False,
        max_connections=32,
        health_check_interval=30,
        retry_on_timeout=True,
    )
