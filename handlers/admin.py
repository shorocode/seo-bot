import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum, auto

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    Filters,
    JobQueue
)

from config import settings
from config.keyboards import get_admin_keyboard, get_back_button
from services.database import Database
from utils.decorators import restricted
from utils.helpers import format_timedelta, truncate_text
from utils.logger import logger

class BroadcastState(Enum):
    WAITING_MESSAGE = auto()
    WAITING_CONFIRMATION = auto()

class AdminCommand(Enum):
    STATS = "📊 نمایش آمار سیستم"
    USERS = "👥 مدیریت کاربران"
    SETTINGS = "⚙️ تنظیمات سیستم"
    BROADCAST = "📢 ارسال پیام همگانی"
    MAINTENANCE = "🔧 حالت تعمیرات"
    BACKUP = "💾 تهیه نسخه پشتیبان"

class AdminHandler:
    def __init__(self, db: Database):
        self.db = db
        self.broadcast_lock = False

    @restricted(access_level="admin")
    def admin_panel(self, update: Update, context: CallbackContext) -> None:
        """نمایش پنل مدیریت به ادمین‌ها"""
        try:
            user = update.effective_user
            uptime = format_timedelta(datetime.now() - context.bot_data.get('start_time', datetime.now()))
            
            welcome_text = (
                f"👮‍♂️ *پنل مدیریت*\n\n"
                f"🔹 کاربر: {user.mention_markdown()}\n"
                f"🔹 آپتایم: {uptime}\n"
                f"🔹 حالت تعمیرات: {'✅ فعال' if settings.MAINTENANCE_MODE else '❌ غیرفعال'}\n\n"
                "لطفا یکی از گزینه‌ها را انتخاب کنید:"
            )
            
            update.message.reply_text(
                text=welcome_text,
                reply_markup=get_admin_keyboard(),
                parse_mode='Markdown'
            )
            
            logger.info(f"Admin panel accessed by {user.id}")
            
        except Exception as e:
            logger.error(f"Error in admin_panel: {e}", exc_info=True)
            self._send_error_message(update, "نمایش پنل مدیریت")

    def handle_admin_callback(self, update: Update, context: CallbackContext) -> None:
        """مدیریت کلیک‌های کیبورد ادمین"""
        query = update.callback_query
        query.answer()
        
        try:
            action = query.data
            
            if action == "admin_stats":
                self._show_system_stats(query)
            elif action == "admin_settings":
                self._show_system_settings(query)
            elif action == "admin_maintenance":
                self._toggle_maintenance_mode(query)
            elif action == "admin_broadcast":
                self._start_broadcast(query, context)
            elif action == "back":
                self._return_to_main_menu(query)
                
        except Exception as e:
            logger.error(f"Error in admin callback: {e}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در پردازش درخواست شما رخ داد.")

    def _show_system_stats(self, query) -> None:
        """نمایش آمار سیستم"""
        try:
            stats = self.db.get_usage_stats() if self.db else {}
            
            report = [
                "📊 *آمار سیستم*\n",
                f"👤 کاربران کل: {stats.get('total_users', 0)}",
                f"📝 درخواست‌های امروز: {self._get_today_requests(stats)}",
                "\n🔝 ابزارهای پراستفاده:"
            ]
            
            for tool in stats.get('tool_stats', [])[:5]:
                report.append(f"- {tool['tool_id']}: {tool['count']} بار")
            
            report.extend([
                "\n📅 استفاده 30 روز اخیر:",
                self._format_daily_usage(stats.get('daily_usage', []))
            ])
            
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
            logger.error(f"Error showing stats: {e}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در دریافت آمار سیستم رخ داد.")

    def _get_today_requests(self, stats: Dict) -> int:
        """دریافت تعداد درخواست‌های امروز"""
        today = datetime.now().date().isoformat()
        return next((day['count'] for day in stats.get('daily_usage', []) 
                   if day['day'] == today), 0)

    def _format_daily_usage(self, daily_usage: List[Dict]) -> str:
        """قالب‌بندی آمار روزانه"""
        if not daily_usage:
            return "اطلاعاتی موجود نیست"
        
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
        
        return "\n".join(
            f"هفته {week[0]['day'][5:]} تا {week[-1]['day'][5:]}: {sum(day['count'] for day in week)} درخواست"
            for week in weekly[-4:]
        )

    def _show_system_settings(self, query) -> None:
        """نمایش تنظیمات سیستم"""
        try:
            settings_text = [
                "⚙️ *تنظیمات سیستم*\n",
                f"🔸 حالت دیباگ: {'✅ فعال' if settings.DEBUG else '❌ غیرفعال'}",
                f"🔸 سطح لاگ: {settings.LOG_LEVEL}",
                f"🔸 تعداد کارگران: {settings.WORKERS}",
                f"🔸 حالت وب‌هوک: {'✅ فعال' if settings.WEBHOOK_MODE else '❌ غیرفعال'}",
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
            logger.error(f"Error showing settings: {e}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در نمایش تنظیمات رخ داد.")

    def _toggle_maintenance_mode(self, query) -> None:
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
            logger.error(f"Error toggling maintenance: {e}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در تغییر حالت تعمیرات رخ داد.")

    def _start_broadcast(self, query, context: CallbackContext) -> None:
        """شروع فرآیند ارسال پیام همگانی"""
        if self.broadcast_lock:
            query.edit_message_text("⏳ یک ارسال همگانی در حال انجام است. لطفا صبر کنید.")
            return
            
        try:
            context.user_data['broadcast_state'] = BroadcastState.WAITING_MESSAGE
            context.user_data['admin_chat_id'] = query.message.chat_id
            
            query.edit_message_text(
                text="✍️ لطفا پیام همگانی را ارسال کنید:",
                reply_markup=InlineKeyboardMarkup([[get_back_button("لغو")]])
            )
            
        except Exception as e:
            logger.error(f"Error starting broadcast: {e}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در شروع ارسال همگانی رخ داد.")

    def _process_broadcast_message(self, update: Update, context: CallbackContext) -> None:
        """پردازش پیام همگانی"""
        if context.user_data.get('broadcast_state') != BroadcastState.WAITING_MESSAGE:
            return
            
        try:
            message = update.message.text
            users_count = self.db.get_active_users_count() if self.db else 0
            
            confirm_text = (
                f"📢 *پیام همگانی*\n\n"
                f"{message}\n\n"
                f"این پیام برای {users_count} کاربر ارسال خواهد شد.\n"
                "آیا مطمئن هستید؟"
            )
            
            buttons = [
                [InlineKeyboardButton("✅ بله، ارسال کن", callback_data="confirm_broadcast")],
                [InlineKeyboardButton("❌ خیر، لغو", callback_data="cancel_broadcast")]
            ]
            
            update.message.reply_text(
                text=confirm_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode='Markdown'
            )
            
            context.user_data['broadcast_message'] = message
            context.user_data['broadcast_state'] = BroadcastState.WAITING_CONFIRMATION
            
        except Exception as e:
            logger.error(f"Error processing broadcast: {e}", exc_info=True)
            self._send_error_message(update, "پردازش پیام همگانی")
            self._reset_broadcast(context)

    def _handle_broadcast_confirmation(self, update: Update, context: CallbackContext) -> None:
        """مدیریت تایید یا لغو ارسال همگانی"""
        query = update.callback_query
        query.answer()
        
        try:
            if query.data == "confirm_broadcast":
                self.broadcast_lock = True
                context.job_queue.run_once(
                    self._send_broadcast,
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
            
            self._reset_broadcast(context)
            
        except Exception as e:
            logger.error(f"Error handling broadcast confirmation: {e}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در پردازش درخواست شما رخ داد.")
            self._reset_broadcast(context)

    def _send_broadcast(self, context: CallbackContext) -> None:
        """ارسال واقعی پیام همگانی"""
        try:
            job_context = context.job.context
            message = job_context.get('broadcast_message')
            
            if not message or not self.db:
                raise ValueError("Invalid broadcast parameters")
            
            users = self.db.get_all_users()
            success_count = 0
            failed_users = []
            
            for user in users:
                try:
                    context.bot.send_message(
                        chat_id=user['id'],
                        text=f"📢 پیام همگانی:\n\n{message}"
                    )
                    success_count += 1
                except Exception as e:
                    logger.warning(f"Failed to send to {user['id']}: {e}")
                    failed_users.append(user['id'])
            
            report = (
                f"✅ ارسال همگانی تکمیل شد:\n\n"
                f"📩 ارسال موفق: {success_count}\n"
                f"❌ ارسال ناموفق: {len(failed_users)}"
            )
            
            if failed_users:
                report += f"\n\nکاربران ناموفق: {truncate_text(', '.join(map(str, failed_users)), 1000}"
            
            context.bot.send_message(
                chat_id=job_context.get('admin_chat_id'),
                text=report
            )
            
        except Exception as e:
            logger.error(f"Error sending broadcast: {e}", exc_info=True)
            context.bot.send_message(
                chat_id=job_context.get('admin_chat_id'),
                text="⚠️ خطایی در ارسال پیام همگانی رخ داد."
            )
        finally:
            self.broadcast_lock = False

    def _reset_broadcast(self, context: CallbackContext) -> None:
        """بازنشانی وضعیت ارسال همگانی"""
        context.user_data.pop('broadcast_state', None)
        context.user_data.pop('broadcast_message', None)
        context.user_data.pop('admin_chat_id', None)

    def _return_to_main_menu(self, query) -> None:
        """بازگشت به منوی اصلی مدیریت"""
        try:
            query.edit_message_text(
                text="لطفا یکی از گزینه‌های مدیریت را انتخاب کنید:",
                reply_markup=get_admin_keyboard()
            )
        except Exception as e:
            logger.error(f"Error returning to main menu: {e}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در بازگشت به منوی اصلی رخ داد.")

    def _send_error_message(self, update: Update, action: str) -> None:
        """ارسال پیام خطای استاندارد"""
        if update.message:
            update.message.reply_text(f"⚠️ خطایی در {action} رخ داد.")

def setup_admin_handlers(dispatcher, db: Database) -> None:
    """تنظیم هندلرهای مدیریت"""
    admin_handler = AdminHandler(db)
    
    dispatcher.add_handler(CommandHandler("admin", admin_handler.admin_panel))
    dispatcher.add_handler(CallbackQueryHandler(
        admin_handler.handle_admin_callback, 
        pattern="^admin_"
    ))
    dispatcher.add_handler(CallbackQueryHandler(
        admin_handler._handle_broadcast_confirmation, 
        pattern="^(confirm|cancel)_broadcast$"
    ))
    dispatcher.add_handler(MessageHandler(
        Filters.text & ~Filters.command,
        admin_handler._process_broadcast_message,
        pass_user_data=True
    ))
