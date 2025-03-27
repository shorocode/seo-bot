import logging
from telegram import Update
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    Dispatcher,
    CallbackContext,
)
from functools import partial
from typing import Callable, Dict, Any

# Import modules
from config import settings
from config.keyboards import (
    get_main_menu_keyboard,
    get_category_keyboard,
    get_tool_keyboard,
)
from utils.logger import configure_logging
from utils.decorators import restricted, log_activity
from services.database import init_db
from services.cache import init_cache
from handlers import (
    admin,
    content,
    technical,
    backlinks,
    competition,
)

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)

class SEOToolsBot:
    def __init__(self):
        self.updater = Updater(settings.TELEGRAM_TOKEN, workers=settings.WORKERS)
        self.dispatcher: Dispatcher = self.updater.dispatcher
        self.handlers = {
            'content': content,
            'technical': technical,
            'backlinks': backlinks,
            'competition': competition,
        }
        
        # Initialize services
        init_db()
        init_cache()
        
        # Register handlers
        self._register_handlers()
        
    def _register_handlers(self):
        """Register all handlers"""
        # Command handlers
        self.dispatcher.add_handler(CommandHandler("start", self._start))
        self.dispatcher.add_handler(CommandHandler("admin", admin.admin_panel))
        
        # Category handlers
        for category in self.handlers.keys():
            self.dispatcher.add_handler(
                CallbackQueryHandler(
                    partial(self._handle_category, category=category),
                    pattern=f"^{category}$"
                )
            )
        
        # Tool handlers
        for category, handler_module in self.handlers.items():
            for tool in handler_module.TOOLS:
                self.dispatcher.add_handler(
                    CallbackQueryHandler(
                        partial(self._handle_tool, category=category),
                        pattern=f"^{tool['id']}$"
                    )
                )
        
        # Message handler
        self.dispatcher.add_handler(
            MessageHandler(
                Filters.text & ~Filters.command,
                self._process_input
            )
        )
        
        # Error handler
        self.dispatcher.add_error_handler(self._error_handler)
    
    @log_activity
    def _start(self, update: Update, context: CallbackContext):
        """Send main menu with glass buttons"""
        user = update.effective_user
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"👋 سلام {user.first_name}!\n\n🛠️ *ابزارهای سئو* را انتخاب کنید:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    @log_activity
    def _handle_category(self, update: Update, context: CallbackContext, category: str):
        """Show tools for selected category"""
        query = update.callback_query
        query.answer()
        
        handler_module = self.handlers.get(category)
        if not handler_module:
            query.edit_message_text("⚠️ دسته بندی یافت نشد!")
            return
        
        query.edit_message_text(
            text=f"🔧 *{handler_module.CATEGORY_NAME}* را انتخاب کنید:",
            reply_markup=get_category_keyboard(handler_module.TOOLS),
            parse_mode='Markdown'
        )
    
    @log_activity
    def _handle_tool(self, update: Update, context: CallbackContext, category: str):
        """Handle tool selection"""
        query = update.callback_query
        query.answer()
        
        tool_id = query.data
        handler_module = self.handlers.get(category)
        if not handler_module:
            query.edit_message_text("⚠️ دسته بندی یافت نشد!")
            return
        
        tool = next((t for t in handler_module.TOOLS if t['id'] == tool_id), None)
        if not tool:
            query.edit_message_text("⚠️ ابزار یافت نشد!")
            return
        
        # Store selected tool in user data
        context.user_data['current_tool'] = {
            'category': category,
            'id': tool_id,
            'handler': tool.get('handler')
        }
        
        # Get input prompt
        input_prompt = tool.get('input_prompt', 'لطفا ورودی مورد نیاز را ارسال کنید:')
        query.edit_message_text(input_prompt)
    
    @log_activity
    def _process_input(self, update: Update, context: CallbackContext):
        """Process user input for selected tool"""
        user_input = update.message.text
        user_data = context.user_data.get('current_tool', {})
        
        if not user_data:
            update.message.reply_text("⚠️ لطفا ابتدا یک ابزار را از منو انتخاب کنید.")
            return
        
        category = user_data.get('category')
        tool_id = user_data.get('id')
        handler_func = user_data.get('handler')
        
        if not all([category, tool_id, handler_func]):
            update.message.reply_text("⚠️ اطلاعات ابزار نامعتبر است!")
            return
        
        try:
            # Call the appropriate handler function
            handler_module = self.handlers.get(category)
            result = handler_func(update, context, user_input)
            
            # Send result to user
            if result:
                update.message.reply_text(
                    f"✅ نتیجه تحلیل:\n\n{result}",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error processing tool {tool_id}: {str(e)}")
            update.message.reply_text("⚠️ خطایی در پردازش درخواست رخ داد. لطفا مجددا تلاش کنید.")
    
    def _error_handler(self, update: Update, context: CallbackContext):
        """Log errors and notify admins"""
        logger.error(f"Update {update} caused error {context.error}")
        
        # Notify admins
        for admin_id in settings.ADMINS:
            context.bot.send_message(
                chat_id=admin_id,
                text=f"⚠️ خطا در ربات:\n\n{context.error}"
            )
    
    def run(self):
        """Run the bot"""
        logger.info("Starting SEO Tools Bot...")
        if settings.WEBHOOK_MODE:
            self.updater.start_webhook(
                listen="0.0.0.0",
                port=settings.PORT,
                url_path=settings.TELEGRAM_TOKEN,
                webhook_url=f"{settings.WEBHOOK_URL}/{settings.TELEGRAM_TOKEN}"
            )
            logger.info(f"Webhook mode started at {settings.WEBHOOK_URL}")
        else:
            self.updater.start_polling()
            logger.info("Polling mode started")
        
        self.updater.idle()

if __name__ == '__main__':
    bot = SEOToolsBot()
    bot.run()
