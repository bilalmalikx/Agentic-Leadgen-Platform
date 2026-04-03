"""
Structured Logging with Loguru
Supports JSON logs for production and pretty logs for development
"""

import sys
import json
from pathlib import Path
from loguru import logger
from datetime import datetime
import logging

from app.core.config import settings

# Remove default handler
logger.remove()

# Log format for development (pretty)
DEV_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

# Log format for production (JSON)
PROD_FORMAT = lambda record: json.dumps({
    "timestamp": record["time"].isoformat(),
    "level": record["level"].name,
    "logger": record["name"],
    "function": record["function"],
    "line": record["line"],
    "message": record["message"],
    "extra": record.get("extra", {})
}) + "\n"


def setup_logging():
    """Setup logging configuration"""
    
    # Create logs directory
    Path("logs").mkdir(exist_ok=True)
    
    # Console logging
    if settings.app_env == "production":
        # JSON format for production
        logger.add(
            sys.stdout,
            format=PROD_FORMAT,
            level=settings.log_level,
            colorize=False
        )
    else:
        # Pretty format for development
        logger.add(
            sys.stdout,
            format=DEV_FORMAT,
            level=settings.log_level,
            colorize=True
        )
    
    # File logging (always JSON for structured logging)
    logger.add(
        "logs/app.log",
        format=PROD_FORMAT,
        level=settings.log_level,
        rotation="100 MB",  # Rotate when file reaches 100MB
        retention="30 days",  # Keep logs for 30 days
        compression="gz",  # Compress rotated logs
        enqueue=True  # Thread-safe
    )
    
    # Error logs separately
    logger.add(
        "logs/error.log",
        format=PROD_FORMAT,
        level="ERROR",
        rotation="50 MB",
        retention="90 days",
        compression="gz",
        enqueue=True
    )
    
    # Access logs (API requests)
    logger.add(
        "logs/access.log",
        format=PROD_FORMAT,
        level="INFO",
        rotation="100 MB",
        retention="30 days",
        compression="gz",
        filter=lambda record: "access" in record["extra"]
    )
    
    # Task logs (Celery)
    logger.add(
        "logs/tasks.log",
        format=PROD_FORMAT,
        level="INFO",
        rotation="100 MB",
        retention="30 days",
        compression="gz",
        filter=lambda record: "task" in record["extra"]
    )
    
    # Bind default context
    logger.configure(
        extra={
            "app": settings.app_name,
            "env": settings.app_env,
            "version": settings.app_version
        }
    )
    
    # Intercept standard logging
    class InterceptHandler(logging.Handler):
        def emit(self, record):
            logger_opt = logger.opt(depth=6, exception=record.exc_info)
            logger_opt.log(record.levelname, record.getMessage())
    
    logging.basicConfig(handlers=[InterceptHandler()], level=0)
    
    logger.info(f"Logging initialized - Environment: {settings.app_env}, Level: {settings.log_level}")


def get_logger(name: str):
    """Get logger instance with name"""
    return logger.bind(name=name)


def log_request(request_id: str, method: str, path: str, status_code: int, duration_ms: float):
    """Log API request"""
    logger.bind(access=True, request_id=request_id).info(
        f"{method} {path} - {status_code} - {duration_ms:.2f}ms"
    )


def log_task(task_id: str, task_name: str, status: str, duration_ms: float = None):
    """Log Celery task"""
    extra = {"task": True, "task_id": task_id, "task_name": task_name, "task_status": status}
    if duration_ms:
        extra["duration_ms"] = duration_ms
    
    logger.bind(**extra).info(f"Task {task_name} {status}")


def log_error(error: Exception, context: dict = None):
    """Log error with context"""
    extra = {"error_type": type(error).__name__, "error_message": str(error)}
    if context:
        extra.update(context)
    
    logger.bind(**extra).exception("Error occurred")