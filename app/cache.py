from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings

redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)


def check_redis() -> None:
    try:
        redis_client.ping()
    except RedisError as exc:
        raise ConnectionError("Redis is not ready") from exc
