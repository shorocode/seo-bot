import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

from config import settings
from utils.logger import logger

# SQLAlchemy setup
Base = declarative_base()

class AnalysisResult(Base):
    """Database model for storing analysis results"""
    __tablename__ = 'analysis_results'
    
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.BigInteger, nullable=False)
    tool_id = sa.Column(sa.String(50), nullable=False)
    input_text = sa.Column(sa.Text)
    result = sa.Column(sa.Text)
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow)
    metadata_ = sa.Column(sa.JSON, name='metadata')

class User(Base):
    """Database model for bot users"""
    __tablename__ = 'users'
    
    id = sa.Column(sa.BigInteger, primary_key=True)
    username = sa.Column(sa.String(100))
    first_name = sa.Column(sa.String(100))
    last_name = sa.Column(sa.String(100))
    language_code = sa.Column(sa.String(10))
    is_admin = sa.Column(sa.Boolean, default=False)
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow)
    last_activity = sa.Column(sa.DateTime)

class DatabaseService:
    """
    Database service with SQLAlchemy ORM
    Handles all database operations for the bot
    """
    
    def __init__(self):
        self.engine = None
        self.Session = None
        self._connect()
        
    def _connect(self):
        """Initialize database connection"""
        try:
            self.engine = sa.create_engine(settings.DATABASE_URL)
            self.Session = sessionmaker(bind=self.engine)
            
            # Create tables if they don't exist
            Base.metadata.create_all(self.engine)
            
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            raise
    
    def save_result(self, user_id: int, tool_id: str, input_text: str, result: str, metadata: dict = None) -> bool:
        """
        Save analysis result to database
        Returns True if successful
        """
        if not self.Session:
            return False
            
        session = self.Session()
        try:
            record = AnalysisResult(
                user_id=user_id,
                tool_id=tool_id,
                input_text=input_text,
                result=result,
                metadata_=metadata or {}
            )
            session.add(record)
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to save result: {str(e)}")
            return False
        finally:
            session.close()
    
    def get_user_results(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent analysis results for a user"""
        if not self.Session:
            return []
            
        session = self.Session()
        try:
            results = session.query(AnalysisResult)\
                .filter_by(user_id=user_id)\
                .order_by(AnalysisResult.created_at.desc())\
                .limit(limit)\
                .all()
                
            return [{
                'tool_id': r.tool_id,
                'created_at': r.created_at,
                'summary': r.result[:100] + '...' if len(r.result) > 100 else r.result
            } for r in results]
        except SQLAlchemyError as e:
            logger.error(f"Failed to get user results: {str(e)}")
            return []
        finally:
            session.close()
    
    def get_or_create_user(self, user_data: dict) -> Optional[User]:
        """Get user record or create if not exists"""
        if not self.Session:
            return None
            
        session = self.Session()
        try:
            user = session.query(User)\
                .filter_by(id=user_data['id'])\
                .first()
                
            if not user:
                user = User(
                    id=user_data['id'],
                    username=user_data.get('username'),
                    first_name=user_data.get('first_name'),
                    last_name=user_data.get('last_name'),
                    language_code=user_data.get('language_code', 'fa')
                )
                session.add(user)
                session.commit()
            else:
                # Update last activity
                user.last_activity = datetime.utcnow()
                session.commit()
                
            return user
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"User operation failed: {str(e)}")
            return None
        finally:
            session.close()
    
    def get_usage_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get usage statistics for admin panel"""
        if not self.Session:
            return {}
            
        session = self.Session()
        try:
            # Daily usage
            daily_usage = session.execute(
                sa.text("""
                    SELECT DATE(created_at) as day, 
                           COUNT(*) as count
                    FROM analysis_results
                    WHERE created_at >= :start_date
                    GROUP BY day
                    ORDER BY day
                """),
                {'start_date': datetime.utcnow() - timedelta(days=days)}
            ).fetchall()
            
            # Tool popularity
            tool_stats = session.execute(
                sa.text("""
                    SELECT tool_id, COUNT(*) as count
                    FROM analysis_results
                    WHERE created_at >= :start_date
                    GROUP BY tool_id
                    ORDER BY count DESC
                """),
                {'start_date': datetime.utcnow() - timedelta(days=days)}
            ).fetchall()
            
            return {
                'daily_usage': [{'day': str(r[0]), 'count': r[1]} for r in daily_usage],
                'tool_stats': [{'tool_id': r[0], 'count': r[1]} for r in tool_stats],
                'total_users': session.query(User).count()
            }
        except SQLAlchemyError as e:
            logger.error(f"Failed to get stats: {str(e)}")
            return {}
        finally:
            session.close()

# Initialize database service
def init_db():
    """Initialize database service"""
    try:
        db_service = DatabaseService()
        return db_service
    except Exception as e:
        logger.critical(f"Database initialization failed: {str(e)}")
        return None

# Singleton database instance
db = init_db()
