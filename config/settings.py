import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
from pathlib import Path

class Settings:
    """
    کلاس تنظیمات اصلی سیستم - مقادیر از محیط و فایل‌های پیکربندی بارگذاری می‌شوند
    """
    
    def __init__(self):
        # بارگذاری متغیرهای محیطی
        load_dotenv()
        
        # شناسه ادمین‌ها
        self.ADMINS: List[int] = self._parse_admins(os.getenv("ADMINS", ""))
        
        # تنظیمات تلگرام
        self.TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
        self.WORKERS: int = int(os.getenv("WORKERS", 4))
        self.WEBHOOK_MODE: bool = os.getenv("WEBHOOK_MODE", "False").lower() == "true"
        self.WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
        self.PORT: int = int(os.getenv("PORT", 8443))
        
        # تنظیمات دیتابیس
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///db.sqlite3")
        
        # تنظیمات ردیس
        self.REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
        self.REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
        self.REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
        self.REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
        
        # تنظیمات API هوش مصنوعی
        self.OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        self.GOOGLE_AI_KEY: str = os.getenv("GOOGLE_AI_KEY", "")
        self.ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
        self.AI_REQUEST_TIMEOUT: int = int(os.getenv("AI_REQUEST_TIMEOUT", 30))
        
        # سایر تنظیمات
        self.DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        self.MAINTENANCE_MODE: bool = os.getenv("MAINTENANCE_MODE", "False").lower() == "true"
        
        # بارگذاری تنظیمات از فایل JSON اگر وجود دارد
        self._load_from_json()
        
        # اعتبارسنجی تنظیمات ضروری
        self._validate_settings()
    
    def _parse_admins(self, admins_str: str) -> List[int]:
        """تبدیل رشته ادمین‌ها به لیست"""
        try:
            return [int(admin_id.strip()) for admin_id in admins_str.split(",") if admin_id.strip()]
        except (ValueError, AttributeError):
            return []
    
    def _load_from_json(self):
        """بارگذاری تنظیمات اضافی از فایل JSON"""
        config_path = Path("config.json")
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                
                for key, value in config_data.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
            except Exception as e:
                print(f"خطا در بارگذاری فایل پیکربندی: {str(e)}")
    
    def _validate_settings(self):
        """اعتبارسنجی تنظیمات ضروری"""
        errors = []
        
        if not self.TELEGRAM_TOKEN:
            errors.append("توکن تلگرام (TELEGRAM_TOKEN) تنظیم نشده است")
        
        if self.WEBHOOK_MODE and not self.WEBHOOK_URL:
            errors.append("در حالت Webhook، آدرس وب‌هوک (WEBHOOK_URL) باید تنظیم شود")
        
        if not self.ADMINS:
            errors.append("حداقل یک ادمین باید تعریف شود (ADMINS)")
        
        if errors:
            raise ValueError("\n".join(errors))
    
    def get_ai_providers(self) -> List[str]:
        """دریافت لیست ارائه‌دهندگان هوش مصنوعی فعال"""
        providers = []
        
        if self.OPENAI_API_KEY:
            providers.append("openai")
        
        if self.GOOGLE_AI_KEY:
            providers.append("google_ai")
        
        if self.ANTHROPIC_API_KEY:
            providers.append("anthropic")
        
        return providers
    
    @property
    def DEFAULT_AI_PROVIDER(self) -> str:
        """دریافت ارائه‌دهنده پیش‌فرض هوش مصنوعی"""
        providers = self.get_ai_providers()
        return providers[0] if providers else ""
