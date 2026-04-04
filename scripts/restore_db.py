#!/usr/bin/env python3
"""
Database Restore Script
Restore database from backup
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging import get_logger

logger = get_logger(__name__)


def list_backups():
    """List available backups"""
    backup_dir = Path("backups")
    if not backup_dir.exists():
        print("No backups found")
        return []
    
    backups = sorted(backup_dir.glob("leadgen_db_*.dump"))
    return backups


def restore_database(backup_file: str):
    """Restore database from backup"""
    from app.core.config import settings
    
    # Parse database URL
    import re
    db_url = settings.database_url
    match = re.match(r'postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', db_url)
    
    if not match:
        print("❌ Failed to parse database URL")
        return False
    
    user, password, host, port, dbname = match.groups()
    
    # Set password environment variable
    import os
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    
    # Run pg_restore
    cmd = [
        "pg_restore",
        "-h", host,
        "-p", port,
        "-U", user,
        "-d", dbname,
        "-c",  # Clean (drop) before creating
        "-v",  # Verbose
        backup_file
    ]
    
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Database restored from: {backup_file}")
            return True
        else:
            print(f"❌ Restore failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Restore error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("LeadGen Database Restore")
    print("=" * 50)
    
    backups = list_backups()
    
    if not backups:
        print("No backups found in 'backups/' directory")
        sys.exit(1)
    
    print("\nAvailable backups:")
    for i, backup in enumerate(backups):
        size = backup.stat().st_size / (1024 * 1024)
        print(f"  {i+1}. {backup.name} ({size:.2f} MB)")
    
    choice = input("\nEnter backup number to restore (or 'q' to quit): ")
    
    if choice.lower() == 'q':
        sys.exit(0)
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(backups):
            restore_database(str(backups[idx]))
        else:
            print("Invalid choice")
    except ValueError:
        print("Invalid input")