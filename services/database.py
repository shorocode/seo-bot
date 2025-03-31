from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager
from typing import Generator
import logging
from config import settings

logger = logging.getLogger(__name__)

# تنظیمات پیشرفته اتصال به دیتابیس
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        'connect_timeout': 10,
        'application_name': 'seo-bot'
    } if 'postgresql' in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)

Base = declarative_base()

class Database:
    """کلاس مدیریت دیتابیس با قابلیت‌های پیشرفته"""
    
    def __init__(self):
        self.session_factory = SessionLocal

    @contextmanager
    def session(self) -> Generator[SessionLocal, None, None]:
        """مدیریت خودکار session با قابلیت rollback"""
        session = scoped_session(self.session_factory)
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}", exc_info=True)
            raise
        finally:
            session.close()

    def health_check(self) -> bool:
        """بررسی سلامت اتصال به دیتابیس"""
        try:
            with self.session() as session:
                session.execute("SELECT 1")
            return True
        except Exception as e:
            logger.critical(f"Database connection failed: {e}")
            return False

# نمونه Singleton از دیتابیس
db = Database()

# توابع کمکی
def get_db() -> Generator[SessionLocal, None, None]:
    """تهیه session برای FastAPI Dependency Injection"""
    with db.session() as session:
        yield session
