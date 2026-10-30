#!/bin/bash

# Health Check Script
# Verifies application is running correctly

set -e

# Configuration
APP_URL=${1:-http://localhost:8080}
TIMEOUT=10

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "CoreDent PMS Health Check"
echo "URL: $APP_URL"
echo "-----------------------------------"

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint=$1
    local expected_status=$2
    local description=$3
    
    echo -n "Checking $description... "
    
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$APP_URL$endpoint" || echo "000")
    
    if [ "$status" = "$expected_status" ]; then
        echo -e "${GREEN}✓ OK (HTTP $status)${NC}"
        return 0
    else
        echo -e "${RED}✗ FAILED (HTTP $status, expected $expected_status)${NC}"
        return 1
    fi
}

# Function to check response time
check_response_time() {
    local endpoint=$1
    local max_time=$2
    local description=$3
    
    echo -n "Checking $description response time... "
    
    time=$(curl -s -o /dev/null -w "%{time_total}" --max-time $TIMEOUT "$APP_URL$endpoint" || echo "999")
    time_ms=$(echo "$time * 1000" | bc)
    
    if (( $(echo "$time_ms < $max_time" | bc -l) )); then
        echo -e "${GREEN}✓ OK (${time_ms}ms)${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ SLOW (${time_ms}ms, expected <${max_time}ms)${NC}"
        return 1
    fi
}

# Run health checks
FAILED=0

# Check main page
check_endpoint "/" "200" "Main page" || ((FAILED++))

# Check health endpoint
check_endpoint "/health" "200" "Health endpoint" || ((FAILED++))

# Check static assets
check_endpoint "/assets" "404" "Assets directory (should 404)" || true

# Check response times
check_response_time "/" "2000" "Main page" || ((FAILED++))

# Check if JavaScript is loading
echo -n "Checking JavaScript bundle... "
if curl -s "$APP_URL/" | grep -q "script"; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

# Check if CSS is loading
echo -n "Checking CSS bundle... "
if curl -s "$APP_URL/" | grep -q "stylesheet"; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

# Check security headers
echo -n "Checking security headers... "
headers=$(curl -s -I "$APP_URL/" || echo "")

if echo "$headers" | grep -q "X-Frame-Options"; then
    echo -e "${GREEN}✓ Security headers present${NC}"
else
    echo -e "${YELLOW}⚠ Security headers missing${NC}"
    ((FAILED++))
fi

# Summary
echo ""
echo "-----------------------------------"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All health checks passed!${NC}"
    exit 0
else
    echo -e "${RED}$FAILED health check(s) failed${NC}"
    exit 1
fi
