#!/usr/bin/env python3
"""
Celery Queue Monitor
Monitor Celery queue sizes and task status
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


def monitor_queues():
    """Monitor Celery queues"""
    print("\n📊 Celery Queue Monitor")
    print("=" * 40)
    
    try:
        # Get active queues
        inspect = celery_app.control.inspect()
        
        # Active tasks
        active = inspect.active()
        if active:
            total_active = sum(len(tasks) for tasks in active.values())
            print(f"🟢 Active tasks: {total_active}")
        else:
            print("🟢 Active tasks: 0")
        
        # Reserved tasks
        reserved = inspect.reserved()
        if reserved:
            total_reserved = sum(len(tasks) for tasks in reserved.values())
            print(f"🟡 Reserved tasks: {total_reserved}")
        else:
            print("🟡 Reserved tasks: 0")
        
        # Scheduled tasks
        scheduled = inspect.scheduled()
        if scheduled:
            total_scheduled = sum(len(tasks) for tasks in scheduled.values())
            print(f"🔵 Scheduled tasks: {total_scheduled}")
        else:
            print("🔵 Scheduled tasks: 0")
        
        # Registered workers
        stats = inspect.stats()
        if stats:
            print(f"👷 Active workers: {len(stats)}")
            
            for worker, stat in stats.items():
                print(f"\n   Worker: {worker}")
                print(f"   - Total tasks: {stat.get('total', 0)}")
                print(f"   - Pool size: {stat.get('pool', {}).get('max-concurrency', 0)}")
        
        # Queue sizes (if using Redis)
        from app.core.redis_client import get_redis
        import asyncio
        
        async def get_queue_sizes():
            redis = await get_redis()
            queues = ["high_priority", "default", "low_priority", "scraping", "email"]
            
            print("\n📋 Queue Sizes:")
            for queue in queues:
                size = await redis.llen(queue)
                print(f"   - {queue}: {size}")
        
        asyncio.run(get_queue_sizes())
        
    except Exception as e:
        print(f"❌ Failed to monitor queues: {e}")


if __name__ == "__main__":
    monitor_queues()