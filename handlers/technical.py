from telegram import Update
from telegram.ext import CallbackContext
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import urllib.parse
import json
import socket
import ssl
from typing import Dict, Optional, List
from urllib.parse import urlparse
from datetime import datetime

from config import settings
from services.database import save_result
from utils.decorators import log_activity
from utils.helpers import is_valid_url, truncate_text
from utils.logger import logger

# تنظیمات
REQUEST_TIMEOUT = 10
MAX_REDIRECTS = 3
RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[408, 429, 500, 502, 503, 504]
)

IMPORTANT_HEADERS = [
    'Server', 'Content-Type', 'Cache-Control',
    'Last-Modified', 'Content-Encoding',
    'X-Powered-By', 'X-Frame-Options',
    'Content-Security-Policy', 'Strict-Transport-Security'
]

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

def create_http_session():
    """ایجاد یک session با قابلیت retry و timeout"""
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=RETRY_STRATEGY)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def get_ssl_details(url: str) -> Dict:
    """بررسی جزئیات SSL و گواهی سایت"""
    result = {
        'has_ssl': False,
        'valid': False,
        'expires': None,
        'issued_to': None
    }
    
    try:
        hostname = urlparse(url).hostname
        if not hostname:
            return result
            
        context = ssl.create_default_context()
        with socket.create_connection((hostname, 443)) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                result['has_ssl'] = True
                result['valid'] = True
                
                # استخراج اطلاعات گواهی
                if 'notAfter' in cert:
                    expire_date = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    result['expires'] = expire_date.strftime('%Y-%m-%d')
                
                if 'subject' in cert:
                    subject = dict(x[0] for x in cert['subject'])
                    result['issued_to'] = subject.get('commonName', hostname)
    
    except Exception as e:
        logger.warning(f"SSL check failed for {url}: {str(e)}")
    
    return result

def get_http_headers(url: str) -> Dict:
    """دریافت هدرهای HTTP با مدیریت خطا و redirect"""
    try:
        session = create_http_session()
        response = session.head(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; SiteAnalyzerBot/1.0)'}
        )
        return dict(response.headers)
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request failed for {url}: {str(e)}")
        return {}

def generate_security_suggestions(headers: Dict) -> List[str]:
    """تولید پیشنهادات امنیتی بر اساس هدرها"""
    suggestions = []
    
    # بررسی HSTS
    if 'strict-transport-security' not in headers:
        suggestions.append("فعالسازی HSTS برای افزایش امنیت انتقال داده")
    
    # بررسی CSP
    if 'content-security-policy' not in headers:
        suggestions.append("اضافه کردن Content-Security-Policy برای جلوگیری از XSS")
    
    # بررسی X-Frame-Options
    if 'x-frame-options' not in headers:
        suggestions.append("اضافه کردن X-Frame-Options برای جلوگیری از Clickjacking")
    
    return suggestions

def generate_performance_suggestions(headers: Dict) -> List[str]:
    """تولید پیشنهادات عملکردی بر اساس هدرها"""
    suggestions = []
    
    # بررسی فشرده‌سازی
    if 'gzip' not in headers.get('content-encoding', '').lower():
        suggestions.append("فعالسازی فشرده‌سازی Gzip برای کاهش حجم داده")
    
    # بررسی کش
    cache_control = headers.get('cache-control', '').lower()
    if 'no-cache' in cache_control or 'no-store' in cache_control:
        suggestions.append("بهینه‌سازی تنظیمات کش برای منابع استاتیک")
    
    return suggestions

@log_activity
def headers_check_handler(update: Update, context: CallbackContext, url: str) -> str:
    """بررسی کامل هدرهای HTTP سایت"""
    if not is_valid_url(url):
        return "⚠️ آدرس سایت نامعتبر است. لطفا یک URL کامل وارد کنید (مثال: https://example.com)"
    
    try:
        # دریافت هدرها و اطلاعات SSL
        headers = get_http_headers(url)
        ssl_info = get_ssl_details(url)
        
        if not headers:
            return "⚠️ خطایی در دریافت هدرها رخ داد. لطفا آدرس را بررسی کنید."
        
        # فیلتر هدرهای مهم
        filtered_headers = {
            h: headers.get(h, 'وجود ندارد') 
            for h in IMPORTANT_HEADERS
        }
        
        # ساخت گزارش
        report = [
            f"🔍 نتایج بررسی هدرهای {url}",
            f"🔒 وضعیت SSL: {'✅ فعال' if ssl_info['has_ssl'] else '❌ غیرفعال'}",
            f"📅 تاریخ انقضا: {ssl_info['expires'] or 'نامشخص'}",
            f"🌍 صادر شده برای: {ssl_info['issued_to'] or 'نامشخص'}",
            "\n📌 هدرهای مهم:"
        ]
        
        for key, value in filtered_headers.items():
            report.append(f"- {key}: {truncate_text(str(value), 50)}")
        
        # تولید پیشنهادات
        security_suggestions = generate_security_suggestions(headers)
        performance_suggestions = generate_performance_suggestions(headers)
        
        if security_suggestions:
            report.extend(["\n🛡 پیشنهادات امنیتی:", *security_suggestions])
        
        if performance_suggestions:
            report.extend(["\n⚡ پیشنهادات عملکردی:", *performance_suggestions])
        
        # ذخیره نتیجه و بازگشت گزارش
        result = "\n".join(report)
        save_result(update.effective_user.id, 'headers_check', url, result)
        return result
        
    except Exception as e:
        logger.error(f"Error in headers check: {str(e)}", exc_info=True)
        return "⚠️ خطایی در پردازش درخواست رخ داد. لطفا بعدا تلاش کنید."
