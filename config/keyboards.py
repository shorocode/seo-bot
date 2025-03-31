from typing import List, Dict, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# متن‌های پیش‌فرض (می‌تواند به فایل جداگانه منتقل شود)
BUTTON_TEXTS = {
    "main_menu": {
        "content": "📝 تحلیل محتوا",
        "technical": "⚙️ تحلیل فنی",
        "backlinks": "🔗 تحلیل بک‌لینک",
        "competition": "🏆 رقابت‌سنجی",
        "advanced": "🛠️ ابزارهای پیشرفته"
    },
    "admin": {
        "stats": "📊 آمار کاربران",
        "settings": "🔧 تنظیمات سیستم",
        "maintenance": "🔄 حالت تعمیرات",
        "broadcast": "📝 اطلاع‌رسانی"
    },
    "common": {
        "back": "◀️ بازگشت",
        "retry": "🔍 تحلیل مجدد",
        "save": "📊 ذخیره نتیجه",
        "share": "📤 اشتراک‌گذاری"
    }
}

class KeyboardGenerator:
    """کلاس اصلی برای تولید کیبوردهای اینلاین"""
    
    @staticmethod
    def generate_grid_buttons(
        items: List[Dict],
        items_per_row: int = 2,
        back_button: bool = True
    ) -> InlineKeyboardMarkup:
        """
        تولید خودکار کیبورد با چیدمان گرید
        
        :param items: لیست آیتم‌ها با کلیدهای text و data
        :param items_per_row: تعداد دکمه در هر سطر
        :param back_button: آیا دکمه بازگشت اضافه شود؟
        :return: شیء InlineKeyboardMarkup
        """
        if not items or items_per_row < 1:
            raise ValueError("ورودی‌های نامعتبر برای تولید کیبورد")
            
        keyboard = []
        for i in range(0, len(items), items_per_row):
            row = [
                InlineKeyboardButton(
                    text=item["text"],
                    callback_data=item["data"]
                )
                for item in items[i:i+items_per_row]
            ]
            keyboard.append(row)
        
        if back_button:
            keyboard.append([KeyboardGenerator.get_back_button()])
            
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_back_button(text: Optional[str] = None) -> InlineKeyboardButton:
        """تولید دکمه بازگشت استاندارد"""
        return InlineKeyboardButton(
            text=text or BUTTON_TEXTS["common"]["back"],
            callback_data="back"
        )

# --- توابع اصلی (برای سازگاری با نسخه قبلی) ---

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """کیبورد منوی اصلی"""
    buttons = [
        {"text": BUTTON_TEXTS["main_menu"]["content"], "data": "content"},
        {"text": BUTTON_TEXTS["main_menu"]["technical"], "data": "technical"},
        {"text": BUTTON_TEXTS["main_menu"]["backlinks"], "data": "backlinks"},
        {"text": BUTTON_TEXTS["main_menu"]["competition"], "data": "competition"},
        {"text": BUTTON_TEXTS["main_menu"]["advanced"], "data": "advanced"}
    ]
    return KeyboardGenerator.generate_grid_buttons(buttons, items_per_row=2)

def get_category_keyboard(tools: List[Dict]) -> InlineKeyboardMarkup:
    """کیبورد ابزارهای یک دسته‌بندی"""
    if not tools:
        raise ValueError("لیست ابزارها نمی‌تواند خالی باشد")
        
    items = [{"text": tool["name"], "data": tool["id"]} for tool in tools]
    return KeyboardGenerator.generate_grid_buttons(items)

def get_tool_keyboard(tool_id: str) -> InlineKeyboardMarkup:
    """کیبورد ابزار خاص"""
    buttons = [
        {"text": BUTTON_TEXTS["common"]["retry"], "data": f"retry_{tool_id}"},
        {"text": BUTTON_TEXTS["common"]["save"], "data": f"save_{tool_id}"},
        {"text": BUTTON_TEXTS["common"]["share"], "data": f"share_{tool_id}"}
    ]
    return KeyboardGenerator.generate_grid_buttons(buttons, items_per_row=2)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """کیبورد مدیریت"""
    buttons = [
        {"text": BUTTON_TEXTS["admin"]["stats"], "data": "admin_stats"},
        {"text": BUTTON_TEXTS["admin"]["settings"], "data": "admin_settings"},
        {"text": BUTTON_TEXTS["admin"]["maintenance"], "data": "admin_maintenance"},
        {"text": BUTTON_TEXTS["admin"]["broadcast"], "data": "admin_broadcast"}
    ]
    return KeyboardGenerator.generate_grid_buttons(buttons, items_per_row=2)

def create_inline_keyboard(buttons: List[Dict], back_button: bool = True) -> InlineKeyboardMarkup:
    """کیبورد سفارشی (سازگار با نسخه قبلی)"""
    return KeyboardGenerator.generate_grid_buttons(buttons, back_button=back_button)
