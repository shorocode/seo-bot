"""
پکیج تنظیمات - این پکیج شامل تمام تنظیمات و پیکربندی‌های سیستم می‌شود
"""

from .settings import Settings
from .keyboards import (
    get_main_menu_keyboard,
    get_category_keyboard,
    get_tool_keyboard,
    get_admin_keyboard,
    get_back_button
)

# ایجاد یک نمونه از تنظیمات که در تمام سیستم قابل دسترسی است
settings = Settings()

__all__ = [
    'settings',
    'get_main_menu_keyboard',
    'get_category_keyboard',
    'get_tool_keyboard',
    'get_admin_keyboard',
    'get_back_button'
]
