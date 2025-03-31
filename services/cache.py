import redis
from redis.asyncio import Redis
from functools import wraps
from typing import Callable, Any, Optional
import pickle
import hashlib
from datetime import timedelta
from config import settings
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    """مدیریت کش پیشرفته با پشتیبانی از Async"""
    
    def __init__(self):
        self.redis: Optional[Redis] = None
        self._connect()

    def _connect(self):
        """اتصال به Redis"""
        try:
            self.redis = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=False,
                socket_connect_timeout=5
            )
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error(f"Redis connection failed: {str(e)}")
            self.redis = None

    async def get(self, key: str) -> Any:
        """دریافت داده از کش"""
        if not self.redis:
            return None
            
        try:
            data = await self.redis.get(key)
            return pickle.loads(data) if data else None
        except Exception as e:
            logger.error(f"Cache get failed: {str(e)}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """ذخیره داده در کش"""
        if not self.redis:
            return False
            
        try:
            await self.redis.setex(
                key,
                timedelta(seconds=ttl),
                pickle.dumps(value)
            return True
        except Exception as e:
            logger.error(f"Cache set failed: {str(e)}")
            return False

    def cache(self, ttl: int = 600, key_prefix: str = None):
        """دکوراتور کش برای توابع"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                if not self.redis:
                    return await func(*args, **kwargs)
                
                cache_key = self._generate_key(func, key_prefix, *args, **kwargs)
                cached = await self.get(cache_key)
                if cached is not None:
                    return cached
                
                result = await func(*args, **kwargs)
                await self.set(cache_key, result, ttl)
                return result
            return wrapper
        return decorator

    def _generate_key(self, func: Callable, prefix: str, *args, **kwargs) -> str:
        """تولید کلید کش یکتا"""
        key_parts = [
            prefix or func.__module__,
            func.__name__,
            hashlib.md5(pickle.dumps(args)).hexdigest(),
            hashlib.md5(pickle.dumps(kwargs)).hexdigest()
        ]
        return ":".join(key_parts)

# نمونه Singleton از Cache
cache = CacheManager()
