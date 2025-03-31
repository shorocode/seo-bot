from typing import List, Dict, Optional
import aiohttp
from pydantic import BaseModel
from config import settings
from services.database import db
import logging

logger = logging.getLogger(__name__)

class Notification(BaseModel):
    """مدل داده‌های نوتیفیکیشن"""
    user_id: int
    message: str
    level: str = "info"  # info, warning, critical
    is_read: bool = False

class NotificationManager:
    """سیستم ارسال و مدیریت نوتیفیکیشن‌ها"""
    
    def __init__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))

    async def send(
        self,
        user_id: int,
        message: str,
        level: str = "info",
        channels: List[str] = ["telegram"]
    ) -> bool:
        """ارسال نوتیفیکیشن به کاربر"""
        try:
            notification = Notification(
                user_id=user_id,
                message=message,
                level=level
            )
            
            # ذخیره در دیتابیس
            async with db.session() as session:
                await session.execute(
                    "INSERT INTO notifications (user_id, message, level) "
                    "VALUES (:user_id, :message, :level)",
                    notification.dict()
                )
            
            # ارسال به کانال‌های مختلف
            if "telegram" in channels:
                await self._send_telegram(user_id, message)
                
            return True
        except Exception as e:
            logger.error(f"Notification failed: {str(e)}")
            return False

    async def _send_telegram(self, user_id: int, message: str) -> bool:
        """ارسال از طریق تلگرام"""
        # پیاده‌سازی ارسال واقعی
        return True

# نمونه Singleton
notification_manager = NotificationManager()
