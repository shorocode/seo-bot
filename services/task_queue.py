import asyncio
from typing import Callable, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
from config import settings
import logging

logger = logging.getLogger(__name__)

class AsyncTaskQueue:
    """صف وظایف ناهمزمان با مدیریت پیشرفته"""
    
    def __init__(self, max_workers: int = 5):
        self.queue = Queue()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.loop = asyncio.get_event_loop()
        self._running = True
        self._start_consumer()

    def _start_consumer(self):
        """شروع مصرف‌کننده وظایف"""
        def consumer():
            while self._running:
                try:
                    task = self.queue.get(timeout=1)
                    func, args, kwargs, future = task
                    try:
                        result = func(*args, **kwargs)
                        future.set_result(result)
                    except Exception as e:
                        future.set_exception(e)
                except Empty:
                    continue
                    
        for _ in range(settings.TASK_QUEUE_WORKERS):
            self.executor.submit(consumer)

    async def add_task(self, func: Callable, *args, **kwargs) -> Any:
        """اضافه کردن وظیفه جدید به صف"""
        if not self._running:
            raise RuntimeError("Queue is not running")
            
        future = self.loop.create_future()
        self.queue.put((func, args, kwargs, future))
        return await future

    def shutdown(self):
        """خاموش کردن صف به صورت گراسیوس"""
        self._running = False
        self.executor.shutdown(wait=True)

# نمونه جهانی از صف وظایف
task_queue = AsyncTaskQueue(max_workers=settings.TASK_QUEUE_WORKERS)
