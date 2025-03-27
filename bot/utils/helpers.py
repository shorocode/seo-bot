import re
import hashlib
import string
import random
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse
import pytz
from datetime import datetime
import html
import emoji
import logging

from config import settings
from utils.logger import logger

def clean_text(text: str, remove_emoji: bool = False) -> str:
    """Clean and normalize text for processing"""
    if not text:
        return ""
    
    # Remove extra whitespace
    text = " ".join(text.split())
    
    # Normalize Persian characters
    text = normalize_persian(text)
    
    # Remove emojis if requested
    if remove_emoji:
        text = emoji.replace_emoji(text, replace="")
    
    # Escape HTML entities
    text = html.escape(text)
    
    return text.strip()

def normalize_persian(text: str) -> str:
    """Normalize Persian/Arabic characters"""
    replacements = {
        'ك': 'ک',
        'ي': 'ی',
        'ة': 'ه',
        'ۀ': 'ه',
        'ؤ': 'و',
        'إ': 'ا',
        'أ': 'ا',
        'ٱ': 'ا',
        'ڵ': 'ل',
        'ڭ': 'ن',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text

def generate_random_string(length: int = 8) -> str:
    """Generate random string with letters and digits"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def is_valid_url(url: str) -> bool:
    """Check if a string is a valid URL"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def extract_urls(text: str) -> List[str]:
    """Extract all valid URLs from text"""
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    return [url for url in url_pattern.findall(text) if is_valid_url(url)]

def truncate_text(text: str, max_length: int = 100, ellipsis: str = "...") -> str:
    """Truncate text with ellipsis if needed"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(ellipsis)] + ellipsis

def parse_keywords(text: str, min_length: int = 3) -> List[str]:
    """Extract keywords from text"""
    words = re.findall(r'\w+', clean_text(text).lower())
    return [word for word in words if len(word) >= min_length]

def get_tehran_time() -> datetime:
    """Get current time in Tehran timezone"""
    tz = pytz.timezone("Asia/Tehran")
    return datetime.now(tz)

def format_timedelta(delta) -> str:
    """Format timedelta as human-readable string"""
    parts = []
    
    # Days
    if delta.days > 0:
        parts.append(f"{delta.days} روز")
    
    # Hours
    hours = delta.seconds // 3600
    if hours > 0:
        parts.append(f"{hours} ساعت")
    
    # Minutes
    minutes = (delta.seconds % 3600) // 60
    if minutes > 0:
        parts.append(f"{minutes} دقیقه")
    
    # Seconds
    seconds = delta.seconds % 60
    if seconds > 0 and len(parts) < 2:
        parts.append(f"{seconds} ثانیه")
    
    return " و ".join(parts) if parts else "کمتر از یک ثانیه"

def create_checksum(data: Any) -> str:
    """Create checksum for data"""
    if isinstance(data, (dict, list)):
        data = str(sorted(data.items())) if isinstance(data, dict) else str(sorted(data))
    return hashlib.md5(data.encode('utf-8')).hexdigest()

def split_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks"""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

def safe_get(dictionary: Dict, *keys, default=None) -> Any:
    """Safely get nested dictionary keys"""
    current = dictionary
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current

def calculate_readability_score(text: str) -> float:
    """Calculate simple readability score for Persian text"""
    # Implementation of a basic readability algorithm
    words = clean_text(text).split()
    word_count = len(words)
    
    if word_count == 0:
        return 0.0
    
    # Count sentences (very basic)
    sentence_count = max(1, text.count('.') + text.count('!') + text.count('؟'))
    
    # Count complex words (more than 3 syllables - approximation)
    complex_words = sum(1 for word in words if len(word) > 5)
    
    # Simple readability formula (adjusted for Persian)
    score = 200 - (1.5 * (word_count / sentence_count)) - (8 * (complex_words / word_count))
    
    # Normalize to 0-100 range
    return max(0, min(100, score))
