"""
Context Utilities
Context managers for resource management and timing
"""

from typing import Any, Optional, Dict
import time
import asyncio
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime

from app.core.logging import get_logger

logger = get_logger(__name__)


@contextmanager
def timer(operation: str):
    """
    Context manager to time operations
    Usage: with timer("database_query"): do_something()
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.debug(f"{operation} took {duration:.3f}s")


@asynccontextmanager
async def async_timer(operation: str):
    """
    Async context manager to time operations
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.debug(f"{operation} took {duration:.3f}s")


@contextmanager
def ignore_errors(exception_types: tuple = (Exception,), log_error: bool = True):
    """
    Context manager to ignore specific exceptions
    """
    try:
        yield
    except exception_types as e:
        if log_error:
            logger.warning(f"Ignored exception: {e}")
        pass


@asynccontextmanager
async def async_ignore_errors(exception_types: tuple = (Exception,), log_error: bool = True):
    """
    Async context manager to ignore specific exceptions
    """
    try:
        yield
    except exception_types as e:
        if log_error:
            logger.warning(f"Ignored exception: {e}")
        pass


class TransactionContext:
    """
    Context manager for database transactions
    """
    
    def __init__(self, session):
        self.session = session
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.session.rollback()
            logger.error(f"Transaction rolled back due to: {exc_val}")
        else:
            await self.session.commit()


class PerformanceContext:
    """
    Context manager for performance monitoring
    """
    
    def __init__(self, operation: str, metrics: Optional[Dict] = None):
        self.operation = operation
        self.metrics = metrics or {}
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        self.metrics["duration_seconds"] = duration
        self.metrics["success"] = exc_type is None
        self.metrics["timestamp"] = datetime.utcnow().isoformat()
        
        if exc_type:
            self.metrics["error"] = str(exc_val)
        
        logger.info(f"Performance {self.operation}: {duration:.3f}s")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics"""
        return self.metrics


class AsyncPerformanceContext:
    """
    Async context manager for performance monitoring
    """
    
    def __init__(self, operation: str, metrics: Optional[Dict] = None):
        self.operation = operation
        self.metrics = metrics or {}
        self.start_time = None
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        self.metrics["duration_seconds"] = duration
        self.metrics["success"] = exc_type is None
        self.metrics["timestamp"] = datetime.utcnow().isoformat()
        
        if exc_type:
            self.metrics["error"] = str(exc_val)
        
        logger.info(f"Performance {self.operation}: {duration:.3f}s")


class ConnectionPoolContext:
    """
    Context manager for connection pool management
    """
    
    def __init__(self, pool, resource_name: str = "connection"):
        self.pool = pool
        self.resource_name = resource_name
        self.resource = None
    
    async def __aenter__(self):
        self.resource = await self.pool.acquire()
        logger.debug(f"Acquired {self.resource_name} from pool")
        return self.resource
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.resource:
            await self.pool.release(self.resource)
            logger.debug(f"Released {self.resource_name} back to pool")


def timing_decorator(operation: str):
    """
    Decorator to time function execution
    """
    def decorator(func):
        def sync_wrapper(*args, **kwargs):
            with timer(operation):
                return func(*args, **kwargs)
        
        async def async_wrapper(*args, **kwargs):
            async with async_timer(operation):
                return await func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


# Convenience functions
def time_it(operation: str):
    """Alias for timing_decorator"""
    return timing_decorator(operation)