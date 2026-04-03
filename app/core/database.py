"""
Database Configuration and Session Management
Async PostgreSQL with SQLAlchemy 2.0
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from typing import Optional, Dict, Any
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create base class for models
Base = declarative_base()

# Global engine and session factory
_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[async_sessionmaker] = None


async def init_db() -> None:
    """
    Initialize database connection pool
    Creates engine and session factory
    """
    global _engine, _async_session_maker
    
    try:
        # Create async engine with connection pooling
        _engine = create_async_engine(
            settings.get_database_url_async(),
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout,
            pool_pre_ping=True,  # Verify connections before using
            echo=settings.database_echo,
            echo_pool=settings.database_echo
        )
        
        # Create session factory
        _async_session_maker = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )
        
        # Test connection
        async with _engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        
        logger.info("Database connection pool created successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_db() -> None:
    """
    Close database connection pool
    Cleanup on application shutdown
    """
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("Database connection pool closed")


async def get_session() -> AsyncSession:
    """
    Get a database session
    Used as dependency in FastAPI routes
    """
    if not _async_session_maker:
        await init_db()
    
    async with _async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_health() -> Dict[str, Any]:
    """
    Check database health
    Returns status and connection info
    """
    try:
        if not _engine:
            return {"status": "unhealthy", "error": "Database not initialized"}
        
        async with _engine.begin() as conn:
            result = await conn.execute(text("SELECT 1 as health, version(), current_database(), current_user"))
            row = result.fetchone()
            
            return {
                "status": "healthy",
                "version": row[1] if row else "unknown",
                "database": row[2] if row else "unknown",
                "user": row[3] if row else "unknown"
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


# Dependency to get session (for FastAPI routes)
async def get_db():
    """FastAPI dependency for database session"""
    async for session in get_session():
        return session


# Sync engine for Alembic migrations (not async)
def get_sync_engine():
    """Get sync engine for migrations"""
    from sqlalchemy import create_engine
    return create_engine(settings.get_database_url_sync())