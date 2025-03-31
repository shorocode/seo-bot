from typing import Dict, Optional, List, Any, Union, TypeVar, Generic
import httpx
from pydantic import BaseModel, validator
from config import settings
from utils.error_handling import SEOBotError
import logging
from functools import wraps
import asyncio
from datetime import timedelta
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

T = TypeVar('T')

class CMSAuth(BaseModel):
    """مدل اعتبارسنجی CMS با اعتبارسنجی پیشرفته"""
    api_key: str
    endpoint: str
    timeout: float = 30.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    extra_headers: Dict[str, str] = {}
    cache_ttl: int = 300  # زمان کش پیش‌فرض به ثانیه

    @validator('endpoint')
    def validate_endpoint(cls, v):
        """اعتبارسنجی endpoint"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Endpoint must start with http:// or https://")
        return v.rstrip('/')

class CMSResponse(BaseModel):
    """مدل استاندارد برای پاسخ‌های CMS"""
    success: bool
    data: Optional[Union[Dict, List]]
    message: Optional[str]
    status_code: int

class CMSClient:
    """کلاینت یکپارچه و پیشرفته برای CMSهای مختلف"""
    
    def __init__(self, cms_type: str):
        self.cms_type = cms_type
        self._http_client = None
        self.auth = self._get_auth_config()
        self._setup_http_client()

    def _get_auth_config(self) -> CMSAuth:
        """دریافت تنظیمات احراز هویت با مدیریت خطا"""
        try:
            config = settings.CMS_INTEGRATIONS.get(self.cms_type)
            if not config:
                raise SEOBotError(f"Configuration missing for CMS type: {self.cms_type}")
            return CMSAuth(**config)
        except Exception as e:
            logger.error(f"Failed to load auth config for {self.cms_type}: {str(e)}")
            raise SEOBotError("CMS configuration error")

    def _setup_http_client(self):
        """تنظیم کلاینت HTTP با پیکربندی پیشرفته"""
        transport = httpx.AsyncHTTPTransport(
            retries=self.auth.retry_attempts,
            max_connections=100,
            max_keepalive_connections=20
        )
        
        self._http_client = httpx.AsyncClient(
            base_url=self.auth.endpoint,
            timeout=self.auth.timeout,
            transport=transport,
            follow_redirects=True,
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10
            )
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        """بستن اتصال HTTP"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def _get_headers(self, extra_headers: Dict[str, str] = None) -> Dict[str, str]:
        """تهیه هدرهای درخواست"""
        headers = {
            "Authorization": f"Bearer {self.auth.api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"SEOBotCMSClient/{self.cms_type}",
            **self.auth.extra_headers
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> httpx.Response:
        """ارسال درخواست با قابلیت تکرار خودکار"""
        last_exception = None
        
        for attempt in range(1, self.auth.retry_attempts + 1):
            try:
                response = await self._http_client.request(
                    method,
                    path,
                    **kwargs
                )
                if response.status_code < 500:
                    return response
                
                logger.warning(
                    f"Attempt {attempt} failed for {method} {path}. "
                    f"Status: {response.status_code}"
                )
            except (httpx.NetworkError, httpx.TimeoutException) as e:
                logger.warning(
                    f"Network error on attempt {attempt} for {method} {path}: {str(e)}"
                )
                last_exception = e
            
            if attempt < self.auth.retry_attempts:
                await asyncio.sleep(self.auth.retry_delay * attempt)
        
        if last_exception:
            raise SEOBotError(f"Request failed after {self.auth.retry_attempts} attempts: {str(last_exception)}")
        raise SEOBotError(f"Request failed with status {response.status_code}")

    async def _process_response(self, response: httpx.Response) -> CMSResponse:
        """پردازش پاسخ و تبدیل به مدل استاندارد"""
        try:
            response_data = response.json()
        except ValueError:
            response_data = None

        return CMSResponse(
            success=200 <= response.status_code < 300,
            data=response_data,
            message=None if response.is_success else response.text,
            status_code=response.status_code
        )

    async def update_seo_meta(
        self,
        content_id: str,
        meta_data: Dict[str, Any],
        **kwargs
    ) -> CMSResponse:
        """به‌روزرسانی متا تگ‌های سئو"""
        try:
            response = await self._request_with_retry(
                "POST",
                "/seo/update",
                json={"id": content_id, "meta": meta_data},
                headers=self._get_headers(kwargs.get("headers"))
            )
            return await self._process_response(response)
        except Exception as e:
            logger.error(f"CMS update failed for content {content_id}: {str(e)}", exc_info=True)
            return CMSResponse(
                success=False,
                data=None,
                message=str(e),
                status_code=500
            )

    async def get_content(
        self,
        content_id: str,
        content_type: str = "post",
        **kwargs
    ) -> CMSResponse:
        """دریافت محتوا از CMS"""
        try:
            response = await self._request_with_retry(
                "GET",
                f"/{content_type}/{content_id}",
                headers=self._get_headers(kwargs.get("headers"))
            )
            return await self._process_response(response)
        except Exception as e:
            logger.error(f"Failed to get content {content_id}: {str(e)}", exc_info=True)
            return CMSResponse(
                success=False,
                data=None,
                message=str(e),
                status_code=500
            )

class WordPressIntegration(CMSClient):
    """پیاده‌سازی اختصاصی برای وردپرس با قابلیت‌های اضافه"""
    
    async def get_post(
        self,
        post_id: Union[int, str],
        fields: List[str] = None,
        **kwargs
    ) -> CMSResponse:
        """دریافت پست از وردپرس با قابلیت انتخاب فیلدها"""
        try:
            params = {}
            if fields:
                params["_fields"] = ",".join(fields)
            
            response = await self._request_with_retry(
                "GET",
                f"/wp-json/wp/v2/posts/{post_id}",
                params=params,
                headers=self._get_headers(kwargs.get("headers"))
            )
            return await self._process_response(response)
        except Exception as e:
            logger.error(f"WordPress get_post failed for {post_id}: {str(e)}", exc_info=True)
            return CMSResponse(
                success=False,
                data=None,
                message=str(e),
                status_code=500
            )

    async def update_post(
        self,
        post_id: Union[int, str],
        update_data: Dict[str, Any],
        **kwargs
    ) -> CMSResponse:
        """به‌روزرسانی پست در وردپرس"""
        try:
            response = await self._request_with_retry(
                "POST",
                f"/wp-json/wp/v2/posts/{post_id}",
                json=update_data,
                headers=self._get_headers(kwargs.get("headers"))
            )
            return await self._process_response(response)
        except Exception as e:
            logger.error(f"WordPress update_post failed for {post_id}: {str(e)}", exc_info=True)
            return CMSResponse(
                success=False,
                data=None,
                message=str(e),
                status_code=500
            )

    async def list_posts(
        self,
        page: int = 1,
        per_page: int = 10,
        search: str = None,
        **kwargs
    ) -> CMSResponse:
        """لیست پست‌های وردپرس"""
        try:
            params = {
                "page": page,
                "per_page": per_page
            }
            if search:
                params["search"] = search
            
            response = await self._request_with_retry(
                "GET",
                "/wp-json/wp/v2/posts",
                params=params,
                headers=self._get_headers(kwargs.get("headers"))
            )
            return await self._process_response(response)
        except Exception as e:
            logger.error(f"WordPress list_posts failed: {str(e)}", exc_info=True)
            return CMSResponse(
                success=False,
                data=None,
                message=str(e),
                status_code=500
            )

# مثال استفاده:
# async with WordPressIntegration("wordpress") as wp_client:
#     response = await wp_client.get_post(123)
#     if response.success:
#         print(response.data)
