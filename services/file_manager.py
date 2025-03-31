from pathlib import Path
import aiofiles
from typing import AsyncGenerator
from config import settings
import logging

logger = logging.getLogger(__name__)

class FileManager:
    """مدیریت امن عملیات فایل‌سیستمی"""
    
    def __init__(self):
        self.base_dir = Path(settings.FILE_STORAGE)
        self.base_dir.mkdir(exist_ok=True)
        
    async def save_file(self, path: str, content: bytes) -> bool:
        """ذخیره ایمن فایل"""
        try:
            file_path = self._validate_path(path)
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
            return True
        except Exception as e:
            logger.error(f"File save failed: {str(e)}")
            return False

    async def read_file(self, path: str) -> AsyncGenerator[bytes, None]:
        """خواندن ایمن فایل به صورت جریانی"""
        try:
            file_path = self._validate_path(path)
            async with aiofiles.open(file_path, 'rb') as f:
                while chunk := await f.read(4096):
                    yield chunk
        except Exception as e:
            logger.error(f"File read failed: {str(e)}")
            raise

    def _validate_path(self, path: str) -> Path:
        """اعتبارسنجی مسیر فایل برای جلوگیری از Directory Traversal"""
        full_path = (self.base_dir / path).resolve()
        if not full_path.is_relative_to(self.base_dir):
            raise ValueError("Invalid file path")
        return full_path

# نمونه Singleton
file_manager = FileManager()
