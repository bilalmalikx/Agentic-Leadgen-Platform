"""
Base Agent Class
All agents inherit from this base class with common functionality
"""

from typing import Dict, Any, Optional, List, Callable
from abc import ABC, abstractmethod
import asyncio
import time
from datetime import datetime
from functools import wraps

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator for retrying agent operations on failure
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__}: {e}"
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All retries failed for {func.__name__}: {e}")
            
            raise last_exception
        return wrapper
    return decorator


class BaseAgent(ABC):
    """
    Abstract base class for all agents
    Provides common functionality: logging, metrics, error handling, retries
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.logger = get_logger(f"agent.{name}")
        self.metrics = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_duration_ms": 0,
            "last_run": None
        }
    
    @abstractmethod
    async def process(self, *args, **kwargs) -> Any:
        """
        Main processing method - must be implemented by child classes
        """
        pass
    
    async def execute(self, *args, **kwargs) -> Any:
        """
        Execute agent with metrics collection
        """
        start_time = time.time()
        self.metrics["total_calls"] += 1
        self.metrics["last_run"] = datetime.utcnow().isoformat()
        
        try:
            self.logger.info(f"Agent {self.name} starting execution")
            
            result = await self.process(*args, **kwargs)
            
            duration_ms = (time.time() - start_time) * 1000
            self.metrics["successful_calls"] += 1
            self.metrics["total_duration_ms"] += duration_ms
            
            self.logger.info(
                f"Agent {self.name} completed in {duration_ms:.2f}ms"
            )
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.metrics["failed_calls"] += 1
            self.metrics["total_duration_ms"] += duration_ms
            
            self.logger.error(
                f"Agent {self.name} failed after {duration_ms:.2f}ms: {e}"
            )
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get agent performance metrics
        """
        total_calls = self.metrics["total_calls"]
        avg_duration = (
            self.metrics["total_duration_ms"] / total_calls
            if total_calls > 0 else 0
        )
        
        return {
            "agent_name": self.name,
            "agent_version": self.version,
            "total_calls": self.metrics["total_calls"],
            "successful_calls": self.metrics["successful_calls"],
            "failed_calls": self.metrics["failed_calls"],
            "success_rate": (
                (self.metrics["successful_calls"] / total_calls) * 100
                if total_calls > 0 else 0
            ),
            "average_duration_ms": round(avg_duration, 2),
            "last_run": self.metrics["last_run"]
        }
    
    def reset_metrics(self):
        """
        Reset agent metrics
        """
        self.metrics = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_duration_ms": 0,
            "last_run": None
        }
    
    async def process_batch(
        self,
        items: List[Any],
        batch_size: int = 10,
        max_concurrent: int = 5
    ) -> List[Any]:
        """
        Process multiple items in batches with concurrency control
        """
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(item):
            async with semaphore:
                return await self.process(item)
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[process_with_semaphore(item) for item in batch],
                return_exceptions=True
            )
            
            for result in batch_results:
                if isinstance(result, Exception):
                    self.logger.error(f"Batch processing error: {result}")
                    results.append({"error": str(result)})
                else:
                    results.append(result)
            
            self.logger.debug(f"Processed batch {i // batch_size + 1}/{len(items) // batch_size + 1}")
        
        return results
    
    def log_step(self, step_name: str, data: Optional[Dict] = None):
        """
        Log a step in the agent's processing
        """
        self.logger.info(f"[{self.name}] Step: {step_name}", extra={"step_data": data})


class BatchProcessor(BaseAgent):
    """
    Base class for agents that process data in batches
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        super().__init__(name, version)
        self.batch_size = 10
        self.max_concurrent = 5
    
    async def process_batch(
        self,
        items: List[Any],
        batch_size: Optional[int] = None,
        max_concurrent: Optional[int] = None
    ) -> List[Any]:
        """
        Process batch with custom settings
        """
        self.batch_size = batch_size or self.batch_size
        self.max_concurrent = max_concurrent or self.max_concurrent
        
        return await super().process_batch(
            items=items,
            batch_size=self.batch_size,
            max_concurrent=self.max_concurrent
        )
    
    @abstractmethod
    async def process_item(self, item: Any) -> Any:
        """
        Process a single item - must be implemented
        """
        pass
    
    async def process(self, items: List[Any]) -> List[Any]:
        """
        Main process method that calls process_item for each item
        """
        return await self.process_batch(items)