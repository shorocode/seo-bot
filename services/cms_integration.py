from typing import Dict, Optional, List
import httpx
from pydantic import BaseModel
from config import settings
from utils.error_handling import SEOBotError
import logging

logger = logging.getLogger(__name__)

class CMSAuth(BaseModel):
    """مدل اعتبارسنجی CMS"""
    api_key: str
    endpoint: str
    extra_headers: Dict[str, str] = {}

class CMSClient:
    """کلاینت یکپارچه برای CMSهای مختلف"""
    
    def __init__(self, cms_type: str):
        self.cms_type = cms_type
        self.http = httpx.AsyncClient(timeout=30.0)
        self.auth = self._get_auth_config()

    def _get_auth_config(self) -> CMSAuth:
        """دریافت تنظیمات احراز هویت"""
        config = settings.CMS_INTEGRATIONS.get(self.cms_type)
        if not config:
            raise SEOBotError(f"Configuration missing for {self.cms_type}")
        return CMSAuth(**config)

    async def update_seo_meta(self, content_id: str, meta_data: Dict) -> bool:
        """به‌روزرسانی متا تگ‌های سئو"""
        try:
            headers = {
                "Authorization": f"Bearer {self.auth.api_key}",
                **self.auth.extra_headers
            }
            
            response = await self.http.post(
                f"{self.auth.endpoint}/seo/update",
                json={"id": content_id, "meta": meta_data},
                headers=headers
            )
            
            if response.status_code != 200:
                raise SEOBotError(f"CMS API error: {response.text}")
                
            return True
        except Exception as e:
            logger.error(f"CMS update failed: {str(e)}")
            raise SEOBotError("Failed to update CMS content")

class WordPressIntegration(CMSClient):
    """پیاده‌سازی اختصاصی برای وردپرس"""
    async def get_post(self, post_id: int) -> Optional[Dict]:
        try:
            response = await self.http.get(
                f"{self.auth.endpoint}/wp-json/wp/v2/posts/{post_id}",
                headers={"Authorization": f"Bearer {self.auth.api_key}"}
            )
            return response.json()
        except Exception as e:
            logger.error(f"WordPress get_post failed: {str(e)}")
            return None
