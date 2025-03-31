from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from contextlib import contextmanager, AbstractContextManager
from typing import Generator, Optional, Callable, Any
import logging
from threading import Lock
from config import settings
import time
from datetime import datetime
from typing import TypeVar, Type

logger = logging.getLogger(__name__)

T = TypeVar('T', bound='Base')

# تنظیمات پیشرفته اتصال به دیتابیس با قابلیت‌های اضافه
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=30,
    echo=settings.DB_ECHO,
    echo_pool=settings.DB_ECHO_POOL,
    hide_parameters=not settings.DB_SHOW_PARAMETERS,
    connect_args={
        'connect_timeout': 10,
        'application_name': 'telegram-seo-bot',
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 3
    } if 'postgresql' in settings.DATABASE_URL else {},
    future=True  # برای پشتیبانی از SQLAlchemy 2.0
)

# رویدادهای اتصال برای مانیتورینگ
@event.listens_for(engine, "connect")
def on_connect(dbapi_connection, connection_record):
    logger.debug("New database connection established")

@event.listens_for(engine, "close")
def on_close(dbapi_connection, connection_record):
    logger.debug("Database connection closed")

@event.listens_for(engine, "checkout")
def on_checkout(dbapi_connection, connection_record, connection_proxy):
    logger.debug("Connection checked out from pool")

@event.listens_for(engine, "checkin")
def on_checkin(dbapi_connection, connection_record):
    logger.debug("Connection returned to pool")

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
    twophase=False,
    info=None
)

Base = declarative_base()

class DatabaseManager:
    """کلاس مدیریت پیشرفته دیتابیس با قابلیت‌های حرفه‌ای"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """مقداردهی اولیه با تنظیمات پیشرفته"""
        self.session_factory = SessionLocal
        self.engine = engine
        self._setup_connection_pool_monitoring()
        logger.info("DatabaseManager initialized successfully")
    
    def _setup_connection_pool_monitoring(self):
        """تنظیم مانیتورینگ برای connection pool"""
        @event.listens_for(self.engine, 'engine_connect')
        def receive_engine_connect(conn, branch):
            if branch:
                logger.debug("Branch new database connection")
        
        @event.listens_for(self.engine, 'engine_disposed')
        def receive_engine_disposed(engine):
            logger.info("Database engine disposed")

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """مدیریت خودکار session با قابلیت‌های پیشرفته"""
        session: Session = scoped_session(self.session_factory)
        session.begin()
        try:
            yield session
            session.commit()
            logger.debug("Session committed successfully")
        except OperationalError as e:
            session.rollback()
            logger.error(f"Database operational error: {e}", exc_info=True)
            raise DatabaseError("Database connection problem") from e
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error occurred: {e}", exc_info=True)
            raise DatabaseError("Database operation failed") from e
        except Exception as e:
            session.rollback()
            logger.critical(f"Unexpected database error: {e}", exc_info=True)
            raise DatabaseError("Unexpected database error") from e
        finally:
            session.close()
            logger.debug("Session closed")

    def health_check(self, retries: int = 3, delay: float = 1.0) -> bool:
        """بررسی سلامت اتصال به دیتابیس با قابلیت تلاش مجدد"""
        for attempt in range(1, retries + 1):
            try:
                with self.session() as session:
                    result = session.execute("SELECT 1").scalar()
                    if result == 1:
                        logger.info("Database health check successful")
                        return True
            except Exception as e:
                logger.warning(
                    f"Database health check attempt {attempt} failed: {str(e)}"
                )
                if attempt < retries:
                    time.sleep(delay * attempt)
        logger.error("All database health check attempts failed")
        return False

    def get_or_create(
        self,
        session: Session,
        model: Type[T],
        defaults: Optional[dict] = None,
        **kwargs
    ) -> tuple[T, bool]:
        """دریافت یا ایجاد رکورد جدید (get_or_create pattern)"""
        try:
            instance = session.query(model).filter_by(**kwargs).first()
            if instance:
                return instance, False
            
            params = {**kwargs, **(defaults or {})}
            instance = model(**params)
            session.add(instance)
            session.commit()
            return instance, True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"get_or_create failed for {model.__name__}: {e}")
            raise DatabaseError(f"Failed to get_or_create {model.__name__}") from e

    def bulk_insert(
        self,
        session: Session,
        model: Type[T],
        data_list: list[dict],
        return_defaults: bool = False
    ) -> Optional[list[T]]:
        """درج دسته‌ای رکوردها با کارایی بالا"""
        try:
            result = session.execute(
                model.__table__.insert(),
                data_list,
                return_defaults=return_defaults
            )
            session.commit()
            return result.inserted_primary_key_rows if return_defaults else None
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Bulk insert failed for {model.__name__}: {e}")
            raise DatabaseError(f"Bulk insert failed for {model.__name__}") from e

    def execute_raw_sql(
        self,
        session: Session,
        sql: str,
        params: Optional[dict] = None
    ) -> list[Any]:
        """اجرای کوئری خام SQL"""
        try:
            result = session.execute(sql, params or {})
            return [row for row in result]
        except SQLAlchemyError as e:
            logger.error(f"Raw SQL execution failed: {e}\nSQL: {sql}")
            raise DatabaseError("Raw SQL execution failed") from e

    async def async_health_check(self) -> bool:
        """بررسی سلامت دیتابیس به صورت غیرهمزمان"""
        # برای استفاده با async/await (در صورت نیاز به async)
        return await asyncio.get_event_loop().run_in_executor(
            None,
            self.health_check
        )

    def get_session_stats(self) -> dict:
        """دریافت آمار و اطلاعات connection pool"""
        return {
            "checked_out": self.engine.pool.checkedout(),
            "checked_in": self.engine.pool.checkedin(),
            "connections": self.engine.pool.status(),
            "size": self.engine.pool.size(),
            "timeout": self.engine.pool.timeout(),
            "created_at": datetime.now().isoformat()
        }

class DatabaseError(Exception):
    """خطای سفارشی برای عملیات دیتابیس"""
    pass

# نمونه Singleton از دیتابیس
db = DatabaseManager()

# توابع کمکی برای یکپارچه‌سازی با فریمورک‌ها
def get_db() -> Generator[Session, None, None]:
    """تهیه session برای FastAPI Dependency Injection"""
    with db.session() as session:
        yield session

def get_db_session() -> AbstractContextManager[Session]:
    """تهیه session به عنوان context manager"""
    return db.session()

def init_db():
    """مقداردهی اولیه دیتابیس و ایجاد جداول"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.critical(f"Failed to initialize database tables: {e}")
        raise
