from typing import Dict, List
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from config import settings
import logging

logger = logging.getLogger(__name__)

class AutoReporter:
    """سیستم تولید و ارسال خودکار گزارش‌ها"""
    
    def __init__(self):
        self.smtp_config = {
            'server': settings.SMTP_SERVER,
            'port': settings.SMTP_PORT,
            'username': settings.SMTP_USERNAME,
            'password': settings.SMTP_PASSWORD
        }

    async def generate_daily_report(self, user_id: int) -> BytesIO:
        """تولید گزارش روزانه"""
        try:
            # جمع‌آوری داده‌ها از دیتابیس
            data = await self._fetch_report_data(user_id)
            
            # ایجاد DataFrame
            df = pd.DataFrame(data)
            
            # ساخت اکسل در حافظه
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='SEO Report')
                
                # فرمت‌بندی پیشرفته
                workbook = writer.book
                worksheet = writer.sheets['SEO Report']
                
                # اضافه کردن نمودار
                chart = workbook.add_chart({'type': 'column'})
                chart.add_series({
                    'values': '=SEO Report!$B$2:$B$10',
                    'categories': '=SEO Report!$A$2:$A$10'
                })
                worksheet.insert_chart('D2', chart)
            
            output.seek(0)
            return output
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}")
            raise

    async def send_report_email(
        self,
        to_email: str,
        report_data: BytesIO,
        report_type: str = "daily"
    ) -> bool:
        """ارسال گزارش از طریق ایمیل"""
        msg = MIMEMultipart()
        msg['From'] = settings.EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = f"SEO {report_type.capitalize()} Report - {datetime.now().date()}"
        
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(report_data.getvalue())
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename="seo_report_{datetime.now().date()}.xlsx"'
        )
        msg.attach(part)
        
        try:
            with smtplib.SMTP_SSL(
                self.smtp_config['server'],
                self.smtp_config['port']
            ) as server:
                server.login(
                    self.smtp_config['username'],
                    self.smtp_config['password']
                )
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Email sending failed: {str(e)}")
            return False

# نمونه Singleton
auto_reporter = AutoReporter()
