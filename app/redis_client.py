import redis.asyncio as redis

from .config import get_settings

settings = get_settings()

print(f"Redis URL: {settings.redis_url}")
print(f"Redis Timeout: {settings.redis_timeout}")
print(f"Redis TTL: {settings.cache_ttl}")

redis_client = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=settings.redis_timeout,
    socket_timeout=settings.redis_timeout,
)
