from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO
from config import settings
from services.database import db
import logging

logger = logging.getLogger(__name__)

class ReportGenerator:
    """سیستم تولید گزارش‌های حرفه‌ای"""
    
    def __init__(self):
        self.cache = {}

    async def generate_seo_report(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        report_type: str = "full"
    ) -> BytesIO:
        """تولید گزارش سئو"""
        cache_key = f"report_{user_id}_{start_date.date()}_{end_date.date()}_{report_type}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        data = await self._fetch_report_data(user_id, start_date, end_date)
        report = self._format_report(data, report_type)
        
        # کش کردن به مدت 1 ساعت
        self.cache[cache_key] = report
        asyncio.get_event_loop().call_later(
            3600, lambda: self.cache.pop(cache_key, None)
            
        return report

    async def _fetch_report_data(self, user_id: int, start: datetime, end: datetime) -> Dict:
        """دریافت داده‌های گزارش از دیتابیس"""
        async with db.session() as session:
            results = await session.execute(
                """
                SELECT tool_id, COUNT(*) as count, 
                       AVG(LENGTH(result)) as avg_length
                FROM analysis_results
                WHERE user_id = :user_id 
                AND created_at BETWEEN :start AND :end
                GROUP BY tool_id
                """,
                {"user_id": user_id, "start": start, "end": end}
            )
            return {row.tool_id: row._asdict() for row in results}

    def _format_report(self, data: Dict, report_type: str) -> BytesIO:
        """قالب‌بندی گزارش به صورت Excel"""
        df = pd.DataFrame.from_dict(data, orient='index')
        
        with BytesIO() as output:
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='SEO Report')
                
                # فرمت‌بندی پیشرفته
                workbook = writer.book
                worksheet = writer.sheets['SEO Report']
                
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'fg_color': '#4472C4',
                    'font_color': 'white',
                    'border': 1
                })
                
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num + 1, value, header_format)
                    
            output.seek(0)
            return output

# نمونه Singleton از گزارش‌گر
report_generator = ReportGenerator()
