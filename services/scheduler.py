import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Callable, Dict
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class TaskScheduler:
    """سیستم زمان‌بندی پیشرفته برای وظایف دوره‌ای"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.jobs: Dict[str, str] = {}

    def add_job(
        self,
        func: Callable,
        job_id: str,
        cron_expr: str,
        args: tuple = ()
    ) -> bool:
        """اضافه کردن وظیفه زمان‌بندی شده"""
        try:
            trigger = CronTrigger.from_crontab(cron_expr)
            self.scheduler.add_job(
                func,
                trigger=trigger,
                id=job_id,
                args=args,
                next_run_time=datetime.now()
            )
            self.jobs[job_id] = cron_expr
            return True
        except Exception as e:
            logger.error(f"Failed to add job {job_id}: {str(e)}")
            return False

    async def start(self):
        """شروع زمان‌بند"""
        self.scheduler.start()
        logger.info("Task scheduler started with jobs: %s", self.jobs)

    async def shutdown(self):
        """توقف زمان‌بند"""
        self.scheduler.shutdown(wait=True)
        logger.info("Task scheduler stopped")

# نمونه Singleton
task_scheduler = TaskScheduler()
