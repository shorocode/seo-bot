#!/usr/bin/env python3
import logging
from typing import Optional
from telegram.ext import (
    Updater,
    Dispatcher,
    CallbackContext
)
from telegram import Update
from config import settings
from utils.logger import configure_logging
from utils.error_handling import (
    handle_network_error,
    handle_validation_error,
    notify_admins
)
from handlers import (
    register_admin_handlers,
    register_content_handlers,
    register_technical_handlers,
    register_backlink_handlers,
    register_competition_handlers,
    register_dashboard_handlers
)

logger = logging.getLogger(__name__)

def setup_dispatcher(dp: Dispatcher) -> None:
    """ثبت تمام هندلرهای ربات با مدیریت خطاهای خاص"""
    try:
        register_admin_handlers(dp)
        register_content_handlers(dp)
        register_technical_handlers(dp)
        register_backlink_handlers(dp)
        register_competition_handlers(dp)
        register_dashboard_handlers(dp)
        
        # هندلر خطاهای عمومی
        dp.add_error_handler(global_error_handler)
        
        logger.info("تمام هندلرها با موفقیت ثبت شدند")
    except Exception as e:
        logger.critical(f"خطا در تنظیم هندلرها: {e}")
        raise

def global_error_handler(update: Optional[Update], context: CallbackContext) -> None:
    """مدیریت متمرکز و طبقه‌بندی شده خطاها"""
    error = context.error
    
    try:
        # تفکیک نوع خطا
        if isinstance(error, ConnectionError):
            handle_network_error(update, context)
        elif isinstance(error, ValueError):
            handle_validation_error(update, context)
        else:
            logger.error(f"خطای ناشناخته: {error}", exc_info=error)
            notify_admins(context.bot, f"⚠️ خطای سیستمی: {error}")
            
        if update and update.effective_message:
            update.effective_message.reply_text(
                "⚠️ خطایی در پردازش درخواست شما رخ داد. لطفاً稍后再试"
            )
    except Exception as e:
        logger.critical(f"خطا در مدیریت خطا! {e}", exc_info=e)

def start_bot(updater: Updater) -> None:
    """راه‌اندازی ربات بر اساس حالت عملیاتی"""
    if settings.WEBHOOK_MODE:
        if not all([settings.SSL_CERT_PATH, settings.SSL_KEY_PATH]):
            logger.warning("فایل‌های SSL یافت نشدند، استفاده از حالت ناامن")
        
        updater.start_webhook(
            listen='0.0.0.0',
            port=settings.PORT,
            url_path=settings.TELEGRAM_TOKEN,
            webhook_url=f"{settings.WEBHOOK_URL}/{settings.TELEGRAM_TOKEN}",
            cert=settings.SSL_CERT_PATH,
            key=settings.SSL_KEY_PATH,
            drop_pending_updates=True
        )
        logger.info(f"وب‌هوک راه‌اندازی شد در {settings.WEBHOOK_URL}")
    else:
        updater.start_polling(
            poll_interval=0.5,
            timeout=20,
            drop_pending_updates=True,
            allowed_updates=[
                'message', 'callback_query', 
                'inline_query', 'chosen_inline_result'
            ]
        )
        logger.info("ربات در حالت polling راه‌اندازی شد")

def main() -> None:
    """ورودی اصلی برنامه با مدیریت جامع خطاها"""
    try:
        # پیکربندی لاگینگ
        configure_logging()
        logger.info("آماده‌سازی ربات...")
        
        # تنظیمات پیشرفته
        request_kwargs = {
            'read_timeout': settings.READ_TIMEOUT,
            'connect_timeout': settings.CONNECT_TIMEOUT,
            'pool_timeout': settings.POOL_TIMEOUT
        }
        
        if settings.PROXY_URL:
            request_kwargs['proxy_url'] = settings.PROXY_URL
        
        updater = Updater(
            token=settings.TELEGRAM_TOKEN,
            workers=settings.WORKERS,
            request_kwargs=request_kwargs,
            use_context=True
        )
        
        # تنظیم هندلرها
        setup_dispatcher(updater.dispatcher)
        
        # راه‌اندازی ربات
        start_bot(updater)
        logger.info("ربات با موفقیت راه‌اندازی شد")
        
        # اجرای اصلی
        updater.idle()
        
    except KeyboardInterrupt:
        logger.info("ربات به صورت دستی متوقف شد")
    except Exception as e:
        logger.critical(f"خطای بحرانی: {e}", exc_info=e)
        notify_admins(None, f"🚨 ربات دچار خطای بحرانی شد: {e}")
        raise

if __name__ == '__main__':
    main()
