import redis
from redis.asyncio import Redis
from functools import wraps
from typing import Callable, Any, Optional, Union, Dict, List
import pickle
import hashlib
from datetime import timedelta
from config import settings
import logging
import asyncio
import inspect

logger = logging.getLogger(__name__)

class CacheManager:
    """مدیریت کش پیشرفته با پشتیبانی از Async و قابلیت‌های اضافه برای ربات تلگرام"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.redis = None
            cls._instance._connect()
        return cls._instance

    def _connect(self):
        """اتصال به Redis با تلاش مجدد خودکار"""
        try:
            self.redis = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=False,
                socket_connect_timeout=5,
                socket_keepalive=True,
                retry_on_timeout=True,
                max_connections=100
            )
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error(f"Redis connection failed: {str(e)}")
            self.redis = None

    async def _ensure_connection(self):
        """اطمینان از اتصال به Redis"""
        if not self.redis:
            self._connect()
            # اگر هنوز متصل نشده، یک تلاش دیگر بعد از تاخیر
            if not self.redis and settings.REDIS_RETRY:
                await asyncio.sleep(2)
                self._connect()

    async def get(self, key: str) -> Any:
        """دریافت داده از کش"""
        await self._ensure_connection()
        if not self.redis:
            return None
            
        try:
            data = await self.redis.get(key)
            return pickle.loads(data) if data else None
        except redis.ConnectionError:
            logger.warning("Redis connection lost, reconnecting...")
            self._connect()
            return None
        except Exception as e:
            logger.error(f"Cache get failed for key {key}: {str(e)}", exc_info=True)
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """ذخیره داده در کش"""
        await self._ensure_connection()
        if not self.redis:
            return False
            
        try:
            await self.redis.setex(
                key,
                timedelta(seconds=ttl),
                pickle.dumps(value)
            )
            return True
        except redis.ConnectionError:
            logger.warning("Redis connection lost during set operation")
            return False
        except Exception as e:
            logger.error(f"Cache set failed for key {key}: {str(e)}", exc_info=True)
            return False

    async def delete(self, key: str) -> bool:
        """حذف یک کلید از کش"""
        await self._ensure_connection()
        if not self.redis:
            return False
            
        try:
            return await self.redis.delete(key) > 0
        except Exception as e:
            logger.error(f"Cache delete failed for key {key}: {str(e)}")
            return False

    async def keys(self, pattern: str = "*") -> List[str]:
        """لیست کلیدهای مطابق با الگو"""
        await self._ensure_connection()
        if not self.redis:
            return []
            
        try:
            return [k.decode('utf-8') for k in await self.redis.keys(pattern)]
        except Exception as e:
            logger.error(f"Cache keys failed for pattern {pattern}: {str(e)}")
            return []

    async def flush(self) -> bool:
        """پاک کردن تمام کش"""
        await self._ensure_connection()
        if not self.redis:
            return False
            
        try:
            return await self.redis.flushdb()
        except Exception as e:
            logger.error(f"Cache flush failed: {str(e)}")
            return False

    async def exists(self, key: str) -> bool:
        """بررسی وجود کلید در کش"""
        await self._ensure_connection()
        if not self.redis:
            return False
            
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists failed for key {key}: {str(e)}")
            return False

    async def ttl(self, key: str) -> int:
        """دریافت زمان باقی مانده تا انقضا (ثانیه)"""
        await self._ensure_connection()
        if not self.redis:
            return -2
            
        try:
            return await self.redis.ttl(key)
        except Exception as e:
            logger.error(f"Cache ttl failed for key {key}: {str(e)}")
            return -2

    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """افزایش مقدار یک کلید عددی"""
        await self._ensure_connection()
        if not self.redis:
            return None
            
        try:
            return await self.redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"Cache increment failed for key {key}: {str(e)}")
            return None

    async def hset(self, key: str, field: str, value: Any) -> bool:
        """ذخیره در هش"""
        await self._ensure_connection()
        if not self.redis:
            return False
            
        try:
            return await self.redis.hset(key, field, pickle.dumps(value)) > 0
        except Exception as e:
            logger.error(f"Cache hset failed for key {key}.{field}: {str(e)}")
            return False

    async def hget(self, key: str, field: str) -> Any:
        """دریافت از هش"""
        await self._ensure_connection()
        if not self.redis:
            return None
            
        try:
            data = await self.redis.hget(key, field)
            return pickle.loads(data) if data else None
        except Exception as e:
            logger.error(f"Cache hget failed for key {key}.{field}: {str(e)}")
            return None

    async def hgetall(self, key: str) -> Dict[str, Any]:
        """دریافت تمام فیلدهای یک هش"""
        await self._ensure_connection()
        if not self.redis:
            return {}
            
        try:
            data = await self.redis.hgetall(key)
            return {k.decode('utf-8'): pickle.loads(v) for k, v in data.items()}
        except Exception as e:
            logger.error(f"Cache hgetall failed for key {key}: {str(e)}")
            return {}

    def cache(
        self, 
        ttl: int = 600, 
        key_prefix: str = None,
        ignore_args: bool = False,
        ignore_kwargs: bool = False,
        exclude_args: List[str] = None,
        exclude_kwargs: List[str] = None
    ):
        """دکوراتور کش برای توابع با قابلیت‌های پیشرفته"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                if not self.redis:
                    return await func(*args, **kwargs)
                
                cache_key = self._generate_key(
                    func, 
                    key_prefix, 
                    *args, 
                    **kwargs,
                    ignore_args=ignore_args,
                    ignore_kwargs=ignore_kwargs,
                    exclude_args=exclude_args or [],
                    exclude_kwargs=exclude_kwargs or []
                )
                
                cached = await self.get(cache_key)
                if cached is not None:
                    return cached
                
                result = await func(*args, **kwargs)
                await self.set(cache_key, result, ttl)
                return result
            return wrapper
        return decorator

    def _generate_key(
        self, 
        func: Callable, 
        prefix: str, 
        *args, 
        **kwargs
    ) -> str:
        """تولید کلید کش یکتا با قابلیت‌های پیشرفته"""
        ignore_args = kwargs.pop('ignore_args', False)
        ignore_kwargs = kwargs.pop('ignore_kwargs', False)
        exclude_args = kwargs.pop('exclude_args', [])
        exclude_kwargs = kwargs.pop('exclude_kwargs', [])
        
        key_parts = [prefix or func.__module__, func.__name__]
        
        if not ignore_args:
            filtered_args = []
            if inspect.ismethod(func) or inspect.isfunction(func):
                params = inspect.signature(func).parameters
                for i, arg in enumerate(args):
                    param_name = list(params.keys())[i]
                    if param_name not in exclude_args:
                        filtered_args.append(arg)
            key_parts.append(hashlib.md5(pickle.dumps(filtered_args)).hexdigest())
        
        if not ignore_kwargs:
            filtered_kwargs = {k: v for k, v in kwargs.items() if k not in exclude_kwargs}
            key_parts.append(hashlib.md5(pickle.dumps(filtered_kwargs)).hexdigest())
        
        return ":".join(key_parts)

    async def close(self):
        """بستن اتصال Redis"""
        if self.redis:
            await self.redis.close()
            self.redis = None

# نمونه Singleton از Cache
cache = CacheManager()

async def shutdown_cache():
    """تابع برای بستن اتصال کش هنگام خاتمه برنامه"""
    await cache.close()
