#!/bin/bash
# Rollback Script for Production

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}========================================${NC}"
echo -e "${RED}⚠️  ROLLBACK SCRIPT ⚠️${NC}"
echo -e "${RED}========================================${NC}"

# Get previous version
PREVIOUS_VERSION=$(docker ps -a --filter "name=leadgen-api" --format "{{.Image}}" | head -1 | cut -d: -f2)

if [ -z "$PREVIOUS_VERSION" ]; then
    echo -e "${RED}❌ No previous version found${NC}"
    exit 1
fi

echo -e "${YELLOW}Rolling back to version: $PREVIOUS_VERSION${NC}"

# Stop current containers
echo -e "\n${YELLOW}Stopping current containers...${NC}"
docker-compose -f docker-compose.prod.yml down

# Revert to previous version
echo -e "\n${YELLOW}Reverting to previous version...${NC}"
export TAG=$PREVIOUS_VERSION
docker-compose -f docker-compose.prod.yml up -d

# Health check
echo -e "\n${YELLOW}Checking health...${NC}"
sleep 10

HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)

if [ "$HEALTH_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Rollback successful!${NC}"
else
    echo -e "${RED}❌ Rollback failed! Health check failed${NC}"
    exit 1
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Rollback completed!${NC}"
echo -e "${GREEN}========================================${NC}"