# handlers/competition.py - مدیریت تحلیل رقابت‌سنجی (نسخه نهایی)

import logging
import re
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ParseMode,
    InputFile
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
from services.seo_tools import CompetitionAnalyzer
from utils.decorators import restricted
from utils.helpers import format_number, truncate_text
from utils.logger import logger
from utils.visualization import generate_comparison_chart


class CompetitionState(Enum):
    """وضعیت‌های مختلف فرآیند تحلیل رقابتی"""
    IDLE = auto()
    AWAITING_DOMAIN = auto()
    AWAITING_KEYWORDS = auto()
    PROCESSING = auto()


class CompetitionReportManager:
    """کلاس مدیریت گزارشات رقابتی"""
    
    @staticmethod
    def generate_competitors_summary(domain: str, competitors: List[Dict]) -> str:
        """تولید خلاصه گزارش رقبا"""
        report = [
            f"🏆 *نتایج تحلیل رقبای {domain}*",
            f"🔍 تعداد رقبای شناسایی شده: {len(competitors)}",
            "\n🏅 *برترین رقبا:*"
        ]

        for i, comp in enumerate(competitors[:5], 1):
            report.append(
                f"{i}. {comp.get('domain', 'N/A')} - "
                f"امتیاز: {comp.get('score', 0)} - "
                f"کلمات مشترک: {comp.get('common_keywords', 0)}"
            )
        
        return "\n".join(report)

    @staticmethod
    def generate_full_report(domain: str, report_data: Dict) -> Tuple[str, str]:
        """تولید گزارش کامل با قالب‌بندی مناسب"""
        summary = [
            f"📋 *گزارش کامل رقابت‌سنجی {domain}*",
            f"🏆 تعداد رقبا: {len(report_data.get('competitors', []))}",
            f"🔑 کلمات کلیدی کل: {format_number(report_data.get('total_keywords', 0))}",
            f"📈 ترافیک تخمینی: {format_number(report_data.get('estimated_traffic', 0))} بازدید ماهانه",
            "\n🔍 *جزئیات رقابت:*"
        ]

        # رقبای برتر
        top_competitors = report_data.get('top_competitors', [])[:5]
        comp_text = ["\n🥇 *برترین رقبا:*"]
        for i, comp in enumerate(top_competitors, 1):
            comp_text.append(
                f"{i}. {comp.get('domain', 'N/A')} - "
                f"امتیاز: {comp.get('competition_level', 'N/A')} - "
                f"کلمات مشترک: {comp.get('common_keywords', 0)}"
            )

        # کلمات کلیدی برتر
        top_keywords = report_data.get('top_keywords', [])[:5]
        kw_text = ["\n🔠 *کلمات کلیدی پرترافیک:*"]
        for i, kw in enumerate(top_keywords, 1):
            kw_text.append(
                f"{i}. {kw.get('keyword', 'N/A')} - "
                f"حجم جستجو: {format_number(kw.get('search_volume', 0))} - "
                f"سختی: {kw.get('difficulty', 'N/A')}"
            )

        return "\n".join(summary), "\n".join(comp_text + kw_text)


class CompetitionValidator:
    """کلاس اعتبارسنجی ورودی‌های تحلیل رقابتی"""
    
    @staticmethod
    def validate_domain(domain: str) -> bool:
        """اعتبارسنجی فرمت دامنه"""
        if not domain or ' ' in domain:
            return False
            
        domain = domain.replace('https://', '').replace('http://', '').split('/')[0]
        pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        return bool(re.match(pattern, domain))

    @staticmethod
    def validate_keywords(keywords: List[str]) -> bool:
        """اعتبارسنجی کلمات کلیدی"""
        return len(keywords) >= 2 and all(kw.strip() for kw in keywords)


