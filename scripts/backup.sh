#!/bin/bash
# Database and Redis Backup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}LeadGen Backup Script${NC}"
echo -e "${GREEN}========================================${NC}"

# Create backup directory
BACKUP_DIR="./backups"
mkdir -p $BACKUP_DIR

# Timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Database backup
echo -e "${YELLOW}Creating database backup...${NC}"

if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}DATABASE_URL not set. Using default...${NC}"
    DB_HOST=${DB_HOST:-localhost}
    DB_PORT=${DB_PORT:-5432}
    DB_USER=${DB_USER:-leadgen}
    DB_PASSWORD=${DB_PASSWORD:-leadgen123}
    DB_NAME=${DB_NAME:-leadgen}
else
    # Parse DATABASE_URL
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_USER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
fi

# Create database backup
PGPASSWORD=$DB_PASSWORD pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -F c -f "$BACKUP_DIR/leadgen_db_$TIMESTAMP.dump"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Database backup created: $BACKUP_DIR/leadgen_db_$TIMESTAMP.dump${NC}"
else
    echo -e "${RED}❌ Database backup failed${NC}"
    exit 1
fi

# Redis backup (RDB)
echo -e "${YELLOW}Creating Redis backup...${NC}"

REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}

# Save Redis data to disk
redis-cli -h $REDIS_HOST -p $REDIS_PORT SAVE

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Redis backup triggered${NC}"
    
    # Copy RDB file if available
    if [ -f /var/lib/redis/dump.rdb ]; then
        cp /var/lib/redis/dump.rdb "$BACKUP_DIR/redis_dump_$TIMESTAMP.rdb"
        echo -e "${GREEN}✅ Redis RDB copied: $BACKUP_DIR/redis_dump_$TIMESTAMP.rdb${NC}"
    fi
else
    echo -e "${RED}❌ Redis backup failed${NC}"
fi

# Create backup info file
cat > "$BACKUP_DIR/backup_info_$TIMESTAMP.txt" << EOF
Backup Information
==================
Timestamp: $TIMESTAMP
Database: $DB_NAME
Host: $DB_HOST
Redis Host: $REDIS_HOST

Files created:
- leadgen_db_$TIMESTAMP.dump
- redis_dump_$TIMESTAMP.rdb

Size: $(du -sh $BACKUP_DIR/leadgen_db_$TIMESTAMP.dump | cut -f1)
EOF

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Backup completed successfully!${NC}"
echo -e "${GREEN}Backup directory: $BACKUP_DIR${NC}"
echo -e "${GREEN}========================================${NC}"