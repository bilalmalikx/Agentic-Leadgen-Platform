#!/bin/bash
# Deployment Script for Production

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}LeadGen Deployment Script${NC}"
echo -e "${GREEN}========================================${NC}"

# Load environment
if [ -f .env.production ]; then
    export $(cat .env.production | grep -v '^#' | xargs)
    echo -e "${GREEN}✅ Loaded production environment${NC}"
else
    echo -e "${YELLOW}⚠️  .env.production not found, using .env${NC}"
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

command -v docker >/dev/null 2>&1 || { echo -e "${RED}❌ Docker is required but not installed${NC}" >&2; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo -e "${RED}❌ Docker Compose is required but not installed${NC}" >&2; exit 1; }

echo -e "${GREEN}✅ Prerequisites OK${NC}"

# Pull latest images
echo -e "\n${YELLOW}Pulling latest images...${NC}"
docker-compose -f docker-compose.prod.yml pull

# Stop old containers
echo -e "\n${YELLOW}Stopping old containers...${NC}"
docker-compose -f docker-compose.prod.yml down

# Run migrations
echo -e "\n${YELLOW}Running database migrations...${NC}"
docker-compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# Start new containers
echo -e "\n${YELLOW}Starting new containers...${NC}"
docker-compose -f docker-compose.prod.yml up -d

# Health check
echo -e "\n${YELLOW}Waiting for services to be ready...${NC}"
sleep 10

# Check health
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)

if [ "$HEALTH_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Health check passed!${NC}"
else
    echo -e "${RED}❌ Health check failed! Status: $HEALTH_STATUS${NC}"
    echo -e "${YELLOW}Checking logs...${NC}"
    docker-compose -f docker-compose.prod.yml logs --tail=50 api
    exit 1
fi

# Show status
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
docker-compose -f docker-compose.prod.yml ps