import os
import json
from pathlib import Path
from typing import List, Dict, Any
from pydantic import BaseSettings, validator, root_validator

class Settings(BaseSettings):
    """تنظیمات اصلی با اعتبارسنجی پیشرفته"""
    
    # تنظیمات تلگرام
    TELEGRAM_TOKEN: str
    ADMINS: List[int] = []
    WORKERS: int = 4
    
    # تنظیمات سرور
    WEBHOOK_MODE: bool = False
    WEBHOOK_URL: str = ""
    PORT: int = 8443
    SSL_CERT_PATH: str = None
    SSL_KEY_PATH: str = None
    
    # تنظیمات دیتابیس
    DATABASE_URL: str = "sqlite:///db.sqlite3"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 5
    
    # تنظیمات APIها
    OPENAI_API_KEY: str = None
    GOOGLE_API_KEY: str = None
    MOZ_API_KEY: str = None
    
    # اعتبارسنجی‌های سفارشی
    @validator('ADMINS', pre=True)
    def parse_admins(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(',') if x.strip()]
        return v
        
    @root_validator
    def validate_webhook(cls, values):
        if values.get('WEBHOOK_MODE'):
            if not values.get('WEBHOOK_URL'):
                raise ValueError("WEBHOOK_URL is required in webhook mode")
        return values

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False

# نمونه Singleton از تنظیمات
settings = Settings()

# بارگذاری تنظیمات اضافی از فایل JSON
_config_path = Path('config.json')
if _config_path.exists():
    with open(_config_path, 'r', encoding='utf-8') as f:
        custom_config = json.load(f)
    for key, value in custom_config.items():
        setattr(settings, key, value)