class CompetitionHandler:
    """کلاس اصلی مدیریت تحلیل رقابت‌سنجی"""
    
    def __init__(self, analyzer: CompetitionAnalyzer = None):
        self.analyzer = analyzer or CompetitionAnalyzer(api_key=settings.SEMRUSH_API_KEY)
        self.max_competitors = settings.get('MAX_COMPETITORS', 5)
        self.validator = CompetitionValidator()
        self.report_manager = CompetitionReportManager()

    @restricted()
    def competition_menu(self, update: Update, context: CallbackContext) -> None:
        """نمایش منوی رقابت‌سنجی"""
        try:
            buttons = [
                [
                    InlineKeyboardButton("🔍 تحلیل رقبا", callback_data="comp_analyze"),
                    InlineKeyboardButton("📊 گزارش کامل", callback_data="comp_full_report")
                ],
                [
                    InlineKeyboardButton("📈 مقایسه کلیدی", callback_data="comp_compare"),
                    InlineKeyboardButton("📌 ذخیره شده‌ها", callback_data="comp_saved")
                ],
                [get_back_button()]
            ]

            context.user_data['competition_state'] = CompetitionState.IDLE
            update.message.reply_text(
                text="🏆 لطفا نوع تحلیل رقابتی را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        except Exception as e:
            logger.error(f"Error in competition_menu: {str(e)}", exc_info=True)
            self._send_error_message(update, "نمایش منوی رقابت‌سنجی")

    def handle_competition_callback(self, update: Update, context: CallbackContext) -> None:
        """مدیریت کلیک‌های منوی رقابت‌سنجی"""
        query = update.callback_query
        query.answer()

        try:
            action = query.data

            if action == "comp_analyze":
                self._request_target_domain(query, context)
            elif action == "comp_full_report":
                self._request_full_report_domain(query, context)
            elif action == "comp_compare":
                self._request_compare_keywords(query, context)
            elif action == "comp_saved":
                self._show_saved_reports(query)
            elif action.startswith("comp_details:"):
                domain = action.split(":")[1]
                self._show_competitor_details(query, domain)
            elif action.startswith("comp_chart:"):
                domain = action.split(":")[1]
                self._generate_competition_chart(query, domain)
            elif action == "back":
                self._return_to_main_menu(query)

        except Exception as e:
            logger.error(f"Error in competition callback: {str(e)}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در پردازش درخواست شما رخ داد.")

    def _request_target_domain(self, query, context: CallbackContext) -> None:
        """درخواست دامنه هدف برای تحلیل رقبا"""
        try:
            context.user_data['competition_action'] = 'analyze_competitors'
            context.user_data['competition_state'] = CompetitionState.AWAITING_DOMAIN
            
            query.edit_message_text(
                text="🎯 لطفا دامنه اصلی را برای تحلیل رقبا وارد کنید:\nمثال: example.com",
                reply_markup=InlineKeyboardMarkup([[get_back_button("لغو")]])
            )

        except Exception as e:
            logger.error(f"Error requesting target domain: {str(e)}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در دریافت دامنه رخ داد.")

    def _request_full_report_domain(self, query, context: CallbackContext) -> None:
        """درخواست دامنه برای گزارش کامل"""
        try:
            context.user_data['competition_action'] = 'full_report'
            context.user_data['competition_state'] = CompetitionState.AWAITING_DOMAIN
            
            query.edit_message_text(
                text="📋 لطفا دامنه مورد نظر برای گزارش کامل رقابتی را وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[get_back_button("لغو")]])
            )

        except Exception as e:
            logger.error(f"Error requesting full report: {str(e)}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در دریافت درخواست گزارش رخ داد.")

    def _request_compare_keywords(self, query, context: CallbackContext) -> None:
        """درخواست کلمات کلیدی برای مقایسه"""
        try:
            context.user_data['competition_action'] = 'compare_keywords'
            context.user_data['competition_state'] = CompetitionState.AWAITING_KEYWORDS
            
            query.edit_message_text(
                text="🔠 لطفا کلمات کلیدی را با کاما جدا کنید:\nمثال: سئو,میزبانی وب,طراحی سایت",
                reply_markup=InlineKeyboardMarkup([[get_back_button("لغو")]])
            )

        except Exception as e:
            logger.error(f"Error requesting keywords: {str(e)}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در دریافت کلمات کلیدی رخ داد.")

    def process_domain_input(self, update: Update, context: CallbackContext) -> None:
        """پردازش دامنه وارد شده"""
        try:
            domain = update.message.text.strip().lower()
            
            if not self.validator.validate_domain(domain):
                update.message.reply_text("⚠️ فرمت دامنه نامعتبر است. لطفا دامنه را بدون https:// وارد کنید.")
                return

            action = context.user_data.get('competition_action')
            context.user_data['competition_state'] = CompetitionState.PROCESSING
            
            if action == 'analyze_competitors':
                self._analyze_competitors(update, context, domain)
            elif action == 'full_report':
                self._generate_full_report(update, context, domain)
            else:
                update.message.reply_text("⚠️ درخواست نامعتبر")

        except Exception as e:
            logger.error(f"Error processing domain input: {str(e)}", exc_info=True)
            self._send_error_message(update, "پردازش دامنه")
            context.user_data['competition_state'] = CompetitionState.IDLE

    def process_keywords_input(self, update: Update, context: CallbackContext) -> None:
        """پردازش کلمات کلیدی وارد شده"""
        try:
            keywords_text = update.message.text.strip()
            keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]
            
            if not self.validator.validate_keywords(keywords):
                update.message.reply_text("⚠️ حداقل به دو کلمه کلیدی معتبر برای مقایسه نیاز است.")
                return

            context.user_data['competition_state'] = CompetitionState.PROCESSING
            self._compare_keywords(update, context, keywords)

        except Exception as e:
            logger.error(f"Error processing keywords input: {str(e)}", exc_info=True)
            self._send_error_message(update, "پردازش کلمات کلیدی")
            context.user_data['competition_state'] = CompetitionState.IDLE

    def _analyze_competitors(self, update: Update, context: CallbackContext, domain: str) -> None:
        """تحلیل رقبای یک دامنه"""
        try:
            update.message.reply_text(f"🔍 در حال تحلیل رقبای {domain}...")
            
            competitors = self.analyzer.get_competitors(domain, limit=self.max_competitors)
            
            if not competitors:
                update.message.reply_text("⚠️ اطلاعاتی برای این دامنه یافت نشد.")
                return

            report = self.report_manager.generate_competitors_summary(domain, competitors)
            buttons = [
                [InlineKeyboardButton("📊 مشاهده جزئیات", callback_data=f"comp_details:{domain}")],
                [InlineKeyboardButton("📈 نمودار مقایسه", callback_data=f"comp_chart:{domain}")],
                [get_back_button()]
            ]

            update.message.reply_text(
                text=report,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN
            )

            self._save_to_history(update, domain, competitors)

        except Exception as e:
            logger.error(f"Error analyzing competitors: {str(e)}", exc_info=True)
            self._send_error_message(update, "تحلیل رقبا")
        finally:
            context.user_data['competition_state'] = CompetitionState.IDLE

    def _generate_full_report(self, update: Update, context: CallbackContext, domain: str) -> None:
        """تولید گزارش کامل رقابتی"""
        try:
            update.message.reply_text(f"⏳ در حال تهیه گزارش کامل برای {domain}...")
            
            report = self.analyzer.get_full_competition_report(domain)
            
            if not report:
                update.message.reply_text("⚠️ اطلاعاتی برای این دامنه یافت نشد.")
                return

            summary, details = self.report_manager.generate_full_report(domain, report)
            update.message.reply_text(text=summary, parse_mode=ParseMode.MARKDOWN)
            update.message.reply_text(text=details)

            buttons = [
                [
                    InlineKeyboardButton("📥 دریافت فایل کامل", callback_data=f"download_comp_report:{domain}"),
                    InlineKeyboardButton("📊 نمودار رقابت", callback_data=f"comp_full_chart:{domain}")
                ],
                [get_back_button()]
            ]

            update.message.reply_text(
                text="برای دریافت گزارش کامل به صورت فایل یا مشاهده نمودار از دکمه‌های زیر استفاده کنید:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

            self._save_to_history(update, domain, "FULL_REPORT")

        except Exception as e:
            logger.error(f"Error generating full report: {str(e)}", exc_info=True)
            self._send_error_message(update, "تهیه گزارش کامل")
        finally:
            context.user_data['competition_state'] = CompetitionState.IDLE

    def _compare_keywords(self, update: Update, context: CallbackContext, keywords: List[str]) -> None:
        """مقایسه کلمات کلیدی"""
        try:
            update.message.reply_text(f"⚖️ در حال مقایسه کلمات کلیدی...")
            
            comparison = self.analyzer.compare_keywords(keywords)
            
            if not comparison:
                update.message.reply_text("⚠️ خطایی در مقایسه کلمات کلیدی رخ داد.")
                return

            report = [
                f"📊 *نتایج مقایسه کلمات کلیدی*",
                f"🔠 تعداد کلمات: {len(keywords)}",
                "\n📈 *میانگین معیارها:*"
            ]

            for kw, data in comparison.items():
                report.append(
                    f"🔹 {kw}: حجم جستجو: {format_number(data.get('search_volume', 0))}, "
                    f"سختی: {data.get('difficulty', 0)}, "
                    f"CPC: {data.get('cpc', 0)}"
                )

            with generate_comparison_chart(comparison) as chart_file:
                if chart_file:
                    update.message.reply_photo(
                        photo=InputFile(chart_file),
                        caption="📊 نمودار مقایسه کلمات کلیدی"
                    )

            buttons = [
                [InlineKeyboardButton("📥 دریافت داده‌ها", callback_data=f"download_kw_data:{':'.join(keywords)}")],
                [get_back_button()]
            ]

            update.message.reply_text(
                text="\n".join(report),
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN
            )

            self._save_to_history(update, f"KW Compare: {', '.join(keywords)}", comparison)

        except Exception as e:
            logger.error(f"Error comparing keywords: {str(e)}", exc_info=True)
            self._send_error_message(update, "مقایسه کلمات کلیدی")
        finally:
            context.user_data['competition_state'] = CompetitionState.IDLE

    def _show_saved_reports(self, query) -> None:
        """نمایش گزارشات ذخیره شده"""
        try:
            if not db or not query.from_user:
                query.edit_message_text("⚠️ قابلیت ذخیره سازی فعال نیست.")
                return

            saved_reports = db.get_user_saved_competition_reports(query.from_user.id)
            
            if not saved_reports:
                query.edit_message_text("📭 هیچ گزارشی ذخیره نکرده‌اید.")
                return

            buttons = []
            for report in saved_reports[:10]:
                btn_text = truncate_text(report.get('domain', 'Unknown'), 20)
                buttons.append([
                    InlineKeyboardButton(
                        text=f"📌 {btn_text}",
                        callback_data=f"view_comp_saved:{report['id']}"
                    )
                ])

            buttons.append([get_back_button()])

            query.edit_message_text(
                text="📂 گزارشات رقابت‌سنجی ذخیره شده شما:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        except Exception as e:
            logger.error(f"Error showing saved reports: {str(e)}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در دریافت گزارشات ذخیره شده رخ داد.")

    def _generate_competition_chart(self, query, domain: str) -> None:
        """تولید نمودار رقابتی"""
        try:
            query.edit_message_text("📊 در حال تولید نمودار مقایسه...")
            
            competitors = self.analyzer.get_competitors(domain, limit=self.max_competitors)
            if not competitors:
                query.edit_message_text("⚠️ اطلاعاتی برای تولید نمودار یافت نشد.")
                return

            with generate_comparison_chart(competitors) as chart_file:
                if chart_file:
                    query.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=InputFile(chart_file),
                        caption=f"📈 نمودار مقایسه رقبای {domain}"
                    )
                else:
                    query.edit_message_text("⚠️ خطا در تولید نمودار")

        except Exception as e:
            logger.error(f"Error generating competition chart: {str(e)}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در تولید نمودار رخ داد.")

    def _save_to_history(self, update: Update, domain: str, result) -> None:
        """ذخیره در تاریخچه"""
        if db and update.effective_user:
            try:
                db.save_competition_query(
                    user_id=update.effective_user.id,
                    domain=domain,
                    result=str(result)
                )
            except Exception as e:
                logger.error(f"Error saving to history: {str(e)}", exc_info=True)

    def _send_error_message(self, update: Update, action: str) -> None:
        """ارسال پیام خطای استاندارد"""
        if update.message:
            update.message.reply_text(f"⚠️ خطایی در {action} رخ داد. لطفا بعدا تلاش کنید.")

    def _return_to_main_menu(self, query) -> None:
        """بازگشت به منوی اصلی رقابت‌سنجی"""
        try:
            buttons = [
                [
                    InlineKeyboardButton("🔍 تحلیل رقبا", callback_data="comp_analyze"),
                    InlineKeyboardButton("📊 گزارش کامل", callback_data="comp_full_report")
                ],
                [
                    InlineKeyboardButton("📈 مقایسه کلیدی", callback_data="comp_compare"),
                    InlineKeyboardButton("📌 ذخیره شده‌ها", callback_data="comp_saved")
                ],
                [get_back_button("منوی اصلی")]
            ]

            query.edit_message_text(
                text="🏆 لطفا نوع تحلیل رقابتی را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        except Exception as e:
            logger.error(f"Error returning to main menu: {str(e)}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در بازگشت به منوی اصلی رخ داد.")


def setup_competition_handlers(dispatcher) -> None:
    """تنظیم هندلرهای رقابت‌سنجی"""
    handler = CompetitionHandler()
    
    # تنظیم هندلرهای مختلف
    dispatcher.add_handler(CommandHandler("competition", handler.competition_menu))
    
    # هندلرهای callback
    competition_patterns = [
        "^comp_", "^view_comp_saved:", "^download_", "^comp_chart:"
    ]
    for pattern in competition_patterns:
        dispatcher.add_handler(CallbackQueryHandler(
            handler.handle_competition_callback, 
            pattern=pattern
        ))
    
    # هندلرهای پیام
    dispatcher.add_handler(MessageHandler(
        Filters.text & ~Filters.command & 
        Filters.chat_type.private,
        handler.process_domain_input,
        pass_user_data=True
    ))
    
    dispatcher.add_handler(MessageHandler(
        Filters.text & ~Filters.command & 
        Filters.chat_type.private,
        handler.process_keywords_input,
        pass_user_data=True
    ))
