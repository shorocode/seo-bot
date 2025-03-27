import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler

from config import settings
from config.keyboards import get_admin_keyboard, get_back_button
from services.database import db
from utils.decorators import restricted
from utils.helpers import format_timedelta, truncate_text
from utils.logger import logger

# تنظیمات اختصاصی ادمین
ADMIN_COMMANDS = {
    'stats': '📊 نمایش آمار سیستم',
    'users': '👥 مدیریت کاربران',
    'settings': '⚙️ تنظیمات سیستم',
    'broadcast': '📢 ارسال پیام همگانی',
    'maintenance': '🔧 حالت تعمیرات',
    'backup': '💾 تهیه نسخه پشتیبان'
}

@restricted(access_level="admin")
def admin_panel(update: Update, context: CallbackContext):
    """نمایش پنل مدیریت به ادمین‌ها"""
    try:
        user = update.effective_user
        
        # ایجاد متن خوش‌آمدگویی
        welcome_text = (
            f"👮‍♂️ *پنل مدیریت*\n\n"
            f"🔹 کاربر: {user.mention_markdown()}\n"
            f"🔹 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"🔹 حالت تعمیرات: {'✅ فعال' if settings.MAINTENANCE_MODE else '❌ غیرفعال'}\n\n"
            "لطفا یکی از گزینه‌ها را انتخاب کنید:"
        )
        
        # ارسال کیبورد مدیریت
        update.message.reply_text(
            text=welcome_text,
            reply_markup=get_admin_keyboard(),
            parse_mode='Markdown'
        )
        
        logger.info(f"Admin panel accessed by {user.id}")
        
    except Exception as e:
        logger.error(f"Error in admin_panel: {str(e)}", exc_info=True)
        if update.message:
            update.message.reply_text("⚠️ خطایی در نمایش پنل مدیریت رخ داد.")

def handle_admin_callback(update: Update, context: CallbackContext):
    """مدیریت کلیک‌های کیبورد ادمین"""
    query = update.callback_query
    query.answer()
    
    try:
        action = query.data
        
        if action == "admin_stats":
            show_system_stats(query)
        elif action == "admin_settings":
            show_system_settings(query)
        elif action == "admin_maintenance":
            toggle_maintenance_mode(query)
        elif action == "admin_broadcast":
            start_broadcast(query, context)
        elif action == "back":
            return_to_main_menu(query)
        
    except Exception as e:
        logger.error(f"Error in admin callback: {str(e)}", exc_info=True)
        query.edit_message_text("⚠️ خطایی در پردازش درخواست شما رخ داد.")

