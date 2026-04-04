"""
Retry Utilities
Retry decorators and functions with exponential backoff
"""

from typing import TypeVar, Callable, Any, List, Optional, Tuple
from functools import wraps
import asyncio
import time
import random

from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        retry_on_exceptions: Optional[List[type]] = None
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.retry_on_exceptions = retry_on_exceptions or [Exception]


def retry(config: Optional[RetryConfig] = None):
    """
    Decorator for retrying functions with exponential backoff
    """
    config = config or RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            last_exception = None
            delay = config.initial_delay
            
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except tuple(config.retry_on_exceptions) as e:
                    last_exception = e
                    
                    if attempt == config.max_retries:
                        logger.error(f"All {config.max_retries} retries failed for {func.__name__}: {e}")
                        raise
                    
                    # Calculate wait time with exponential backoff
                    wait_time = delay * (config.backoff_factor ** attempt)
                    wait_time = min(wait_time, config.max_delay)
                    
                    # Add jitter to avoid thundering herd
                    if config.jitter:
                        wait_time = wait_time * (0.5 + random.random())
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{config.max_retries} for {func.__name__} "
                        f"after {wait_time:.2f}s due to: {e}"
                    )
                    
                    await asyncio.sleep(wait_time)
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            last_exception = None
            delay = config.initial_delay
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except tuple(config.retry_on_exceptions) as e:
                    last_exception = e
                    
                    if attempt == config.max_retries:
                        logger.error(f"All {config.max_retries} retries failed for {func.__name__}: {e}")
                        raise
                    
                    wait_time = delay * (config.backoff_factor ** attempt)
                    wait_time = min(wait_time, config.max_delay)
                    
                    if config.jitter:
                        wait_time = wait_time * (0.5 + random.random())
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{config.max_retries} for {func.__name__} "
                        f"after {wait_time:.2f}s due to: {e}"
                    )
                    
                    time.sleep(wait_time)
            
            raise last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


async def retry_async(
    func: Callable[..., T],
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    **kwargs
) -> T:
    """
    Retry an async function with exponential backoff
    """
    config = RetryConfig(max_retries=max_retries, initial_delay=initial_delay)
    
    @retry(config)
    async def wrapped():
        return await func(*args, **kwargs)
    
    return await wrapped()


def retry_sync(
    func: Callable[..., T],
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    **kwargs
) -> T:
    """
    Retry a sync function with exponential backoff
    """
    config = RetryConfig(max_retries=max_retries, initial_delay=initial_delay)
    
    @retry(config)
    def wrapped():
        return func(*args, **kwargs)
    
    return wrapped()


def retry_on_rate_limit(func: Callable[..., T]) -> Callable[..., T]:
    """
    Specialized retry for rate limit errors
    """
    config = RetryConfig(
        max_retries=5,
        initial_delay=5.0,
        max_delay=120.0,
        backoff_factor=2.0,
        jitter=True,
        retry_on_exceptions=[Exception]  # Customize based on rate limit exception
    )
    return retry(config)(func)