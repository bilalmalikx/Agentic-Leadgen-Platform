#!/usr/bin/env python3
"""
Database Backup Script
Creates backup of PostgreSQL database
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def backup_database():
    """Create database backup"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    backup_file = backup_dir / f"leadgen_backup_{timestamp}.sql"
    
    # Parse database URL
    db_url = settings.database_url
    # Format: postgresql+asyncpg://user:pass@host:port/dbname
    import re
    match = re.match(r'postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', db_url)
    
    if not match:
        logger.error("Failed to parse database URL")
        return False
    
    user, password, host, port, dbname = match.groups()
    
    # Set password environment variable
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    
    # Run pg_dump
    cmd = [
        "pg_dump",
        "-h", host,
        "-p", port,
        "-U", user,
        "-d", dbname,
        "-F", "c",  # Custom format
        "-f", str(backup_file)
    ]
    
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            file_size = backup_file.stat().st_size
            logger.info(f"Backup created: {backup_file} ({file_size} bytes)")
            return True
        else:
            logger.error(f"Backup failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Backup error: {e}")
        return False


def backup_redis():
    """Save Redis data to disk"""
    try:
        import redis
        r = redis.from_url(settings.redis_url)
        r.save()
        logger.info("Redis backup triggered (RDB saved)")
        return True
    except Exception as e:
        logger.error(f"Redis backup failed: {e}")
        return False


if __name__ == "__main__":
    print("Starting database backup...")
    
    db_success = backup_database()
    redis_success = backup_redis()
    
    if db_success and redis_success:
        print("✅ Backup completed successfully")
        sys.exit(0)
    else:
        print("❌ Backup failed")
        sys.exit(1)