
from telegram import Update
from telegram.ext import CallbackContext
import requests
from bs4 import BeautifulSoup
import urllib.parse
import json
from typing import Dict, Optional

from config import settings
from services.database import save_result
from utils.decorators import log_activity
from utils.helpers import is_valid_url, truncate_text
from utils.logger import logger

TOOLS = [
    {
        'id': 'headers_check',
        'name': 'بررسی هدرهای سایت',
        'description': 'تحلیل هدرهای HTTP و وضعیت پاسخ سرور',
        'input_prompt': '🌐 لطفا آدرس سایت را برای بررسی هدرها ارسال کنید:'
    },
    {
        'id': 'speed_test',
        'name': 'تست سرعت بارگذاری',
        'description': 'سنجش سرعت لود صفحه و زمان پاسخ سرور',
        'input_prompt': '⏱ لطفا آدرس سایت را برای تست سرعت ارسال کنید:'
    },
    {
        'id': 'mobile_friendly',
        'name': 'سازگاری با موبایل',
        'description': 'بررسی ریسپانسیو بودن سایت در دستگاه‌های موبایل',
        'input_prompt': '📱 لطفا آدرس سایت را برای بررسی موبایل فرندلی ارسال کنید:'
    }
]

@log_activity
def headers_check_handler(update: Update, context: CallbackContext, url: str) -> str:
    """بررسی هدرهای HTTP سایت"""
    if not is_valid_url(url):
        return "⚠️ آدرس سایت نامعتبر است. لطفا یک URL کامل وارد کنید (مثال: https://example.com)"
    
    try:
        response = requests.head(url, timeout=10, allow_redirects=True)
        headers = dict(response.headers)
        
        # فیلتر کردن هدرهای مهم
        important_headers = {
            'Server': headers.get('Server', 'نامشخص'),
            'Content-Type': headers.get('Content-Type', 'نامشخص'),
            'Cache-Control': headers.get('Cache-Control', 'وجود ندارد'),
            'Last-Modified': headers.get('Last-Modified', 'وجود ندارد'),
            'Content-Encoding': headers.get('Content-Encoding', 'وجود ندارد'),
            'X-Powered-By': headers.get('X-Powered-By', 'وجود ندارد')
        }
        
        # بررسی HTTPS
        ssl_status = "✅ فعال" if url.startswith('https') else "❌ غیرفعال"
        
        # ساخت گزارش
        report = [
            f"🔍 نتایج بررسی هدرهای {url}",
            f"🛡️ SSL: {ssl_status}",
            f"🔄 کد وضعیت: {response.status_code}",
            "\n📌 هدرهای مهم:"
        ]
        
        for key, value in important_headers.items():
            report.append(f"- {key}: {value}")
            
        # پیشنهادات بهینه‌سازی
        suggestions = []
        if 'gzip' not in headers.get('Content-Encoding', ''):
            suggestions.append("فشرده‌سازی Gzip را فعال کنید")
        if 'no-cache' in headers.get('Cache-Control', ''):
            suggestions.append("تنظیمات کش را بهبود بخشید")
            
        if suggestions:
            report.extend(["\n💡 پیشنهادات:", *suggestions])
        
        result = "\n".join(report)
        save_result(update.effective_user.id, 'headers_check', url, result)
        return result
        
    except Exception as e:
        logger.error(f"Error checking headers: {str(e)}", exc_info=True)
        return "⚠️ خطایی در بررسی هدرها رخ داد. لطفا آدرس را بررسی کنید."
