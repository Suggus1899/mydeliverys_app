from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio.client import PubSub

from app.core.config import settings

_control_client: redis.Redis | None = None
_cache_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Redis de controles, idempotencia, OTP y Pub/Sub sin eviction."""
    global _control_client
    if _control_client is None:
        _control_client = redis.from_url(
            settings.REDIS_CONTROL_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    return _control_client


def get_cache_redis() -> redis.Redis:
    """Redis evictable dedicado a datos reconstruibles."""
    global _cache_client
    if _cache_client is None:
        _cache_client = redis.from_url(
            settings.REDIS_CACHE_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    return _cache_client


async def init_redis() -> None:
    """Initialize Redis connection."""
    get_redis()
    get_cache_redis()


async def close_redis() -> None:
    """Close Redis connection."""
    global _cache_client, _control_client
    if _control_client:
        await _control_client.aclose()
        _control_client = None
    if _cache_client:
        await _cache_client.aclose()
        _cache_client = None


@asynccontextmanager
async def redis_connection() -> AsyncGenerator[redis.Redis, None]:
    """Context manager for Redis connection."""
    client = get_redis()
    try:
        yield client
    except Exception:
        # Connection will be recreated on next use
        global _control_client
        _control_client = None
        raise


# Pub/Sub helpers
async def publish(channel: str, message: str) -> int:
    """Publish message to Redis channel."""
    return await get_redis().publish(channel, message)


async def subscribe(channel: str) -> PubSub:
    """Subscribe to Redis channel."""
    pubsub = get_redis().pubsub()
    await pubsub.subscribe(channel)
    return pubsub


# Cache helpers
async def cache_get(key: str) -> str | None:
    """Get value from cache."""
    return await get_cache_redis().get(key)


async def cache_set(key: str, value: str, ttl: int) -> bool:
    """Set value in cache with TTL."""
    return await get_cache_redis().setex(key, ttl, value)


async def cache_delete(key: str) -> int:
    """Delete key from cache."""
    return await get_cache_redis().delete(key)


async def cache_delete_pattern(pattern: str) -> int:
    """Delete keys matching pattern."""
    cursor = 0
    deleted = 0
    while True:
        cursor, keys = await get_cache_redis().scan(cursor, match=pattern, count=100)
        if keys:
            deleted += await get_cache_redis().delete(*keys)
        if cursor == 0:
            break
    return deleted
