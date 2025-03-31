import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseSettings, validator, root_validator, HttpUrl, Field

class Settings(BaseSettings):
    """تنظیمات اصلی برنامه با اعتبارسنجی پیشرفته
    
    تنظیمات از سه منبع بارگذاری می‌شوند:
    1. متغیرهای محیطی (اولویت اول)
    2. فایل `.env` (دوم)
    3. فایل `config.json` (سوم)
    """

    # --- تنظیمات اصلی تلگرام ---
    TELEGRAM_TOKEN: str = Field(..., min_length=30)
    ADMINS: List[int] = []
    WORKERS: int = Field(4, ge=1, le=20)
    
    # --- تنظیمات سرور ---
    WEBHOOK_MODE: bool = False
    WEBHOOK_URL: Optional[HttpUrl] = None
    PORT: int = Field(8443, ge=1024, le=65535)
    SSL_CERT_PATH: Optional[str] = None
    SSL_KEY_PATH: Optional[str] = None
    
    # --- تنظیمات دیتابیس ---
    DATABASE_URL: str = "sqlite:///db.sqlite3"
    DB_POOL_SIZE: int = Field(10, ge=1)
    DB_MAX_OVERFLOW: int = Field(5, ge=0)
    
    # --- تنظیمات APIهای خارجی ---
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    MOZ_API_KEY: Optional[str] = None
    
    # --- تنظیمات امنیتی ---
    REQUEST_TIMEOUT: int = Field(30, ge=10)  # ثانیه
    RATE_LIMIT: int = Field(20, ge=1)       # درخواست در دقیقه

    # ============ اعتبارسنجی‌ها ============
    @validator('TELEGRAM_TOKEN')
    def validate_bot_token(cls, v):
        if not re.match(r'^\d+:[\w-]+$', v):
            raise ValueError('قالب توکن تلگرام نامعتبر است!')
        return v

    @validator('ADMINS', pre=True)
    def parse_admins(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(',') if x.strip()]
        return v

    @root_validator
    def validate_webhook(cls, values):
        if values.get('WEBHOOK_MODE'):
            if not values.get('WEBHOOK_URL'):
                raise ValueError("WEBHOOK_URL در حالت وب‌هوک الزامی است")
            
            # بررسی وجود فایل‌های SSL
            if values.get('SSL_CERT_PATH') and not Path(values['SSL_CERT_PATH']).exists():
                raise FileNotFoundError(f"فایل SSL CERT یافت نشد: {values['SSL_CERT_PATH']}")
            
            if values.get('SSL_KEY_PATH') and not Path(values['SSL_KEY_PATH']).exists():
                raise FileNotFoundError(f"فایل SSL KEY یافت نشد: {values['SSL_KEY_PATH']}")
        return values

    @validator('DATABASE_URL')
    def validate_db_url(cls, v):
        if not re.match(r'^(sqlite|postgresql|mysql)://', v):
            raise ValueError('فرمت DATABASE_URL نامعتبر است')
        return v

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False
        extra = 'ignore'  # جلوگیری از خطا در صورت وجود فیلدهای اضافی

# ============ بارگذاری تنظیمات ============
def load_settings() -> Settings:
    """بارگذاری تنظیمات با مدیریت خطاهای احتمالی"""
    settings = Settings()
    
    # بارگذاری تنظیمات اضافی از config.json (اختیاری)
    config_path = Path('config.json')
    try:
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                custom_config = json.load(f)
            
            for key, value in custom_config.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
                else:
                    logging.warning(f"کلید ناشناخته در config.json: {key}")
    except json.JSONDecodeError as e:
        logging.error(f"خطا در خواندن فایل config.json: {e}")
    except Exception as e:
        logging.error(f"خطای ناشناخته در بارگذاری تنظیمات: {e}")

    # هشدار برای کلیدهای API اختیاری
    if not settings.OPENAI_API_KEY:
        logging.warning("OPENAI_API_KEY تنظیم نشده است!")
    
    return settings

# نمونه Singleton از تنظیمات
settings = load_settings()
