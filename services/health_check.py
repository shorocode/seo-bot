import asyncio
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime
import httpx
from prometheus_client import start_http_server, Gauge
import logging

logger = logging.getLogger(__name__)

@dataclass
class HealthStatus:
    service: str
    status: bool
    response_time: float
    last_checked: datetime

class HealthMonitor:
    """سیستم نظارت حرفه‌ای بر سلامت سرویس‌ها"""
    
    def __init__(self):
        self.metrics = {
            'api_health': Gauge('api_health', 'Status of external APIs', ['service']),
            'response_time': Gauge('response_time_ms', 'API response time', ['service'])
        }
        start_http_server(8000)  # برای اکسپورت متریک‌های Prometheus

    async def check_services(self) -> List[HealthStatus]:
        """بررسی سلامت تمام سرویس‌های حیاتی"""
        services = [
            ("Database", self._check_database),
            ("Redis", self._check_redis),
            ("Telegram API", self._check_telegram),
            ("AI Service", self._check_ai_service)
        ]
        
        results = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            for name, checker in services:
                try:
                    start = datetime.now()
                    status = await checker(client)
                    response_time = (datetime.now() - start).total_seconds() * 1000
                    
                    self.metrics['api_health'].labels(name).set(int(status))
                    self.metrics['response_time'].labels(name).set(response_time)
                    
                    results.append(HealthStatus(
                        service=name,
                        status=status,
                        response_time=response_time,
                        last_checked=datetime.now()
                    ))
                except Exception as e:
                    logger.error(f"Health check failed for {name}: {str(e)}")
                    results.append(HealthStatus(name, False, 0, datetime.now()))
        
        return results

    async def _check_database(self, client: httpx.AsyncClient) -> bool:
        """بررسی اتصال به دیتابیس"""
        # پیاده‌سازی واقعی با توجه به سیستم دیتابیس شما
        return True

    async def start_periodic_checks(self, interval: int = 300):
        """شروع بررسی‌های دوره‌ای"""
        while True:
            await self.check_services()
            await asyncio.sleep(interval)

# نمونه Singleton
health_monitor = HealthMonitor()
