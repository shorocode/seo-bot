#!/usr/bin/env python3
import logging
from telegram.ext import (
    Updater,
    Dispatcher,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler
)
from config import settings
from utils.logger import configure_logging
from handlers import (
    register_admin_handlers,
    register_content_handlers,
    register_technical_handlers,
    register_backlink_handlers,
    register_competition_handlers,
    register_dashboard_handlers
)

def setup_dispatcher(dp: Dispatcher) -> None:
    """ثبت تمام هندلرهای ربات"""
    register_admin_handlers(dp)
    register_content_handlers(dp)
    register_technical_handlers(dp)
    register_backlink_handlers(dp)
    register_competition_handlers(dp)
    register_dashboard_handlers(dp)

    # هندلر خطاهای عمومی
    dp.add_error_handler(error_handler)

def error_handler(update: object, context: CallbackContext) -> None:
    """مدیریت متمرکز خطاها"""
    logger = logging.getLogger(__name__)
    logger.error(f"Exception occurred: {context.error}", exc_info=context.error)
    
    if update and hasattr(update, 'message'):
        update.message.reply_text("⚠️ خطایی در پردازش درخواست رخ داد")

def main() -> None:
    """ورودی اصلی برنامه"""
    # پیکربندی لاگینگ
    configure_logging()
    
    try:
        # ایجاد آپدیتر با تنظیمات پیشرفته
        updater = Updater(
            token=settings.TELEGRAM_TOKEN,
            workers=settings.WORKERS,
            request_kwargs={
                'read_timeout': 30,
                'connect_timeout': 15
            },
            use_context=True
        )

        # تنظیم هندلرها
        setup_dispatcher(updater.dispatcher)

        # راه‌اندازی ربات
        if settings.WEBHOOK_MODE:
            updater.start_webhook(
                listen='0.0.0.0',
                port=settings.PORT,
                url_path=settings.TELEGRAM_TOKEN,
                webhook_url=f"{settings.WEBHOOK_URL}/{settings.TELEGRAM_TOKEN}",
                cert=settings.SSL_CERT_PATH if settings.SSL_CERT_PATH else None,
                key=settings.SSL_KEY_PATH if settings.SSL_KEY_PATH else None
            )
        else:
            updater.start_polling(
                poll_interval=0.5,
                timeout=20,
                drop_pending_updates=True
            )

        logger.info(f"ربات با موفقیت در حالت {'Webhook' if settings.WEBHOOK_MODE else 'Polling'} راه‌اندازی شد")
        updater.idle()

    except Exception as e:
        logging.critical(f"خطای بحرانی در راه‌اندازی ربات: {e}")
        raise

if __name__ == '__main__':
    main()
