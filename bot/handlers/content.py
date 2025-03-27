from telegram import Update
from telegram.ext import CallbackContext
from services.ai import analyze_with_ai
from services.database import save_result
from utils.decorators import log_activity

CATEGORY_NAME = "📝 تحلیل محتوا"

TOOLS = [
    {
        'id': 'kw_density',
        'name': 'چگالی کلمات کلیدی',
        'description': 'تحلیل چگالی و توزیع کلمات کلیدی در متن',
        'input_prompt': '🔠 لطفا متن خود را برای تحلیل چگالی کلمات کلیدی ارسال کنید:',
        'handler': kw_density_handler
    },
    {
        'id': 'readability',
        'name': 'تحلیل خوانایی',
        'description': 'سنجش سطح خوانایی متن با معیارهای استاندارد',
        'input_prompt': '📖 لطفا متن خود را برای تحلیل خوانایی ارسال کنید:',
        'handler': readability_handler
    },
    # ... سایر ابزارها
]

@log_activity
def kw_density_handler(update: Update, context: CallbackContext, text: str):
    """Analyze keyword density"""
    words = [word.strip('.,!?()[]{}"\'') for word in text.split() if word.strip()]
    word_count = len(words)
    
    if word_count < 10:
        return "⚠️ متن بسیار کوتاه است. لطفا متن طولانی‌تری ارسال کنید."
    
    keyword_counts = {}
    for word in words:
        normalized_word = word.lower()
        if normalized_word in keyword_counts:
            keyword_counts[normalized_word] += 1
        else:
            keyword_counts[normalized_word] = 1
    
    # Sort by frequency
    sorted_kws = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Generate report
    report = ["📊 نتایج تحلیل چگالی کلمات کلیدی:\n"]
    for kw, count in sorted_kws[:10]:  # Top 10 keywords
        density = (count / word_count) * 100
        if density >= 1.0:  # Only significant keywords
            report.append(f"- {kw}: {count} بار ({density:.2f}%)")
    
    if len(report) == 1:
        report.append("هیچ کلمه کلیدی با چگالی قابل توجه یافت نشد.")
    
    # Save to database
    save_result(
        user_id=update.effective_user.id,
        tool_id='kw_density',
        input_text=text[:500],  # Store first 500 chars
        result='\n'.join(report)
    )
    
    return '\n'.join(report)

@log_activity
def readability_handler(update: Update, context: CallbackContext, text: str):
    """Analyze text readability using AI"""
    if len(text.split()) < 50:
        return "⚠️ متن بسیار کوتاه است. لطفا متن حداقل 50 کلمه‌ای ارسال کنید."
    
    # Use AI service for advanced analysis
    analysis = analyze_with_ai(
        task="readability_analysis",
        text=text,
        language="fa"
    )
    
    if not analysis:
        return "⚠️ خطا در تحلیل خوانایی. لطفا بعدا تلاش کنید."
    
    # Format result
    result = [
        f"📚 سطح خوانایی: {analysis.get('score', 0)}/100",
        f"✍️ سطح پیشنهادی: {analysis.get('recommended_level', 'نامشخص')}",
        "\n🔍 توصیه‌ها:",
        analysis.get('suggestions', 'هیچ توصیه‌ای موجود نیست.')
    ]
    
    # Save to database
    save_result(
        user_id=update.effective_user.id,
        tool_id='readability',
        input_text=text[:500],
        result='\n'.join(result)
    )
    
    return '\n'.join(result)
