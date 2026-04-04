#!/bin/bash
# Health Check Script for Monitoring

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

API_URL=${API_URL:-"http://localhost:8000"}
TIMEOUT=10

echo -e "${YELLOW}Running health checks...${NC}\n"

# Function to check endpoint
check_endpoint() {
    local endpoint=$1
    local expected_status=$2
    local name=$3
    
    response=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$API_URL$endpoint")
    
    if [ "$response" = "$expected_status" ]; then
        echo -e "  ${GREEN}✅ $name: $response${NC}"
        return 0
    else
        echo -e "  ${RED}❌ $name: Expected $expected_status, got $response${NC}"
        return 1
    fi
}

# Run checks
FAILED=0

echo "API Health Checks:"
check_endpoint "/health" "200" "Health endpoint" || FAILED=1
check_endpoint "/ready" "200" "Readiness probe" || FAILED=1
check_endpoint "/" "200" "Root endpoint" || FAILED=1

echo -e "\nDatabase Check:"
if curl -s "$API_URL/health" | grep -q '"database":"healthy"'; then
    echo -e "  ${GREEN}✅ Database is healthy${NC}"
else
    echo -e "  ${RED}❌ Database is unhealthy${NC}"
    FAILED=1
fi

echo -e "\nRedis Check:"
if curl -s "$API_URL/health" | grep -q '"redis":"healthy"'; then
    echo -e "  ${GREEN}✅ Redis is healthy${NC}"
else
    echo -e "  ${RED}❌ Redis is unhealthy${NC}"
    FAILED=1
fi

# Final result
echo -e "\n========================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All health checks passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some health checks failed!${NC}"
    exit 1
fi