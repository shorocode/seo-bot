
# handlers/backlinks.py - مدیریت تحلیل بک‌لینک‌ها

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

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
from services.seo_tools import BacklinkAnalyzer
from utils.decorators import restricted
from utils.helpers import format_number, truncate_text
from utils.logger import logger

class BacklinkHandler:
    def __init__(self):
        self.analyzer = BacklinkAnalyzer(api_key=settings.MOZ_API_KEY)
        self.MAX_RESULTS = 50

    @restricted()
    def backlink_menu(self, update: Update, context: CallbackContext) -> None:
        """نمایش منوی تحلیل بک‌لینک"""
        try:
            buttons = [
                [
                    InlineKeyboardButton("🔍 تحلیل دامنه", callback_data="bl_domain"),
                    InlineKeyboardButton("📊 گزارش کامل", callback_data="bl_full_report")
                ],
                [
                    InlineKeyboardButton("🆚 مقایسه دامنه‌ها", callback_data="bl_compare"),
                    InlineKeyboardButton("📌 ذخیره شده‌ها", callback_data="bl_saved")
                ],
                [get_back_button()]
            ]

            update.message.reply_text(
                text="🔄 لطفا نوع تحلیل بک‌لینک را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        except Exception as e:
            logger.error(f"Error in backlink_menu: {str(e)}", exc_info=True)
            self.send_error_message(update, "نمایش منوی بک‌لینک")

    def handle_backlink_callback(self, update: Update, context: CallbackContext) -> None:
        """مدیریت کلیک‌های منوی بک‌لینک"""
        query = update.callback_query
        query.answer()

        try:
            action = query.data

            if action == "bl_domain":
                self.request_domain_input(query, context)
            elif action == "bl_full_report":
                self.request_full_report(query, context)
            elif action == "bl_compare":
                self.request_compare_input(query, context)
            elif action == "bl_saved":
                self.show_saved_reports(query)
            elif action == "back":
                self.return_to_main_menu(query)

        except Exception as e:
            logger.error(f"Error in backlink callback: {str(e)}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در پردازش درخواست شما رخ داد.")

    def request_domain_input(self, query, context: CallbackContext) -> None:
        """درخواست دامنه برای تحلیل"""
        try:
            context.user_data['backlink_action'] = 'domain_analysis'
            
            query.edit_message_text(
                text="🌐 لطفا دامنه مورد نظر را بدون https:// وارد کنید:\nمثال: example.com",
                reply_markup=InlineKeyboardMarkup([[get_back_button("لغو")]])
            )

        except Exception as e:
            logger.error(f"Error requesting domain input: {str(e)}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در دریافت دامنه رخ داد.")

    def request_full_report(self, query, context: CallbackContext) -> None:
        """درخواست گزارش کامل"""
        try:
            context.user_data['backlink_action'] = 'full_report'
            
            query.edit_message_text(
                text="📋 لطفا دامنه مورد نظر برای گزارش کامل را وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[get_back_button("لغو")]])
            )

        except Exception as e:
            logger.error(f"Error requesting full report: {str(e)}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در دریافت درخواست گزارش رخ داد.")

    def request_compare_input(self, query, context: CallbackContext) -> None:
        """درخواست دامنه‌ها برای مقایسه"""
        try:
            context.user_data['backlink_action'] = 'compare_domains'
            context.user_data['compare_step'] = 1
            context.user_data['domains'] = []
            
            query.edit_message_text(
                text="🔢 لطفا دامنه اول را برای مقایسه وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[get_back_button("لغو")]])
            )

        except Exception as e:
            logger.error(f"Error requesting compare input: {str(e)}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در دریافت دامنه‌ها رخ داد.")

    def process_domain_input(self, update: Update, context: CallbackContext) -> None:
        """پردازش دامنه وارد شده"""
        try:
            domain = update.message.text.strip().lower()
            
            if not self.validate_domain(domain):
                update.message.reply_text("⚠️ فرمت دامنه نامعتبر است. لطفا دامنه را بدون https:// وارد کنید.")
                return

            action = context.user_data.get('backlink_action')
            
            if action == 'domain_analysis':
                self.analyze_domain(update, context, domain)
            elif action == 'full_report':
                self.generate_full_report(update, context, domain)
            elif action == 'compare_domains':
                self.process_compare_step(update, context, domain)
            else:
                update.message.reply_text("⚠️ درخواست نامعتبر")

        except Exception as e:
            logger.error(f"Error processing domain input: {str(e)}", exc_info=True)
            self.send_error_message(update, "پردازش دامنه")

    def validate_domain(self, domain: str) -> bool:
        """اعتبارسنجی فرمت دامنه"""
        if not domain or ' ' in domain:
            return False
            
        # حذف پروتکل و مسیرها در صورت وجود
        domain = domain.replace('https://', '').replace('http://', '').split('/')[0]
        
        # بررسی وجود حداقل یک نقطه و کاراکترهای مجاز
        return '.' in domain and all(c.isalnum() or c in ['.', '-'] for c in domain)

    def analyze_domain(self, update: Update, context: CallbackContext, domain: str) -> None:
        """تحلیل اولیه دامنه"""
        try:
            update.message.reply_text(f"🔍 در حال تحلیل دامنه {domain}...")
            
            # دریافت داده‌های اولیه
            summary = self.analyzer.get_domain_summary(domain)
            
            if not summary:
                update.message.reply_text("⚠️ اطلاعاتی برای این دامنه یافت نشد.")
                return

            # ایجاد گزارش خلاصه
            report = [
                f"📊 *نتایج تحلیل {domain}*",
                f"🔗 تعداد بک‌لینک: {format_number(summary.get('backlinks', 0))}",
                f"⭐ اعتبار دامنه: {summary.get('domain_authority', 0)}",
                f"🚀 اعتبار صفحه: {summary.get('page_authority', 0)}",
                f"🔝 دامنه‌های ارجاع دهنده: {format_number(summary.get('referring_domains', 0))}",
                "\n💡 برای گزارش کامل از منوی بک‌لینک استفاده کنید."
            ]

            buttons = [
                [InlineKeyboardButton("💾 ذخیره گزارش", callback_data=f"save_report:{domain}")],
                [get_back_button()]
            ]

            update.message.reply_text(
                text="\n".join(report),
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN
            )

            # ذخیره در تاریخچه
            if db and update.effective_user:
                db.save_backlink_query(
                    user_id=update.effective_user.id,
                    domain=domain,
                    result=str(summary)
                )

        except Exception as e:
            logger.error(f"Error analyzing domain: {str(e)}", exc_info=True)
            self.send_error_message(update, "تحلیل دامنه")

    def generate_full_report(self, update: Update, context: CallbackContext, domain: str) -> None:
        """تولید گزارش کامل بک‌لینک"""
        try:
            update.message.reply_text(f"⏳ در حال تهیه گزارش کامل برای {domain}...")
            
            # دریافت گزارش کامل
            report = self.analyzer.get_full_report(domain)
            
            if not report:
                update.message.reply_text("⚠️ اطلاعاتی برای این دامنه یافت نشد.")
                return

            # تقسیم گزارش به بخش‌های کوچکتر
            self.send_report_in_parts(update, domain, report)

            # ذخیره در تاریخچه
            if db and update.effective_user:
                db.save_backlink_query(
                    user_id=update.effective_user.id,
                    domain=domain,
                    result="FULL_REPORT"
                )

        except Exception as e:
            logger.error(f"Error generating full report: {str(e)}", exc_info=True)
            self.send_error_message(update, "تهیه گزارش کامل")

    def send_report_in_parts(self, update: Update, domain: str, report: Dict) -> None:
        """ارسال گزارش به صورت بخش‌بندی شده"""
        try:
            # خلاصه گزارش
            summary = [
                f"📋 *گزارش کامل بک‌لینک {domain}*",
                f"🔗 تعداد کل بک‌لینک‌ها: {format_number(report.get('total_backlinks', 0))}",
                f"🌐 دامنه‌های ارجاع دهنده: {format_number(report.get('referring_domains', 0))}",
                f"⭐ اعتبار دامنه (DA): {report.get('domain_authority', 0)}",
                f"🚀 اعتبار صفحه (PA): {report.get('page_authority', 0)}",
                "\n🔍 *بررسی جزئیات:*"
            ]

            update.message.reply_text(
                text="\n".join(summary),
                parse_mode=ParseMode.MARKDOWN
            )

            # ارسال 5 بک‌لینک برتر
            top_backlinks = report.get('top_backlinks', [])[:5]
            if top_backlinks:
                top_text = ["\n🏆 *برترین بک‌لینک‌ها:*"]
                for i, link in enumerate(top_backlinks, 1):
                    top_text.append(
                        f"{i}. [{truncate_text(link.get('url', ''), 30)}]({link.get('url', '')}) - "
                        f"DA: {link.get('domain_authority', 'N/A')}"
                    )
                
                update.message.reply_text(
                    text="\n".join(top_text),
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True
                )

            # ارسال 5 دامنه ارجاع دهنده برتر
            top_domains = report.get('top_referring_domains', [])[:5]
            if top_domains:
                domains_text = ["\n🌍 *برترین دامنه‌های ارجاع دهنده:*"]
                for i, domain_data in enumerate(top_domains, 1):
                    domains_text.append(
                        f"{i}. {domain_data.get('domain', 'N/A')} - "
                        f"بک‌لینک‌ها: {format_number(domain_data.get('backlinks', 0))}"
                    )
                
                update.message.reply_text(text="\n".join(domains_text))

            # دکمه‌های اقدام
            buttons = [
                [
                    InlineKeyboardButton("📥 دریافت فایل کامل", callback_data=f"download_report:{domain}"),
                    InlineKeyboardButton("💾 ذخیره گزارش", callback_data=f"save_full_report:{domain}")
                ],
                [get_back_button()]
            ]

            update.message.reply_text(
                text="برای دریافت گزارش کامل به صورت فایل یا ذخیره گزارش از دکمه‌های زیر استفاده کنید:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        except Exception as e:
            logger.error(f"Error sending report parts: {str(e)}", exc_info=True)
            raise

    def process_compare_step(self, update: Update, context: CallbackContext, domain: str) -> None:
        """پردازش مراحل مقایسه دامنه‌ها"""
        try:
            step = context.user_data.get('compare_step', 1)
            domains = context.user_data.get('domains', [])
            
            domains.append(domain)
            context.user_data['domains'] = domains
            
            if step == 1:
                context.user_data['compare_step'] = 2
                update.message.reply_text(
                    text="🔢 لطفا دامنه دوم را برای مقایسه وارد کنید:",
                    reply_markup=InlineKeyboardMarkup([[get_back_button("لغو")]])
                )
            else:
                self.compare_domains(update, context, domains)

        except Exception as e:
            logger.error(f"Error in compare step: {str(e)}", exc_info=True)
            self.send_error_message(update, "پردازش مقایسه")

    def compare_domains(self, update: Update, context: CallbackContext, domains: List[str]) -> None:
        """مقایسه دو دامنه"""
        try:
            if len(domains) < 2:
                update.message.reply_text("⚠️ حداقل به دو دامنه برای مقایسه نیاز است.")
                return

            update.message.reply_text(f"⚖️ در حال مقایسه {domains[0]} و {domains[1]}...")
            
            # دریافت داده‌های مقایسه
            comparison = self.analyzer.compare_domains(domains[0], domains[1])
            
            if not comparison:
                update.message.reply_text("⚠️ خطایی در مقایسه دامنه‌ها رخ داد.")
                return

            # ایجاد گزارش مقایسه
            report = [
                f"📊 *نتایج مقایسه {domains[0]} و {domains[1]}*",
                "\n🔗 *بک‌لینک‌ها:*",
                f"{domains[0]}: {format_number(comparison.get('domain1', {}).get('backlinks', 0))}",
                f"{domains[1]}: {format_number(comparison.get('domain2', {}).get('backlinks', 0))}",
                f"تفاوت: {format_number(abs(comparison.get('backlinks_diff', 0))}",
                
                "\n🌐 *دامنه‌های ارجاع دهنده:*",
                f"{domains[0]}: {format_number(comparison.get('domain1', {}).get('referring_domains', 0))}",
                f"{domains[1]}: {format_number(comparison.get('domain2', {}).get('referring_domains', 0))}",
                f"تفاوت: {format_number(abs(comparison.get('referring_domains_diff', 0)))}",
                
                "\n⭐ *اعتبار دامنه (DA):*",
                f"{domains[0]}: {comparison.get('domain1', {}).get('domain_authority', 0)}",
                f"{domains[1]}: {comparison.get('domain2', {}).get('domain_authority', 0)}",
                f"تفاوت: {abs(comparison.get('da_diff', 0))}",
            ]

            buttons = [
                [InlineKeyboardButton("📈 نمودار مقایسه", callback_data=f"compare_chart:{domains[0]}:{domains[1]}")],
                [get_back_button()]
            ]

            update.message.reply_text(
                text="\n".join(report),
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN
            )

            # ذخیره در تاریخچه
            if db and update.effective_user:
                db.save_backlink_query(
                    user_id=update.effective_user.id,
                    domain=f"{domains[0]} vs {domains[1]}",
                    result=str(comparison)
                )

        except Exception as e:
            logger.error(f"Error comparing domains: {str(e)}", exc_info=True)
            self.send_error_message(update, "مقایسه دامنه‌ها")

    def show_saved_reports(self, query) -> None:
        """نمایش گزارشات ذخیره شده"""
        try:
            if not db or not query.from_user:
                query.edit_message_text("⚠️ قابلیت ذخیره سازی فعال نیست.")
                return

            saved_reports = db.get_user_saved_reports(query.from_user.id)
            
            if not saved_reports:
                query.edit_message_text("📭 هیچ گزارشی ذخیره نکرده‌اید.")
                return

            buttons = []
            for report in saved_reports[:10]:  # محدودیت نمایش 10 مورد
                buttons.append([
                    InlineKeyboardButton(
                        text=f"📌 {report.get('domain', 'Unknown')}",
                        callback_data=f"view_saved:{report['id']}"
                    )
                ])

            buttons.append([get_back_button()])

            query.edit_message_text(
                text="📂 گزارشات ذخیره شده شما:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        except Exception as e:
            logger.error(f"Error showing saved reports: {str(e)}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در دریافت گزارشات ذخیره شده رخ داد.")

    def send_error_message(self, update: Update, action: str) -> None:
        """ارسال پیام خطای استاندارد"""
        if update.message:
            update.message.reply_text(f"⚠️ خطایی در {action} رخ داد.")

    def return_to_main_menu(self, query) -> None:
        """بازگشت به منوی اصلی بک‌لینک"""
        try:
            buttons = [
                [
                    InlineKeyboardButton("🔍 تحلیل دامنه", callback_data="bl_domain"),
                    InlineKeyboardButton("📊 گزارش کامل", callback_data="bl_full_report")
                ],
                [
                    InlineKeyboardButton("🆚 مقایسه دامنه‌ها", callback_data="bl_compare"),
                    InlineKeyboardButton("📌 ذخیره شده‌ها", callback_data="bl_saved")
                ],
                [get_back_button("منوی اصلی")]
            ]

            query.edit_message_text(
                text="🔄 لطفا نوع تحلیل بک‌لینک را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        except Exception as e:
            logger.error(f"Error returning to main menu: {str(e)}", exc_info=True)
            query.edit_message_text("⚠️ خطایی در بازگشت به منوی اصلی رخ داد.")

def setup_backlink_handlers(dispatcher) -> None:
    """تنظیم هندلرهای تحلیل بک‌لینک"""
    handler = BacklinkHandler()
    
    dispatcher.add_handler(CommandHandler("backlinks", handler.backlink_menu))
    dispatcher.add_handler(CallbackQueryHandler(
        handler.handle_backlink_callback, 
        pattern="^bl_"
    ))
    dispatcher.add_handler(CallbackQueryHandler(
        handler.handle_backlink_callback, 
        pattern="^view_saved:"
    ))
    dispatcher.add_handler(CallbackQueryHandler(
        handler.handle_backlink_callback, 
        pattern="^download_report:"
    ))
    dispatcher.add_handler(CallbackQueryHandler(
        handler.handle_backlink_callback, 
        pattern="^save_"
    ))
    dispatcher.add_handler(CallbackQueryHandler(
        handler.handle_backlink_callback, 
        pattern="^compare_chart:"
    ))
    dispatcher.add_handler(MessageHandler(
        Filters.text & ~Filters.command,
        handler.process_domain_input,
        pass_user_data=True
    ))
