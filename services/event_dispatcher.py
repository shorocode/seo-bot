from typing import Dict, List, Callable, Any
from pydantic import BaseModel
import asyncio
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class EventType(str, Enum):
    """انواع رویدادهای سیستم"""
    USER_ACTIVITY = "user_activity"
    ANALYSIS_COMPLETE = "analysis_complete"
    API_CALL = "api_call"

class Event(BaseModel):
    """مدل پایه رویداد"""
    event_type: EventType
    data: Dict[str, Any]
    timestamp: float

class EventDispatcher:
    """سیستم انتشار رویدادهای پیشرفته"""
    
    def __init__(self):
        self.subscribers: Dict[EventType, List[Callable]] = {}
        self.queue = asyncio.Queue()
        self._running = True
        asyncio.create_task(self._process_events())

    def subscribe(self, event_type: EventType, callback: Callable):
        """ثبت مشترک برای رویدادها"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    async def publish(self, event: Event):
        """انتشار رویداد جدید"""
        await self.queue.put(event)

    async def _process_events(self):
        """پردازش ناهمزمان رویدادها"""
        while self._running:
            try:
                event = await self.queue.get()
                if event.event_type in self.subscribers:
                    for callback in self.subscribers[event.event_type]:
                        try:
                            await callback(event.data)
                        except Exception as e:
                            logger.error(f"Event callback failed: {str(e)}")
                self.queue.task_done()
            except Exception as e:
                logger.error(f"Event processing error: {str(e)}")

    async def shutdown(self):
        """خاموش کردن سیستم به صورت گراسیوس"""
        self._running = False
        await self.queue.join()

# نمونه Singleton
event_dispatcher = EventDispatcher()
