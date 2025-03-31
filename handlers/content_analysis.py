# handlers/content.py - مدیریت تحلیل محتوا

import logging
import re
from typing import Dict, List, Optional, Tuple
from collections import Counter

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ParseMode
)
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    Filters
)

from config import settings
from config.keyboards import get_back_button
from services.database import db
from services.ai import AIService
from utils.decorators import restricted, log_activity
from utils.helpers import format_number, truncate_text
from utils.logger import logger

class ContentAnalysisHandler:
    def __init__(self):
        self.ai_service = AIService(api_key=settings.OPENAI_API_KEY)
        self.MAX_INPUT_LENGTH = 5000  # حداکثر طول متن ورودی

    # لیست ابزارهای تحلیل محتوا
    TOOLS = [
        {
            'id': 'kw_density',
            'name': '📊 چگالی کلمات کلیدی',
            'description': 'تحلیل چگالی و توزیع کلمات کلیدی در متن',
            'input_prompt': '🔠 لطفا متن خود را برای تحلیل چگالی کلمات کلیدی ارسال کنید:',
            'min_length': 50
        },
        {
            'id': 'readability',
            'name': '📖 تحلیل خوانایی',
            'description': 'سنجش سطح خوانایی متن با معیارهای استاندارد',
            'input_prompt': '📚 لطفا متن خود را برای تحلیل خوانایی ارسال کنید (حداقل 100 کلمه):',
            'min_length': 100
        },
        {
            'id': 'seo_optimize',
            'name': '🔍 بهینه‌سازی سئو',
            'description': 'تحلیل و پیشنهادات بهینه‌سازی سئو برای متن',
            'input_prompt': '✍️ لطفا متن خود را برای تحلیل سئو ارسال کنید:',
            'min_length': 150
        },
        {
            'id': 'content_summary',
            'name': '📝 خلاصه‌سازی محتوا',
            'description': 'خلاصه‌سازی هوشمند متن با حفظ نکات کلیدی',
            'input_prompt': '📄 لطفا متن بلند خود را برای خلاصه‌سازی ارسال کنید:',
            'min_length': 200
        },
        {
            'id': 'plagiarism_check',
            'name': '🔎 بررسی سرقت ادبی',
            'description': 'تشخیص مشابهت‌های متنی با محتوای موجود در وب',
            'input_prompt': '📑 لطفا متن خود را برای بررسی سرقت ادبی ارسال کنید:',
            'min_length': 50
        }
    ]

    @restricted()
    def content_menu(self, update: Update, context: CallbackContext) -> None:
        """نمایش منوی تحلیل محتوا"""
        try:
            buttons = []
            
            # ایجاد دکمه‌ها در ردیف‌های دو تایی
            for i in range(0, len(self.TOOLS), 2):
                row = []
                for tool in self.TOOLS[i:i+2]:
                    row.append(
                        InlineKeyboardButton(
                            text=tool['name'],
                            callback_data=f"content_{tool['id']}"
                        )
                    )
                buttons.append(row)
            
            buttons.append([get_back_button()])

            update.message.reply_text(
                text="📝 *منوی تحلیل محتوا*\n\nلطفا ابزار مورد نظر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            logger.error(f"Error in content_menu: {str(e)}", exc_info=True)
            self.send_error_message(update, "نمایش منوی تحلیل محتوا")

    def handle_content_callback(self, update: Update, context: CallbackContext) -> None:
        """مدیریت کلیک‌های منوی تحلیل محتوا"""
        query = update.callback_query
        query.answer()

        try:
            action = query.data.split('_')[1]  # بخش دوم callback_data (مثل kw_density)
            
            # پیدا کردن ابزار مربوطه
            tool = next((t for t in self.TOOLS if t['id'] == action), None)
            
            if tool:
                context.user_data['content_tool'] = tool
                query.edit_message_text(
                    text=tool['input_prompt'],
                    reply_markup=InlineKeyboardMarkup([[get_back_button("لغو")]])
                )
            else:
                query.edit_message_text("⚠️ ابزار مورد نظر یافت نشد.")

        except Exception as e:
            logger.error(f"Error in content callback: {str(e)}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در پردازش درخواست شما رخ داد.")

    def process_content_input(self, update: Update, context: CallbackContext) -> None:
        """پردازش متن وارد شده برای تحلیل"""
        try:
            text = update.message.text.strip()
            tool = context.user_data.get('content_tool')
            
            if not tool or not text:
                update.message.reply_text("⚠️ درخواست نامعتبر")
                return

            # بررسی حداقل طول متن
            if len(text.split()) < tool.get('min_length', 50):
                update.message.reply_text(
                    f"⚠️ متن بسیار کوتاه است. لطفا متنی با حداقل {tool['min_length']} کلمه ارسال کنید."
                )
                return

            # محدودیت طول متن
            if len(text) > self.MAX_INPUT_LENGTH:
                text = text[:self.MAX_INPUT_LENGTH]
                update.message.reply_text(
                    f"⚠️ متن شما طولانی بود و فقط {self.MAX_INPUT_LENGTH} کاراکتر اول آن پردازش شد."
                )

            update.message.reply_text(f"⏳ در حال تحلیل متن با ابزار {tool['name']}...")
            
            # انتخاب تابع پردازش بر اساس ابزار
            if tool['id'] == 'kw_density':
                result = self.analyze_keyword_density(update, text)
            elif tool['id'] == 'readability':
                result = self.analyze_readability(update, text)
            elif tool['id'] == 'seo_optimize':
                result = self.optimize_seo(update, text)
            elif tool['id'] == 'content_summary':
                result = self.summarize_content(update, text)
            elif tool['id'] == 'plagiarism_check':
                result = self.check_plagiarism(update, text)
            else:
                result = "⚠️ ابزار مورد نظر پشتیبانی نمی‌شود."

            # ارسال نتیجه
            self.send_analysis_result(update, tool['name'], result)

        except Exception as e:
            logger.error(f"Error processing content input: {str(e)}", exc_info=True)
            self.send_error_message(update, "پردازش متن")

    @log_activity
    def analyze_keyword_density(self, update: Update, text: str) -> str:
        """تحلیل چگالی کلمات کلیدی"""
        try:
            # پاکسازی و توکن‌سازی متن
            words = [
                word.strip('.,!?()[]{}"\'').lower() 
                for word in re.findall(r'\b\w+\b', text) 
                if word.strip()
            ]
            
            if not words or len(words) < 50:
                return "⚠️ متن بسیار کوتاه است. لطفا متن طولانی‌تری ارسال کنید."
            
            # محاسبه فراوانی کلمات
            word_count = len(words)
            keyword_counts = Counter(words)
            
            # مرتب‌سازی و فیلتر کلمات با معنی
            stopwords = self._get_persian_stopwords()
            meaningful_words = {
                kw: count for kw, count in keyword_counts.items() 
                if kw not in stopwords and len(kw) > 2
            }
            
            if not meaningful_words:
                return "⚠️ هیچ کلمه کلیدی معناداری یافت نشد."
            
            sorted_kws = sorted(
                meaningful_words.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            
            # تولید گزارش
            report = ["📊 *نتایج تحلیل چگالی کلمات کلیدی:*\n"]
            report.append(f"🔠 تعداد کل کلمات: {word_count}")
            report.append(f"🔍 تعداد کلمات منحصر به فرد: {len(meaningful_words)}\n")
            report.append("🏆 *کلمات کلیدی برتر:*")
            
            for kw, count in sorted_kws[:15]:  # 15 کلمه برتر
                density = (count / word_count) * 100
                report.append(f"- {kw}: {count} بار ({density:.2f}%)")
            
            # تحلیل توزیع
            report.append("\n📈 *تحلیل توزیع:*")
            if len(sorted_kws) > 5:
                first_half = sum(count for _, count in sorted_kws[:len(sorted_kws)//2])
                second_half = sum(count for _, count in sorted_kws[len(sorted_kws)//2:])
                
                if first_half > second_half * 1.5:
                    report.append("⚠️ توزیع کلمات کلیدی نامتوازن است (تمرکز در نیمه اول متن)")
                else:
                    report.append("✅ توزیع کلمات کلیدی متوازن است")
            
            return "\n".join(report)
            
        except Exception as e:
            logger.error(f"Error in keyword density analysis: {str(e)}", exc_info=True)
            return "⚠️ خطایی در تحلیل چگالی کلمات کلیدی رخ داد."

    @log_activity
    def analyze_readability(self, update: Update, text: str) -> str:
        """تحلیل سطح خوانایی متن با هوش مصنوعی"""
        try:
            # استفاده از سرویس هوش مصنوعی برای تحلیل پیشرفته
            analysis = self.ai_service.analyze_text(
                task="readability_analysis",
                text=text,
                language="fa"
            )
            
            if not analysis:
                return "⚠️ خطا در تحلیل خوانایی. لطفا بعدا تلاش کنید."
            
            # فرمت‌دهی نتیجه
            result = [
                f"📚 *نتایج تحلیل خوانایی:*",
                f"🔹 امتیاز خوانایی: {analysis.get('score', 0)}/100",
                f"🔹 سطح پیشنهادی: {analysis.get('recommended_level', 'نامشخص')}",
                f"🔹 میانگین طول جمله: {analysis.get('avg_sentence_length', 0)} کلمه",
                "\n📌 *توصیه‌های بهبود:*",
                analysis.get('suggestions', 'هیچ توصیه‌ای موجود نیست.')
            ]
            
            return "\n".join(result)
            
        except Exception as e:
            logger.error(f"Error in readability analysis: {str(e)}", exc_info=True)
            return "⚠️ خطایی در تحلیل خوانایی رخ داد."

    @log_activity
    def optimize_seo(self, update: Update, text: str) -> str:
        """بهینه‌سازی متن برای سئو"""
        try:
            # تحلیل سئو با هوش مصنوعی
            optimization = self.ai_service.analyze_text(
                task="seo_optimization",
                text=text,
                language="fa"
            )
            
            if not optimization:
                return "⚠️ خطا در بهینه‌سازی سئو. لطفا بعدا تلاش کنید."
            
            # فرمت‌دهی نتیجه
            result = [
                f"🔍 *نتایج بهینه‌سازی سئو:*",
                f"🔹 امتیاز سئو: {optimization.get('seo_score', 0)}/100",
                "\n✅ *نقاط قوت:*",
                optimization.get('strengths', 'هیچ نقطه قوت مشخصی یافت نشد.'),
                "\n⚠️ *نقاط ضعف:*",
                optimization.get('weaknesses', 'هیچ نقطه ضعف مشخصی یافت نشد.'),
                "\n💡 *پیشنهادات بهبود:*",
                optimization.get('recommendations', 'هیچ پیشنهادی موجود نیست.')
            ]
            
            return "\n".join(result)
            
        except Exception as e:
            logger.error(f"Error in SEO optimization: {str(e)}", exc_info=True)
            return "⚠️ خطایی در بهینه‌سازی سئو رخ داد."

    @log_activity
    def summarize_content(self, update: Update, text: str) -> str:
        """خلاصه‌سازی هوشمند متن"""
        try:
            # خلاصه‌سازی با هوش مصنوعی
            summary = self.ai_service.analyze_text(
                task="summarization",
                text=text,
                language="fa",
                params={"length": "medium"}
            )
            
            if not summary or not summary.get('summary'):
                return "⚠️ خطا در خلاصه‌سازی متن. لطفا بعدا تلاش کنید."
            
            # فرمت‌دهی نتیجه
            result = [
                f"📝 *خلاصه متن:*",
                summary['summary'],
                f"\n📉 *درصد خلاصه‌سازی: {summary.get('reduction_rate', 0)}%*"
            ]
            
            return "\n".join(result)
            
        except Exception as e:
            logger.error(f"Error in content summarization: {str(e)}", exc_info=True)
            return "⚠️ خطایی در خلاصه‌سازی متن رخ داد."

    @log_activity
    def check_plagiarism(self, update: Update, text: str) -> str:
        """بررسی سرقت ادبی و مشابهت‌های متنی"""
        try:
            # بررسی با هوش مصنوعی و موتورهای جستجو
            plagiarism_check = self.ai_service.analyze_text(
                task="plagiarism_check",
                text=text,
                language="fa"
            )
            
            if not plagiarism_check:
                return "⚠️ خطا در بررسی سرقت ادبی. لطفا بعدا تلاش کنید."
            
            # فرمت‌دهی نتیجه
            result = [
                f"🔎 *نتایج بررسی سرقت ادبی:*",
                f"🔹 درصد اصالت: {plagiarism_check.get('originality_score', 0)}%",
                f"🔹 درصد مشابهت: {plagiarism_check.get('similarity_score', 0)}%",
            ]
            
            if plagiarism_check.get('similar_sources'):
                result.append("\n⚠️ *منابع مشابه:*")
                for i, source in enumerate(plagiarism_check['similar_sources'][:3], 1):
                    result.append(
                        f"{i}. [{truncate_text(source.get('title', 'بدون عنوان'), 30)}]"
                        f"({source.get('url', '#')}) - "
                        f"مشابهت: {source.get('similarity_percentage', 0)}%"
                    )
            
            return "\n".join(result)
            
        except Exception as e:
            logger.error(f"Error in plagiarism check: {str(e)}", exc_info=True)
            return "⚠️ خطایی در بررسی سرقت ادبی رخ داد."

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

            # ذخیره در دیتابیس
            if db and update.effective_user:
                tool_id = next(
                    (t['id'] for t in self.TOOLS if t['name'] == tool_name), 
                    None
                )
                
                if tool_id:
                    db.save_content_analysis(
                        user_id=update.effective_user.id,
                        tool_id=tool_id,
                        input_text=truncate_text(update.message.text, 500),
                        result=truncate_text(result, 1000)
                    )
            
        except Exception as e:
            logger.error(f"Error sending analysis result: {str(e)}", exc_info=True)
            update.message.reply_text("⚠️ خطایی در نمایش نتایج رخ داد.")

    def return_to_main_menu(self, query) -> None:
        """بازگشت به منوی اصلی تحلیل محتوا"""
        try:
            buttons = []
            
            for i in range(0, len(self.TOOLS), 2):
                row = []
                for tool in self.TOOLS[i:i+2]:
                    row.append(
                        InlineKeyboardButton(
                            text=tool['name'],
                            callback_data=f"content_{tool['id']}"
                        )
                    )
                buttons.append(row)
            
            buttons.append([get_back_button("منوی اصلی")])

            query.edit_message_text(
                text="📝 *منوی تحلیل محتوا*\n\nلطفا ابزار مورد نظر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            logger.error(f"Error returning to main menu: {str(e)}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در بازگشت به منوی اصلی رخ داد.")

    def send_error_message(self, update: Update, action: str) -> None:
        """ارسال پیام خطای استاندارد"""
        if update.message:
            update.message.reply_text(f"⚠️ خطایی در {action} رخ داد.")

    def _get_persian_stopwords(self) -> List[str]:
        """لیست کلمات بی‌معنی زبان فارسی"""
        return [
            'و', 'در', 'به', 'از', 'که', 'را', 'این', 'است', 'با', 'برای',
            'آن', 'یک', 'یا', 'هم', 'اما', 'تا', 'کنید', 'شده', 'شود',
            'های', 'کرد', 'شد', 'خود', 'ما', 'شما', 'او', 'آنها', 'همه',
            'هر', 'اگر', 'نیز', 'دیگر', 'بسیار', 'چه', 'هستند', 'بی', 'من',
            'تو', 'بر', 'همین', 'هیچ', 'دو', 'چون', 'پیش', 'بین', 'چیست',
            'کردن', 'کردم', 'کنم', 'کنی', 'کند', 'کنیم', 'کنید', 'کنند'
        ]

def setup_content_handlers(dispatcher) -> None:
    """تنظیم هندلرهای تحلیل محتوا"""
    handler = ContentAnalysisHandler()
    
    dispatcher.add_handler(CommandHandler("content", handler.content_menu))
    dispatcher.add_handler(CallbackQueryHandler(
        handler.handle_content_callback, 
        pattern="^content_"
    ))
    dispatcher.add_handler(MessageHandler(
        Filters.text & ~Filters.command,
        handler.process_content_input,
        pass_user_data=True
    ))
    dispatcher.add_handler(CallbackQueryHandler(
        handler.return_to_main_menu,
        pattern="^content_menu$"
    ))
