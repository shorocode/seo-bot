from typing import Dict, Optional, List
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from config import settings
from utils.error_handling import APILimitExceeded
import logging

logger = logging.getLogger(__name__)

class SEOToolsAPI:
    """مدیریت یکپارچه APIهای سئو"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.headers = {
            "User-Agent": "SEO-Bot/1.0",
            "Accept": "application/json"
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def fetch_serp_data(
        self,
        keyword: str,
        country: str = "ir",
        language: str = "fa"
    ) -> Optional[Dict]:
        """دریافت داده‌های SERP"""
        try:
            response = await self.client.get(
                f"{settings.SERP_API_ENDPOINT}/search",
                params={
                    "q": keyword,
                    "gl": country,
                    "hl": language
                },
                headers={
                    **self.headers,
                    "Authorization": f"Bearer {settings.SERP_API_KEY}"
                }
            )
            
            if response.status_code == 429:
                raise APILimitExceeded()
                
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"SERP API error: {str(e)}")
            raise

    @retry(stop=stop_after_attempt(2))
    async def check_backlinks(
        self,
        domain: str
    ) -> Optional[List[Dict]]:
        """بررسی بک‌لینک‌های یک دامنه"""
        try:
            response = await self.client.post(
                f"{settings.BACKLINK_API_ENDPOINT}/check",
                json={"domain": domain},
                headers={
                    **self.headers,
                    "X-API-KEY": settings.BACKLINK_API_KEY
                }
            )
            return response.json().get("backlinks", [])
        except Exception as e:
            logger.error(f"Backlink API error: {str(e)}")
            return None

# نمونه Singleton
seo_api = SEOToolsAPI()
