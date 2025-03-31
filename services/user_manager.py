from typing import Optional, Dict, List
from datetime import datetime, timedelta
from pydantic import BaseModel, validator
from config import settings
from services.database import db
from services.cache import cache
import logging

logger = logging.getLogger(__name__)

class UserData(BaseModel):
    """مدل داده‌های کاربر با اعتبارسنجی"""
    user_id: int
    username: Optional[str]
    first_name: str
    last_name: Optional[str]
    language_code: str = "fa"
    is_premium: bool = False
    last_activity: datetime = datetime.utcnow()

    @validator('language_code')
    def validate_language(cls, v):
        return v if v in ['fa', 'en'] else 'fa'

class UserManager:
    """مدیریت پیشرفته کاربران با قابلیت کشینگ"""
    
    def __init__(self):
        self.cache_ttl = timedelta(hours=1)

    async def get_user(self, user_id: int) -> Optional[UserData]:
        """دریافت اطلاعات کاربر با کشینگ"""
        cache_key = f"user:{user_id}"
        cached = await cache.get(cache_key)
        if cached:
            return UserData(**cached)
            
        async with db.session() as session:
            user = await session.execute(
                "SELECT * FROM users WHERE id = :user_id",
                {"user_id": user_id}
            )
            user_data = user.fetchone()
            
            if not user_data:
                return None
                
            result = UserData(**dict(user_data))
            await cache.set(cache_key, result.dict(), self.cache_ttl)
            return result

    async def update_user(self, user_data: UserData) -> bool:
        """به‌روزرسانی اطلاعات کاربر"""
        async with db.session() as session:
            try:
                await session.execute(
                    """
                    INSERT INTO users (id, username, first_name, last_name, language_code, is_premium, last_activity)
                    VALUES (:user_id, :username, :first_name, :last_name, :language_code, :is_premium, :last_activity)
                    ON CONFLICT (id) DO UPDATE SET
                        username = EXCLUDED.username,
                        last_activity = EXCLUDED.last_activity
                    """,
                    user_data.dict()
                )
                await cache.delete(f"user:{user_data.user_id}")
                return True
            except Exception as e:
                logger.error(f"Error updating user: {e}")
                return False

# نمونه Singleton
user_manager = UserManager()
