from typing import Dict, Optional, List
import openai
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from config import settings
from utils.error_handling import APILimitExceeded
import logging

logger = logging.getLogger(__name__)

class AIService:
    """سرویس هوش مصنوعی با قابلیت Fallback و Retry"""

    def __init__(self):
        self.providers = {
            'openai': self._call_openai,
            'anthropic': self._call_anthropic,
            'google': self._call_google_ai
        }
        self.setup_clients()

    def setup_clients(self):
        """تنظیم کلاینت‌های API"""
        self.openai_client = openai.AsyncClient(
            api_key=settings.OPENAI_API_KEY,
            timeout=httpx.Timeout(30.0)
        )
        self.http_client = httpx.AsyncClient(timeout=30.0)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_error_callback=lambda _: None
    )
    async def analyze_content(self, text: str, language: str = "fa") -> Dict:
        """تحلیل محتوا با سیستم Fallback خودکار"""
        for provider in ['openai', 'anthropic', 'google']:
            try:
                result = await self.providers[provider](text, language)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"AI provider {provider} failed: {str(e)}")
                continue
        
        raise APILimitExceeded()

    async def _call_openai(self, text: str, language: str) -> Optional[Dict]:
        """تماس با OpenAI API"""
        response = await self.openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": self._get_system_prompt(language)},
                {"role": "user", "content": text}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        return self._parse_openai_response(response.choices[0].message.content)

    def _get_system_prompt(self, language: str) -> str:
        """تهیه پرمپت براساس زبان"""
        prompts = {
            "fa": "شما یک متخصص سئو هستید. تحلیل خود را به زبان فارسی ارائه دهید.",
            "en": "You are an SEO expert. Provide analysis in English."
        }
        return prompts.get(language, prompts["en"])

    def _parse_openai_response(self, text: str) -> Dict:
        """پارس کردن پاسخ OpenAI"""
        # پیاده‌سازی منطق تجزیه پاسخ
        return {"analysis": text}

# نمونه Singleton از سرویس
ai_service = AIService()
