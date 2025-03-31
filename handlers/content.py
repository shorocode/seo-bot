from telegram import Update
from telegram.ext import CallbackContext
from collections import Counter
from services.ai import analyze_with_ai
from services.database import save_result
from utils.decorators import log_activity
from utils.logger import logger
from typing import Dict, List

CATEGORY_NAME = "📝 تحلیل محتوا"

# تنظیمات محدودیت‌ها
MAX_INPUT_LENGTH = 5000
MIN_WORDS_KW_DENSITY = 10
MIN_WORDS_READABILITY = 50

TOOLS = [
    {
        'id': 'kw_density',
        'name': 'چگالی کلمات کلیدی',
        'description': 'تحلیل چگالی و توزیع کلمات کلیدی در متن',
        'input_prompt': '🔠 لطفا متن خود را برای تحلیل چگالی کلمات کلیدی ارسال کنید:',
        'handler': kw_density_handler,
        'min_words': MIN_WORDS_KW_DENSITY
    },
    {
        'id': 'readability',
        'name': 'تحلیل خوانایی',
        'description': 'سنجش سطح خوانایی متن با معیارهای استاندارد',
        'input_prompt': '📖 لطفا متن خود را برای تحلیل خوانایی ارسال کنید:',
        'handler': readability_handler,
        'min_words': MIN_WORDS_READABILITY
    }
]

def validate_text(text: str, min_words: int = 1, max_length: int = MAX_INPUT_LENGTH) -> str:
    """اعتبارسنجی متن ورودی"""
    if not text.strip():
        return "⚠️ متن ورودی خالی است."
    
    if len(text) > max_length:
        return f"⚠️ متن بسیار طولانی است. حداکثر {max_length} کاراکتر مجاز است."
    
    words = text.split()
    if len(words) < min_words:
        return f"⚠️ متن بسیار کوتاه است. حداقل {min_words} کلمه مورد نیاز است."
    
    return ""

@log_activity
def kw_density_handler(update: Update, context: CallbackContext, text: str) -> str:
    """
    تحلیل چگالی کلمات کلیدی در متن
    
    Args:
        update: شیء Update تلگرام
        context: شیء Context تلگرام
        text: متن ورودی برای تحلیل
        
    Returns:
        نتیجه تحلیل به صورت رشته متنی
    """
    # اعتبارسنجی متن
    validation_msg = validate_text(text, MIN_WORDS_KW_DENSITY)
    if validation_msg:
        return validation_msg
    
    # پردازش متن
    words = [word.strip('.,!?()[]{}"\'') for word in text.split() if word.strip()]
    word_count = len(words)
    keyword_counts = Counter(word.lower() for word in words)
    
    # تولید گزارش
    report = ["📊 نتایج تحلیل چگالی کلمات کلیدی:\n"]
    significant_kws = [
        (kw, count) for kw, count in keyword_counts.most_common(10) 
        if (count / word_count) * 100 >= 1.0
    ]
    
    if significant_kws:
        for kw, count in significant_kws:
            density = (count / word_count) * 100
            report.append(f"- {kw}: {count} بار ({density:.2f}%)")
    else:
        report.append("هیچ کلمه کلیدی با چگالی قابل توجه یافت نشد.")
    
    # ذخیره نتیجه
    try:
        save_result(
            user_id=update.effective_user.id,
            tool_id='kw_density',
            input_text=text[:500],
            result='\n'.join(report)
        )
    except Exception as e:
        logger.error(f"خطا در ذخیره نتیجه چگالی کلمات: {e}")
    
    return '\n'.join(report)

@log_activity
def readability_handler(update: Update, context: CallbackContext, text: str) -> str:
    """
    تحلیل سطح خوانایی متن با استفاده از سرویس هوش مصنوعی
    
    Args:
        update: شیء Update تلگرام
        context: شیء Context تلگرام
        text: متن ورودی برای تحلیل
        
    Returns:
        نتیجه تحلیل به صورت رشته متنی
    """
    # اعتبارسنجی متن
    validation_msg = validate_text(text, MIN_WORDS_READABILITY)
    if validation_msg:
        return validation_msg
    
    # تحلیل با هوش مصنوعی
    try:
        analysis = analyze_with_ai(
            task="readability_analysis",
            text=text,
            language="fa"
        )
    except Exception as e:
        logger.error(f"خطا در تحلیل خوانایی: {e}")
        return "⚠️ خطا در تحلیل خوانایی. لطفا بعدا تلاش کنید."
    
    if not analysis:
        return "⚠️ خطا در تحلیل خوانایی. لطفا بعدا تلاش کنید."
    
    # تولید گزارش
    result = [
        f"📚 سطح خوانایی: {analysis.get('score', 0)}/100",
        f"✍️ سطح پیشنهادی: {analysis.get('recommended_level', 'نامشخص')}",
        "\n🔍 توصیه‌ها:",
        analysis.get('suggestions', 'هیچ توصیه‌ای موجود نیست.')
    ]
    
    # ذخیره نتیجه
    try:
        save_result(
            user_id=update.effective_user.id,
            tool_id='readability',
            input_text=text[:500],
            result='\n'.join(result)
        )
    except Exception as e:
        logger.error(f"خطا در ذخیره نتیجه خوانایی: {e}")
    
    return '\n'.join(result)

def register_handlers(dispatcher):
    """ثبت هندلرها برای ابزارهای مختلف"""
    for tool in TOOLS:
        dispatcher.add_handler(
            MessageHandler(
                Filters.text & ~Filters.command,
                tool['handler'],
                pass_user_data=True
            )
        )
