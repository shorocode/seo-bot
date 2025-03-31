import logging
from typing import Callable, Any, Optional
from functools import wraps
from telegram import Update
from telegram.ext import CallbackContext

logger = logging.getLogger(__name__)

def error_handler(func: Callable) -> Callable:
    """دکوراتور مدیریت خطا برای هندلرهای ربات"""
    @wraps(func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs) -> Optional[Any]:
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            logger.error(
                f"Error in {func.__name__}: {str(e)}",
                exc_info=True,
                extra={
                    'user_id': update.effective_user.id if update.effective_user else None,
                    'chat_id': update.effective_chat.id if update.effective_chat else None
                }
            )
            
            if update.callback_query:
                await update.callback_query.answer("⚠️ خطایی رخ داد. لطفا مجددا تلاش کنید", show_alert=True)
            elif update.message:
                await update.message.reply_text("⚠️ خطایی در پردازش درخواست شما رخ داد")
            
            return None
    return wrapper

class SEOBotError(Exception):
    """خطای پایه برای ربات سئو"""
    def __init__(self, message: str, user_friendly: str = None):
        self.message = message
        self.user_friendly = user_friendly or "خطایی در سیستم رخ داد"
        super().__init__(message)

class APILimitExceeded(SEOBotError):
    """خطای محدودیت API"""
    def __init__(self):
        super().__init__(
            "API rate limit exceeded",
            "محدودیت درخواست به سرویس خارجی. لطفا چند دقیقه دیگر تلاش کنید"
        )

class DatabaseError(SEOBotError):
    """خطای پایگاه داده"""
    pass
