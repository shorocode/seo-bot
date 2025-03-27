from typing import List, Dict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    ایجاد کیبورد منوی اصلی با دکمه‌های شیشه‌ای
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="📝 تحلیل محتوا",
                callback_data="content"
            ),
            InlineKeyboardButton(
                text="⚙️ تحلیل فنی",
                callback_data="technical"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔗 تحلیل بک‌لینک",
                callback_data="backlinks"
            ),
            InlineKeyboardButton(
                text="🏆 رقابت‌سنجی",
                callback_data="competition"
            )
        ],
        [
            InlineKeyboardButton(
                text="🛠️ ابزارهای پیشرفته",
                callback_data="advanced"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(buttons)

def get_category_keyboard(tools: List[Dict]) -> InlineKeyboardMarkup:
    """
    ایجاد کیبورد ابزارهای یک دسته‌بندی خاص
    """
    buttons = []
    
    # ایجاد دکمه‌ها در ردیف‌های دو تایی
    for i in range(0, len(tools), 2):
        row = []
        for tool in tools[i:i+2]:
            row.append(
                InlineKeyboardButton(
                    text=tool["name"],
                    callback_data=tool["id"]
                )
            )
        buttons.append(row)
    
    # اضافه کردن دکمه بازگشت
    buttons.append([get_back_button("بازگشت به منوی اصلی")])
    
    return InlineKeyboardMarkup(buttons)

def get_tool_keyboard(tool_id: str) -> InlineKeyboardMarkup:
    """
    ایجاد کیبورد برای یک ابزار خاص
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="🔍 تحلیل مجدد",
                callback_data=f"retry_{tool_id}"
            ),
            InlineKeyboardButton(
                text="📊 ذخیره نتیجه",
                callback_data=f"save_{tool_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📤 اشتراک‌گذاری",
                callback_data=f"share_{tool_id}"
            )
        ],
        [get_back_button("بازگشت به دسته‌بندی")]
    ]
    
    return InlineKeyboardMarkup(buttons)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """
    ایجاد کیبورد مدیریت برای ادمین‌ها
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="📊 آمار کاربران",
                callback_data="admin_stats"
            ),
            InlineKeyboardButton(
                text="🔧 تنظیمات سیستم",
                callback_data="admin_settings"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 حالت تعمیرات",
                callback_data="admin_maintenance"
            ),
            InlineKeyboardButton(
                text="📝 اطلاع‌رسانی",
                callback_data="admin_broadcast"
            )
        ],
        [get_back_button("بازگشت به منوی اصلی")]
    ]
    
    return InlineKeyboardMarkup(buttons)

def get_back_button(text: str = "بازگشت") -> InlineKeyboardButton:
    """
    ایجاد دکمه بازگشت استاندارد
    """
    return InlineKeyboardButton(
        text=f"◀️ {text}",
        callback_data="back"
    )

def create_inline_keyboard(buttons: List[Dict], back_button: bool = True) -> InlineKeyboardMarkup:
    """
    ایجاد کیبورد اینلاین سفارشی
    
    پارامترها:
        buttons: لیستی از دیکشنری‌ها با کلیدهای 'text' و 'data'
        back_button: آیا دکمه بازگشت اضافه شود؟
    
    مثال:
        buttons = [
            {"text": "دکمه ۱", "data": "btn1"},
            {"text": "دکمه ۲", "data": "btn2"}
        ]
    """
    keyboard = []
    
    for btn in buttons:
        keyboard.append([
            InlineKeyboardButton(
                text=btn["text"],
                callback_data=btn["data"]
            )
        ])
    
    if back_button:
        keyboard.append([get_back_button()])
    
    return InlineKeyboardMarkup(keyboard)
