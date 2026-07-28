from redis import Redis

from app.core.config import settings

redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)


class RedisNotReadyError(RuntimeError):
    pass


def check_redis() -> None:
    try:
        redis_client.ping()
    except Exception as exc:
        raise RedisNotReadyError("Redis is not ready") from exc
