from typing import Dict, Optional
from telegram import Update
from telegram.ext import CallbackContext
from services.ai_service import ai_service
from services.database import db
from utils.decorators import error_handler, log_activity
import logging

logger = logging.getLogger(__name__)

class ContentAnalyzer:
    """ابزارهای پیشرفته تحلیل محتوا"""
    
    def __init__(self):
        self.max_input_length = 5000

    @error_handler
    @log_activity
    async def analyze_keyword_density(
        self,
        update: Update,
        context: CallbackContext,
        text: str
    ) -> Optional[Dict]:
        """تحلیل چگالی کلمات کلیدی با هوش مصنوعی"""
        if len(text) > self.max_input_length:
            await update.message.reply_text(f"⚠️ متن نباید بیش از {self.max_input_length} کاراکتر باشد")
            return None

        analysis = await ai_service.analyze_content(
            task="keyword_density",
            text=text,
            language=context.user_data.get('language', 'fa')
        )

        if not analysis:
            await update.message.reply_text("⚠️ خطا در تحلیل محتوا")
            return None

        # ذخیره نتیجه در دیتابیس
        await db.save_analysis_result(
            user_id=update.effective_user.id,
            tool_id="keyword_density",
            input_data=text[:500],
            result=str(analysis)
        )

        return {
            "keywords": analysis.get("keywords", []),
            "suggestions": analysis.get("suggestions", "")
        }

    @error_handler
    @log_activity
    async def generate_meta_tags(
        self,
        update: Update,
        context: CallbackContext,
        url_or_text: str
    ) -> Optional[Dict]:
        """تولید خودکار متا تگ‌های سئو"""
        if url_or_text.startswith(('http://', 'https://')):
            content = await self._extract_web_content(url_or_text)
        else:
            content = url_or_text

        if not content:
            await update.message.reply_text("⚠️ محتوایی برای تحلیل یافت نشد")
            return None

        result = await ai_service.analyze_content(
            task="meta_generation",
            text=content,
            language=context.user_data.get('language', 'fa')
        )

        if not result:
            await update.message.reply_text("⚠️ خطا در تولید متا تگ‌ها")
            return None

        return {
            "title": result.get("title", ""),
            "description": result.get("description", ""),
            "keywords": result.get("keywords", [])
        }

# نمونه Singleton
content_analyzer = ContentAnalyzer()