def show_system_stats(query):
    """نمایش آمار سیستم"""
    try:
        if not db:
            raise Exception("Database not available")
        
        # دریافت آمار از دیتابیس
        stats = db.get_usage_stats()
        
        # ایجاد متن گزارش
        report = [
            "📊 *آمار سیستم*\n",
            f"👤 کاربران کل: {stats.get('total_users', 0)}",
            f"📝 درخواست‌های امروز: {self._get_today_requests(stats)}",
            "\n🔝 ابزارهای پراستفاده:"
        ]
        
        # اضافه کردن ابزارهای پراستفاده
        for tool in stats.get('tool_stats', [])[:5]:
            report.append(f"- {tool['tool_id']}: {tool['count']} بار")
        
        # اضافه کردن اطلاعات استفاده روزانه
        report.extend([
            "\n📅 استفاده 30 روز اخیر:",
            self._format_daily_usage(stats.get('daily_usage', []))
        ])
        
        # ایجاد کیبورد
        buttons = [
            [InlineKeyboardButton("🔄 بروزرسانی آمار", callback_data="admin_stats")],
            [get_back_button()]
        ]
        
        query.edit_message_text(
            text="\n".join(report),
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error showing stats: {str(e)}", exc_info=True)
        query.edit_message_text("⚠️ خطایی در دریافت آمار سیستم رخ داد.")

def _get_today_requests(self, stats: Dict) -> int:
    """دریافت تعداد درخواست‌های امروز"""
    today = datetime.now().date().isoformat()
    for day in stats.get('daily_usage', []):
        if day['day'] == today:
            return day['count']
    return 0

def _format_daily_usage(self, daily_usage: List[Dict]) -> str:
    """قالب‌بندی آمار روزانه"""
    if not daily_usage:
        return "اطلاعاتی موجود نیست"
    
    # گروه‌بندی بر اساس هفته
    weekly = []
    current_week = []
    current_week_num = datetime.strptime(daily_usage[0]['day'], '%Y-%m-%d').isocalendar()[1]
    
    for day in daily_usage:
        week_num = datetime.strptime(day['day'], '%Y-%m-%d').isocalendar()[1]
        if week_num == current_week_num:
            current_week.append(day)
        else:
            weekly.append(current_week)
            current_week = [day]
            current_week_num = week_num
    
    if current_week:
        weekly.append(current_week)
    
    # ایجاد متن
    result = []
    for week in weekly[-4:]:  # آخرین 4 هفته
        total = sum(day['count'] for day in week)
        start_date = week[0]['day'][5:]  # حذف سال
        end_date = week[-1]['day'][5:]
        result.append(f"هفته {start_date} تا {end_date}: {total} درخواست")
    
    return "\n".join(result)

def show_system_settings(query):
    """نمایش تنظیمات سیستم"""
    try:
        settings_text = [
            "⚙️ *تنظیمات سیستم*\n",
            f"🔸 حالت دیباگ: {'✅ فعال' if settings.DEBUG else '❌ غیرفعال'}",
            f"🔸 سطح لاگ: {settings.LOG_LEVEL}",
            f"🔸 تعداد کارگران: {settings.WORKERS}",
            f"🔸 حالت وب‌هوک: {'✅ فعال' if settings.WEBHOOK_MODE else '❌ غیرفعال'}",
            f"🔸 ارائه‌دهنده هوش مصنوعی: {settings.DEFAULT_AI_PROVIDER}",
            "\n⚠️ برای تغییر تنظیمات، فایل .env یا config.json را ویرایش کنید."
        ]
        
        buttons = [
            [InlineKeyboardButton("🔄 بروزرسانی", callback_data="admin_settings")],
            [get_back_button()]
        ]
        
        query.edit_message_text(
            text="\n".join(settings_text),
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error showing settings: {str(e)}", exc_info=True)
        query.edit_message_text("⚠️ خطایی در نمایش تنظیمات رخ داد.")

def toggle_maintenance_mode(query):
    """تغییر حالت تعمیرات"""
    try:
        settings.MAINTENANCE_MODE = not settings.MAINTENANCE_MODE
        status = "✅ فعال" if settings.MAINTENANCE_MODE else "❌ غیرفعال"
        
        query.edit_message_text(
            text=f"حالت تعمیرات به {status} تغییر یافت.",
            reply_markup=InlineKeyboardMarkup([[get_back_button()]])
        )
        
        logger.warning(f"Maintenance mode changed to {settings.MAINTENANCE_MODE} by {query.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error toggling maintenance: {str(e)}", exc_info=True)
        query.edit_message_text("⚠️ خطایی در تغییر حالت تعمیرات رخ داد.")

def start_broadcast(query, context: CallbackContext):
    """شروع فرآیند ارسال پیام همگانی"""
    try:
        context.user_data['broadcast_state'] = 'waiting_message'
        
        query.edit_message_text(
            text="✍️ لطفا پیام همگانی را ارسال کنید:",
            reply_markup=InlineKeyboardMarkup([[get_back_button("لغو")]])
        )
        
    except Exception as e:
        logger.error(f"Error starting broadcast: {str(e)}", exc_info=True)
        query.edit_message_text("⚠️ خطایی در شروع ارسال همگانی رخ داد.")

def process_broadcast_message(update: Update, context: CallbackContext):
    """پردازش پیام همگانی و ارسال به کاربران"""
    if 'broadcast_state' not in context.user_data:
        return
    
    try:
        message = update.message.text
        users_count = db.get_active_users_count() if db else 0
        
        # تایید نهایی توسط ادمین
        confirm_text = (
            f"📢 *پیام همگانی*\n\n"
            f"{message}\n\n"
            f"این پیام برای {users_count} کاربر ارسال خواهد شد.\n"
            "آیا مطمئن هستید؟"
        )
        
        buttons = [
            [
                InlineKeyboardButton("✅ بله، ارسال کن", callback_data="confirm_broadcast"),
                InlineKeyboardButton("❌ خیر، لغو", callback_data="cancel_broadcast")
            ]
        ]
        
        update.message.reply_text(
            text=confirm_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='Markdown'
        )
        
        # ذخیره پیام در context برای استفاده بعدی
        context.user_data['broadcast_message'] = message
        context.user_data['broadcast_state'] = 'waiting_confirmation'
        
    except Exception as e:
        logger.error(f"Error processing broadcast: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطایی در پردازش پیام همگانی رخ داد.")
        context.user_data.pop('broadcast_state', None)

def send_broadcast(context: CallbackContext):
    """ارسال واقعی پیام همگانی به کاربران"""
    try:
        if not db:
            raise Exception("Database not available")
        
        message = context.user_data.get('broadcast_message')
        if not message:
            raise Exception("No broadcast message found")
        
        # دریافت لیست کاربران
        users = db.get_all_users()
        success_count = 0
        failed_count = 0
        
        # ارسال به هر کاربر
        for user in users:
            try:
                context.bot.send_message(
                    chat_id=user['id'],
                    text=f"📢 پیام همگانی:\n\n{message}"
                )
                success_count += 1
            except Exception as e:
                logger.warning(f"Failed to send broadcast to {user['id']}: {str(e)}")
                failed_count += 1
        
        # گزارش نتیجه
        report = (
            f"✅ ارسال همگانی تکمیل شد:\n\n"
            f"📩 ارسال موفق: {success_count}\n"
            f"❌ ارسال ناموفق: {failed_count}"
        )
        
        context.bot.send_message(
            chat_id=context.user_data.get('admin_chat_id'),
            text=report
        )
        
    except Exception as e:
        logger.error(f"Error sending broadcast: {str(e)}", exc_info=True)
        context.bot.send_message(
            chat_id=context.user_data.get('admin_chat_id'),
            text="⚠️ خطایی در ارسال پیام همگانی رخ داد."
        )
    finally:
        context.user_data.pop('broadcast_state', None)
        context.user_data.pop('broadcast_message', None)

def return_to_main_menu(query):
    """بازگشت به منوی اصلی مدیریت"""
    try:
        query.edit_message_text(
            text="لطفا یکی از گزینه‌های مدیریت را انتخاب کنید:",
            reply_markup=get_admin_keyboard()
        )
    except Exception as e:
        logger.error(f"Error returning to main menu: {str(e)}", exc_info=True)
        query.edit_message_text("⚠️ خطایی در بازگشت به منوی اصلی رخ داد.")

def setup_admin_handlers(dispatcher):
    """تنظیم هندلرهای مدیریت"""
    dispatcher.add_handler(CommandHandler("admin", admin_panel))
    dispatcher.add_handler(CallbackQueryHandler(handle_admin_callback, pattern="^admin_"))
    dispatcher.add_handler(CallbackQueryHandler(handle_broadcast_confirmation, pattern="^(confirm|cancel)_broadcast$"))
    
    # هندلر پیام‌های متنی برای ارسال همگانی
    dispatcher.add_handler(MessageHandler(
        Filters.text & ~Filters.command,
        process_broadcast_message,
        pass_user_data=True
    ))

def handle_broadcast_confirmation(update: Update, context: CallbackContext):
    """مدیریت تایید یا لغو ارسال همگانی"""
    query = update.callback_query
    query.answer()
    
    try:
        if query.data == "confirm_broadcast":
            # زمان‌بندی ارسال همگانی
            context.job_queue.run_once(
                send_broadcast,
                when=0,
                context=context.user_data
            )
            
            query.edit_message_text(
                text="✅ ارسال پیام همگانی شروع شد. نتیجه به شما اطلاع داده خواهد شد.",
                reply_markup=None
            )
        else:
            query.edit_message_text(
                text="❌ ارسال پیام همگانی لغو شد.",
                reply_markup=None
            )
        
        context.user_data.pop('broadcast_state', None)
        context.user_data.pop('broadcast_message', None)
        
    except Exception as e:
        logger.error(f"Error handling broadcast confirmation: {str(e)}", exc_info=True)
        query.edit_message_text("⚠️ خطایی در پردازش درخواست شما رخ داد.")
