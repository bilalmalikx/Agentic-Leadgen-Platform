"""
Database Configuration and Session Management
Async PostgreSQL (FastAPI) + Sync Session (Celery/Alembic support)
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine, text
from contextlib import asynccontextmanager, contextmanager
from typing import Optional, Dict, Any
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# =========================
# Base Model
# =========================
Base = declarative_base()

# =========================
# Async (FastAPI)
# =========================
_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[async_sessionmaker] = None

# =========================
# Sync (Celery / Alembic)
# =========================
_sync_engine = None
_SyncSessionLocal = None


# =========================================================
# INIT DATABASE (ASYNC)
# =========================================================
async def init_db() -> None:
    global _engine, _async_session_maker

    try:
        _engine = create_async_engine(
            settings.get_database_url_async(),
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout,
            pool_pre_ping=True,
            echo=settings.database_echo,
            echo_pool=settings.database_echo
        )

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

        logger.info("✅ Async database initialized successfully")

    except Exception as e:
        logger.error(f"❌ Failed to initialize async DB: {e}")
        raise


# =========================================================
# CLOSE DATABASE
# =========================================================
async def close_db() -> None:
    global _engine

    if _engine:
        await _engine.dispose()
        logger.info("🛑 Async database connection closed")


# =========================================================
# ASYNC SESSION (FASTAPI)
# =========================================================
@asynccontextmanager
async def get_session():
    """
    FastAPI async DB session
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


# FastAPI dependency
async def get_db():
    async with get_session() as session:
        yield session


# =========================================================
# SYNC ENGINE (CELERY / ALEMBIC)
# =========================================================
def get_sync_engine():
    global _sync_engine

    if _sync_engine is None:
        _sync_engine = create_engine(
            settings.get_database_url_sync(),
            pool_pre_ping=True
        )

    return _sync_engine


# =========================================================
# SYNC SESSION (CELERY TASKS)
# =========================================================
@contextmanager
def get_sync_session():
    """
    Sync DB session for Celery tasks
    """
    global _SyncSessionLocal

    if _SyncSessionLocal is None:
        _SyncSessionLocal = sessionmaker(
            bind=get_sync_engine(),
            autocommit=False,
            autoflush=False
        )

    db = _SyncSessionLocal()

    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# =========================================================
# HEALTH CHECK
# =========================================================
async def get_db_health() -> Dict[str, Any]:
    try:
        if not _engine:
            return {"status": "unhealthy", "error": "DB not initialized"}

        async with _engine.begin() as conn:
            result = await conn.execute(
                text("SELECT 1 as health, version(), current_database(), current_user")
            )
            row = result.fetchone()

            return {
                "status": "healthy",
                "version": row[1] if row else None,
                "database": row[2] if row else None,
                "user": row[3] if row else None
            }

    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}