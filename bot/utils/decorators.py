import functools
import time
import inspect
from typing import Callable, Any, Optional, Dict
import logging

from telegram import Update
from telegram.ext import CallbackContext

from config import settings
from services.database import db
from utils.logger import logger

def restricted(access_level: str = "admin"):
    """Decorator to restrict access to certain user levels"""
    
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
            user = update.effective_user
            
            # Check access level
            if access_level == "admin":
                if user.id not in settings.ADMINS:
                    update.message.reply_text("⚠️ دسترسی محدود به مدیران سیستم")
                    logger.warning(
                        f"Unauthorized access attempt by user {user.id}",
                        extra={"user": user.id, "command": func.__name__}
                    )
                    return
            
            # Check for maintenance mode
            if settings.MAINTENANCE_MODE and user.id not in settings.ADMINS:
                update.message.reply_text("🔧 ربات در حال حاضر در حالت تعمیرات است. لطفاً بعداً تلاش کنید.")
                return
            
            return func(update, context, *args, **kwargs)
        return wrapper
    return decorator

def log_activity(action_name: Optional[str] = None):
    """Decorator to log user activities"""
    
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
            user = update.effective_user
            chat = update.effective_chat
            
            # Default action name
            action = action_name or func.__name__
            
            try:
                # Log before execution
                logger.info(
                    f"User {user.id} started action: {action}",
                    extra={
                        "user_id": user.id,
                        "chat_id": chat.id if chat else None,
                        "action": action,
                        "status": "started"
                    }
                )
                
                # Execute function
                result = func(update, context, *args, **kwargs)
                
                # Log successful completion
                logger.info(
                    f"User {user.id} completed action: {action}",
                    extra={
                        "user_id": user.id,
                        "chat_id": chat.id if chat else None,
                        "action": action,
                        "status": "completed"
                    }
                )
                
                # Update user last activity in DB
                if db and user:
                    db.get_or_create_user({
                        "id": user.id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "language_code": user.language_code
                    })
                
                return result
                
            except Exception as e:
                # Log failure
                logger.error(
                    f"User {user.id} failed action: {action}",
                    extra={
                        "user_id": user.id,
                        "chat_id": chat.id if chat else None,
                        "action": action,
                        "status": "failed",
                        "error": str(e)
                    },
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator

def validate_input(*validators: Callable):
    """Decorator to validate function inputs"""
    
    def decorator(func: Callable):
        # Preserve function signature
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get parameter names and values
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Run validators
            for validator in validators:
                for param_name, param_value in bound_args.arguments.items():
                    try:
                        validator(param_name, param_value)
                    except ValueError as e:
                        logger.warning(
                            f"Validation failed for {func.__name__}: {str(e)}",
                            extra={
                                "function": func.__name__,
                                "parameter": param_name,
                                "value": str(param_value),
                                "validator": validator.__name__
                            }
                        )
                        raise
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def rate_limited(max_calls: int, time_frame: int = 60):
    """Decorator to implement rate limiting"""
    
    def decorator(func: Callable):
        # Store call timestamps
        call_history = []
        
        @functools.wraps(func)
        def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
            nonlocal call_history
            
            # Get user ID or chat ID for rate limiting
            user_id = update.effective_user.id if update.effective_user else None
            chat_id = update.effective_chat.id if update.effective_chat else None
            limit_key = f"{user_id}:{chat_id}"
            
            # Remove old calls
            current_time = time.time()
            call_history = [
                t for t in call_history 
                if current_time - t[0] < time_frame and t[1] == limit_key
            ]
            
            # Check rate limit
            if len(call_history) >= max_calls:
                logger.warning(
                    f"Rate limit exceeded for {limit_key} on {func.__name__}",
                    extra={
                        "user_id": user_id,
                        "chat_id": chat_id,
                        "function": func.__name__,
                        "call_count": len(call_history),
                        "max_calls": max_calls,
                        "time_frame": time_frame
                    }
                )
                
                if update.callback_query:
                    update.callback_query.answer(
                        f"⚠️ شما در حال ارسال درخواست‌های زیاد هستید. لطفاً {time_frame} ثانیه صبر کنید.",
                        show_alert=True
                    )
                elif update.message:
                    update.message.reply_text(
                        f"⚠️ شما در حال ارسال درخواست‌های زیاد هستید. لطفاً {time_frame} ثانیه صبر کنید."
                    )
                return
            
            # Add current call
            call_history.append((current_time, limit_key))
            
            return func(update, context, *args, **kwargs)
        return wrapper
    return decorator
