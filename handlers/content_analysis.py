from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import CallbackContext, MessageHandler, Filters, CallbackQueryHandler
from collections import Counter
from typing import Dict, List, Optional, Tuple
import re
import logging

from services.ai import AIService
from services.database import Database
from utils.decorators import log_activity, restricted
from utils.helpers import truncate_text, format_number
from utils.logger import logger

class ContentAnalysisHandler:
    def __init__(self, db: Database):
        self.db = db
        self.ai = AIService(api_key=settings.OPENAI_API_KEY)
        self.MAX_INPUT_LENGTH = 5000
        self.PERSIAN_STOPWORDS = self._load_persian_stopwords()

        self.TOOLS = [
            {
                'id': 'kw_density',
                'name': '📊 چگالی کلمات کلیدی',
                'description': 'تحلیل چگالی و توزیع کلمات کلیدی در متن',
                'input_prompt': '🔠 لطفا متن خود را برای تحلیل چگالی کلمات کلیدی ارسال کنید:',
                'min_words': 20,
                'handler': self.kw_density_handler
            },
            {
                'id': 'readability',
                'name': '📖 تحلیل خوانایی',
                'description': 'سنجش سطح خوانایی متن با معیارهای استاندارد',
                'input_prompt': '📚 لطفا متن خود را برای تحلیل خوانایی ارسال کنید:',
                'min_words': 50,
                'handler': self.readability_handler
            },
            {
                'id': 'seo_analysis',
                'name': '🔍 تحلیل سئو',
                'description': 'بررسی متن از نظر معیارهای سئو',
                'input_prompt': '✍️ لطفا متن خود را برای تحلیل سئو ارسال کنید:',
                'min_words': 100,
                'handler': self.seo_analysis_handler
            }
        ]

    def _load_persian_stopwords(self) -> List[str]:
        """بارگذاری لیست کلمات بی‌معنی فارسی"""
        return [
            'و', 'در', 'به', 'از', 'که', 'را', 'این', 'است', 'با', 'برای',
            'آن', 'یک', 'یا', 'هم', 'اما', 'تا', 'کنید', 'شده', 'شود',
            'های', 'کرد', 'شد', 'خود', 'ما', 'شما', 'او', 'آنها', 'همه',
            'هر', 'اگر', 'نیز', 'دیگر', 'بسیار', 'چه', 'هستند', 'بی', 'من',
            'تو', 'بر', 'همین', 'هیچ', 'دو', 'چون', 'پیش', 'بین', 'چیست',
            'کردن', 'کردم', 'کنم', 'کنی', 'کند', 'کنیم', 'کنید', 'کنند'
        ]

    def validate_text(self, text: str, min_words: int) -> Tuple[bool, str]:
        """
        اعتبارسنجی متن ورودی
        
        Args:
            text: متن ورودی
            min_words: حداقل تعداد کلمات مورد نیاز
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not text.strip():
            return False, "⚠️ متن ورودی خالی است."
            
        if len(text) > self.MAX_INPUT_LENGTH:
            return False, f"⚠️ متن بسیار طولانی است (حداکثر {self.MAX_INPUT_LENGTH} کاراکتر)"
            
        word_count = len(text.split())
        if word_count < min_words:
            return False, f"⚠️ متن بسیار کوتاه است (حداقل {min_words} کلمه نیاز است)"
            
        return True, ""

    @log_activity
    def kw_density_handler(self, update: Update, context: CallbackContext, text: str) -> str:
        """تحلیل چگالی کلمات کلیدی"""
        # اعتبارسنجی متن
        is_valid, error_msg = self.validate_text(text, self.TOOLS[0]['min_words'])
        if not is_valid:
            return error_msg

        try:
            # پردازش متن و استخراج کلمات
            words = [
                word.strip('.,!?()[]{}"\'').lower() 
                for word in re.findall(r'\b\w+\b', text) 
                if word.strip()
            ]
            
            word_count = len(words)
            keyword_counts = Counter(words)
            
            # فیلتر کلمات بی‌معنی
            meaningful_words = {
                kw: count for kw, count in keyword_counts.items() 
                if kw not in self.PERSIAN_STOPWORDS and len(kw) > 2
            }
            
            if not meaningful_words:
                return "⚠️ هیچ کلمه کلیدی معناداری یافت نشد."
            
            # تولید گزارش
            report = [
                "📊 *نتایج تحلیل چگالی کلمات کلیدی:*",
                f"🔠 تعداد کل کلمات: {word_count}",
                f"🔍 تعداد کلمات منحصر به فرد: {len(meaningful_words)}",
                "\n🏆 *کلمات کلیدی برتر:*"
            ]
            
            for kw, count in Counter(meaningful_words).most_common(10):
                density = (count / word_count) * 100
                report.append(f"- {kw}: {count} بار ({density:.2f}%)")
            
            # ذخیره در دیتابیس
            self.db.save_content_analysis(
                user_id=update.effective_user.id,
                tool_id='kw_density',
                input_text=truncate_text(text, 500),
                result='\n'.join(report)
            )
            
            return '\n'.join(report)
            
        except Exception as e:
            logger.error(f"Error in kw_density analysis: {e}", exc_info=True)
            return "⚠️ خطایی در تحلیل چگالی کلمات رخ داد."

    @log_activity
    def readability_handler(self, update: Update, context: CallbackContext, text: str) -> str:
        """تحلیل خوانایی متن"""
        # اعتبارسنجی متن
        is_valid, error_msg = self.validate_text(text, self.TOOLS[1]['min_words'])
        if not is_valid:
            return error_msg

        try:
            # تحلیل با هوش مصنوعی
            analysis = self.ai.analyze_text(
                task="readability_analysis",
                text=text,
                language="fa"
            )
            
            if not analysis:
                return "⚠️ خطا در تحلیل خوانایی. لطفا بعدا تلاش کنید."
            
            # تولید گزارش
            result = [
                "📚 *نتایج تحلیل خوانایی:*",
                f"🔹 امتیاز خوانایی: {analysis.get('score', 0)}/100",
                f"🔹 سطح پیشنهادی: {analysis.get('recommended_level', 'نامشخص')}",
                f"🔹 میانگین طول جمله: {analysis.get('avg_sentence_length', 0)} کلمه",
                "\n📌 *توصیه‌های بهبود:*",
                analysis.get('suggestions', 'هیچ توصیه‌ای موجود نیست.')
            ]
            
            # ذخیره در دیتابیس
            self.db.save_content_analysis(
                user_id=update.effective_user.id,
                tool_id='readability',
                input_text=truncate_text(text, 500),
                result='\n'.join(result)
            )
            
            return '\n'.join(result)
            
        except Exception as e:
            logger.error(f"Error in readability analysis: {e}", exc_info=True)
            return "⚠️ خطایی در تحلیل خوانایی رخ داد."

    @log_activity
    def seo_analysis_handler(self, update: Update, context: CallbackContext, text: str) -> str:
        """تحلیل سئو متن"""
        # اعتبارسنجی متن
        is_valid, error_msg = self.validate_text(text, self.TOOLS[2]['min_words'])
        if not is_valid:
            return error_msg

        try:
            # تحلیل با هوش مصنوعی
            analysis = self.ai.analyze_text(
                task="seo_analysis",
                text=text,
                language="fa"
            )
            
            if not analysis:
                return "⚠️ خطا در تحلیل سئو. لطفا بعدا تلاش کنید."
            
            # تولید گزارش
            result = [
                "🔍 *نتایج تحلیل سئو:*",
                f"🔹 امتیاز سئو: {analysis.get('score', 0)}/100",
                "\n✅ *نقاط قوت:*",
                analysis.get('strengths', 'هیچ نقطه قوت مشخصی یافت نشد.'),
                "\n⚠️ *نقاط ضعف:*",
                analysis.get('weaknesses', 'هیچ نقطه ضعف مشخصی یافت نشد.'),
                "\n💡 *پیشنهادات بهبود:*",
                analysis.get('recommendations', 'هیچ پیشنهادی موجود نیست.')
            ]
            
            # ذخیره در دیتابیس
            self.db.save_content_analysis(
                user_id=update.effective_user.id,
                tool_id='seo_analysis',
                input_text=truncate_text(text, 500),
                result='\n'.join(result)
            )
            
            return '\n'.join(result)
            
        except Exception as e:
            logger.error(f"Error in SEO analysis: {e}", exc_info=True)
            return "⚠️ خطایی در تحلیل سئو رخ داد."

    def send_analysis_result(self, update: Update, tool_name: str, result: str) -> None:
        """ارسال نتیجه تحلیل به کاربر"""
        try:
            # ایجاد کیبورد اقدامات بعدی
            buttons = [
                [InlineKeyboardButton("🔄 تحلیل جدید", callback_data="content_menu")],
                [get_back_button()]
            ]

            update.message.reply_text(
                text=f"*{tool_name}*\n\n{result}",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            
        except Exception as e:
            logger.error(f"Error sending analysis result: {e}", exc_info=True)
            update.message.reply_text("⚠️ خطایی در نمایش نتایج رخ داد.")

    def setup_handlers(self, dispatcher):
        """تنظیم هندلرها برای تحلیل محتوا"""
        for tool in self.TOOLS:
            dispatcher.add_handler(MessageHandler(
                Filters.text & ~Filters.command,
                tool['handler'],
                pass_user_data=True
            ))
