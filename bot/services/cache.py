import redis
from datetime import timedelta
from functools import wraps
import pickle
import hashlib
import logging

from config import settings
from utils.logger import logger

class CacheService:
    """
    Advanced caching service with Redis backend
    Supports memoization, time-based invalidation, and cache groups
    """
    
    def __init__(self):
        self.redis = None
        self._connect()
        
    def _connect(self):
        """Initialize Redis connection"""
        try:
            self.redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=False
            )
            # Test connection
            self.redis.ping()
        except Exception as e:
            logger.error(f"Redis connection failed: {str(e)}")
            self.redis = None
    
    def memoize(self, ttl: int = 300, key_prefix: str = None):
        """
        Decorator for function result caching
        Args:
            ttl: Time to live in seconds
            key_prefix: Custom cache key prefix
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.redis:
                    return func(*args, **kwargs)
                    
                # Generate cache key
                cache_key = self._generate_key(func, args, kwargs, key_prefix)
                
                # Try to get cached result
                try:
                    cached = self.redis.get(cache_key)
                    if cached is not None:
                        return pickle.loads(cached)
                except Exception as e:
                    logger.warning(f"Cache read failed: {str(e)}")
                
                # Call function if not in cache
                result = func(*args, **kwargs)
                
                # Store result in cache
                try:
                    self.redis.setex(
                        cache_key,
                        timedelta(seconds=ttl),
                        pickle.dumps(result)
                except Exception as e:
                    logger.warning(f"Cache write failed: {str(e)}")
                
                return result
            return wrapper
        return decorator
    
    def invalidate(self, *keys):
        """Invalidate cache keys"""
        if not self.redis:
            return
            
        try:
            self.redis.delete(*keys)
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {str(e)}")
    
    def invalidate_group(self, group_name: str):
        """Invalidate all keys in a group"""
        if not self.redis:
            return
            
        try:
            keys = self.redis.smembers(f"cache_group:{group_name}")
            if keys:
                self.redis.delete(*keys)
                self.redis.delete(f"cache_group:{group_name}")
        except Exception as e:
            logger.warning(f"Group cache invalidation failed: {str(e)}")
    
    def _generate_key(self, func, args, kwargs, key_prefix=None):
        """Generate consistent cache key"""
        prefix = key_prefix or f"{func.__module__}:{func.__name__}"
        
        # Create hash of arguments
        arg_hash = hashlib.md5(
            pickle.dumps((args, sorted(kwargs.items())))
        ).hexdigest()
        
        return f"cache:{prefix}:{arg_hash}"
    
    def add_to_group(self, key: str, group_name: str):
        """Add key to a cache group for batch invalidation"""
        if not self.redis:
            return
            
        try:
            self.redis.sadd(f"cache_group:{group_name}", key)
        except Exception as e:
            logger.warning(f"Failed to add to cache group: {str(e)}")

# Singleton cache instance with memoization support
cache = CacheService()
