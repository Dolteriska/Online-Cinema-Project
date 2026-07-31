from slowapi import Limiter
from slowapi.util import get_remote_address
from src.config.settings import settings


limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=["100/minute"],
)
