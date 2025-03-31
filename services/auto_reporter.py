from typing import Dict, List, Optional, Union, BinaryIO
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from config import settings
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InputFile, ParseMode
from aiogram.utils import executor
from aiohttp import ClientSession
import matplotlib.pyplot as plt
import seaborn as sns
import tempfile
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ReportStates(StatesGroup):
    """FSM states for report generation"""
    waiting_for_email = State()
    waiting_for_date_range = State()
    waiting_for_report_type = State()

class AutoReporter:
    """Automated reporting system with advanced features"""
    
    def __init__(self):
        self.smtp_config = {
            'server': settings.SMTP_SERVER,
            'port': settings.SMTP_PORT,
            'username': settings.SMTP_USERNAME,
            'password': settings.SMTP_PASSWORD
        }
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher(self.bot, storage=MemoryStorage())
        self._register_handlers()
        
        # Initialize with default values
        self.report_types = {
            'daily': {
                'name': 'گزارش روزانه',
                'time_range': timedelta(days=1)
            },
            'weekly': {
                'name': 'گزارش هفتگی',
                'time_range': timedelta(weeks=1)
            },
            'monthly': {
                'name': 'گزارش ماهانه',
                'time_range': timedelta(days=30)
            }
        }

    def _register_handlers(self):
        """Register all Telegram bot handlers"""
        self.dp.register_message_handler(
            self.start_command, 
            commands=['start']
        )
        self.dp.register_message_handler(
            self.generate_report_command, 
            commands=['report']
        )
        self.dp.register_message_handler(
            self.handle_email_input, 
            state=ReportStates.waiting_for_email
        )
        self.dp.register_message_handler(
            self.handle_date_range_input, 
            state=ReportStates.waiting_for_date_range
        )
        self.dp.register_message_handler(
            self.handle_report_type_input, 
            state=ReportStates.waiting_for_report_type
        )
        self.dp.register_callback_query_handler(
            self.process_report_callback,
            lambda c: c.data.startswith('report_')
        )

    async def start_command(self, message: types.Message):
        """Handle /start command"""
        welcome_text = (
            "🤖 به ربات گزارش‌دهی سئو خوش آمدید!\n\n"
            "🔹 برای دریافت گزارش از دستور /report استفاده کنید\n"
            "🔹 می‌توانید گزارش‌های روزانه، هفتگی یا ماهانه دریافت کنید\n"
            "🔹 گزارش‌ها به صورت فایل اکسل و ایمیل ارسال می‌شوند"
        )
        await message.answer(welcome_text)

    async def generate_report_command(self, message: types.Message):
        """Handle /report command"""
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        buttons = [
            types.InlineKeyboardButton(
                text=f"📊 {info['name']}", 
                callback_data=f"report_{rtype}"
            ) for rtype, info in self.report_types.items()
        ]
        keyboard.add(*buttons)
        
        await message.answer(
            "لطفا نوع گزارش مورد نظر را انتخاب کنید:",
            reply_markup=keyboard
        )

    async def process_report_callback(self, callback_query: types.CallbackQuery):
        """Process report type selection"""
        report_type = callback_query.data.split('_')[1]
        await self.bot.answer_callback_query(callback_query.id)
        
        if report_type == 'custom':
            await ReportStates.waiting_for_date_range.set()
            await self.bot.send_message(
                callback_query.from_user.id,
                "لطفا بازه زمانی را به صورت زیر وارد کنید:\n"
                "مثال: 1402/01/01-1402/01/07"
            )
        else:
            await self._generate_and_send_report(
                callback_query.from_user.id,
                report_type
            )

    async def handle_email_input(self, message: types.Message, state: FSMContext):
        """Handle email address input"""
        if not self._validate_email(message.text):
            await message.answer("لطفا یک ایمیل معتبر وارد کنید:")
            return
            
        async with state.proxy() as data:
            data['email'] = message.text
            report_type = data.get('report_type', 'daily')
            
        await state.finish()
        await self._generate_and_send_report(
            message.from_user.id,
            report_type,
            email=message.text
        )

    async def handle_date_range_input(self, message: types.Message, state: FSMContext):
        """Handle custom date range input"""
        try:
            start_date, end_date = message.text.split('-')
            start_date = datetime.strptime(start_date.strip(), '%Y/%m/%d')
            end_date = datetime.strptime(end_date.strip(), '%Y/%m/%d')
            
            if start_date > end_date:
                raise ValueError("تاریخ شروع باید قبل از تاریخ پایان باشد")
                
            async with state.proxy() as data:
                data['start_date'] = start_date
                data['end_date'] = end_date
                
            await ReportStates.waiting_for_email.set()
            await message.answer(
                "لطفا آدرس ایمیل خود را برای دریافت گزارش وارد کنید:"
            )
            
        except Exception as e:
            await message.answer(
                f"قالب تاریخ نامعتبر است. لطفا به فرمت زیر وارد کنید:\n"
                f"مثال: 1402/01/01-1402/01/07\n\n"
                f"خطا: {str(e)}"
            )

    async def handle_report_type_input(self, message: types.Message, state: FSMContext):
        """Handle report type input"""
        report_type = message.text.lower()
        if report_type not in self.report_types:
            await message.answer(
                "نوع گزارش نامعتبر است. لطفا یکی از گزینه‌های زیر را وارد کنید:\n"
                f"{', '.join(self.report_types.keys())}"
            )
            return
            
        async with state.proxy() as data:
            data['report_type'] = report_type
            
        await ReportStates.waiting_for_email.set()
        await message.answer(
            "لطفا آدرس ایمیل خود را برای دریافت گزارش وارد کنید:"
        )

    async def _generate_and_send_report(
        self,
        user_id: int,
        report_type: str,
        email: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        """Generate and send report to user"""
        await self.bot.send_chat_action(user_id, 'typing')
        
        try:
            # Generate report
            report_data = await self.generate_report(
                user_id,
                report_type,
                start_date,
                end_date
            )
            
            # Send via Telegram
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                tmp.write(report_data.getvalue())
                tmp_path = tmp.name
                
            try:
                await self.bot.send_document(
                    user_id,
                    InputFile(tmp_path),
                    caption=f"📄 گزارش {self.report_types[report_type]['name']}"
                )
            finally:
                os.unlink(tmp_path)
            
            # Send via email if provided
            if email:
                success = await self.send_report_email(
                    email,
                    report_data,
                    report_type
                )
                if success:
                    await self.bot.send_message(
                        user_id,
                        f"📧 گزارش به ایمیل {email} نیز ارسال شد"
                    )
                else:
                    await self.bot.send_message(
                        user_id,
                        "❌ ارسال گزارش به ایمیل با خطا مواجه شد"
                    )
                    
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}", exc_info=True)
            await self.bot.send_message(
                user_id,
                f"❌ خطا در تولید گزارش: {str(e)}"
            )

    async def generate_report(
        self,
        user_id: int,
        report_type: str = "daily",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> BytesIO:
        """Generate comprehensive report with visualizations"""
        try:
            # Fetch data based on time range
            if report_type == 'custom' and start_date and end_date:
                time_range = (start_date, end_date)
            else:
                time_range = (
                    datetime.now() - self.report_types[report_type]['time_range'],
                    datetime.now()
                )
                
            data = await self._fetch_report_data(user_id, *time_range)
            
            if not data:
                raise ValueError("داده‌ای برای نمایش یافت نشد")
            
            # Create DataFrame
            df = pd.DataFrame(data)
            
            # Generate visualizations
            self._generate_charts(df)
            
            # Create Excel file in memory
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Data', index=False)
                
                # Add summary statistics
                df.describe().to_excel(writer, sheet_name='Summary')
                
                # Add charts to Excel
                workbook = writer.book
                worksheet = writer.sheets['Data']
                
                # Insert saved charts
                for i, chart_path in enumerate(self._get_chart_paths()):
                    worksheet.insert_image(
                        f'K{2 + i * 20}',
                        chart_path,
                        {'x_scale': 0.5, 'y_scale': 0.5}
                    )
                
                # Formatting
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'fg_color': '#D7E4BC',
                    'border': 1
                })
                
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                    worksheet.set_column(col_num, col_num, max(len(str(value)) + 2, 20)
            
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}", exc_info=True)
            raise

    def _generate_charts(self, df: pd.DataFrame):
        """Generate visualizations for the report"""
        plt.style.use('seaborn')
        
        # Create temp directory for charts
        if not os.path.exists('temp_charts'):
            os.makedirs('temp_charts')
        
        # Plot 1: Trend analysis
        if 'date' in df.columns and 'visits' in df.columns:
            plt.figure(figsize=(10, 6))
            sns.lineplot(x='date', y='visits', data=df)
            plt.title('Trend Analysis')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig('temp_charts/trend_analysis.png')
            plt.close()
        
        # Plot 2: Top pages
        if 'page' in df.columns and 'visits' in df.columns:
            plt.figure(figsize=(10, 6))
            df.nlargest(10, 'visits').plot.bar(x='page', y='visits')
            plt.title('Top Pages by Visits')
            plt.tight_layout()
            plt.savefig('temp_charts/top_pages.png')
            plt.close()

    def _get_chart_paths(self) -> List[str]:
        """Get paths of generated charts"""
        return [
            os.path.join('temp_charts', f)
            for f in os.listdir('temp_charts')
            if f.endswith('.png')
        ]

    async def _fetch_report_data(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Fetch report data from database or API"""
        # This should be implemented based on your data source
        # Mock data for demonstration
        return [
            {
                'date': (start_date + timedelta(days=i)).strftime('%Y-%m-%d'),
                'visits': 1000 + i * 100,
                'page': f'/page-{i}',
                'conversion_rate': 0.05 + i * 0.01
            }
            for i in range((end_date - start_date).days + 1)
        ]

    async def send_report_email(
        self,
        to_email: str,
        report_data: Union[BytesIO, BinaryIO],
        report_type: str = "daily"
    ) -> bool:
        """Send report via email with improved formatting"""
        try:
            msg = MIMEMultipart()
            msg['From'] = settings.EMAIL_FROM
            msg['To'] = to_email
            msg['Subject'] = (
                f"{self.report_types[report_type]['name']} سئو - "
                f"{datetime.now().strftime('%Y/%m/%d')}"
            )
            
            # Add HTML body
            html = f"""
            <html>
                <body>
                    <h2>گزارش {self.report_types[report_type]['name']} سئو</h2>
                    <p>تاریخ تولید: {datetime.now().strftime('%Y/%m/%d %H:%M')}</p>
                    <p>این گزارش به صورت خودکار تولید شده است.</p>
                </body>
            </html>
            """
            msg.attach(MIMEText(html, 'html'))
            
            # Add attachment
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(report_data.getvalue())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="seo_report_{datetime.now().date()}.xlsx"'
            )
            msg.attach(part)
            
            # Connect and send
            with smtplib.SMTP_SSL(
                self.smtp_config['server'],
                self.smtp_config['port']
            ) as server:
                server.login(
                    self.smtp_config['username'],
                    self.smtplib_config['password']
                )
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            logger.error(f"Email sending failed: {str(e)}", exc_info=True)
            return False

    def _validate_email(self, email: str) -> bool:
        """Simple email validation"""
        return '@' in email and '.' in email.split('@')[-1]

    async def run(self):
        """Run the bot"""
        await self.dp.start_polling()

# Initialize and run the bot
if __name__ == '__main__':
    reporter = AutoReporter()
    asyncio.run(reporter.run())
