#!/bin/bash
#
# Health Check Script for project38-or
# Usage: ./scripts/health-check.sh [--verbose]
#
# Returns:
#   0 - Production healthy
#   1 - Production unhealthy or unreachable
#

set -e

PROD_URL="${PROD_URL:-https://or-infra.com}"
VERBOSE=${1:-""}

echo "=== Production Health Check ==="
echo "URL: $PROD_URL"
echo "Time: $(date -Iseconds)"
echo ""

# Check health endpoint
echo "Checking health endpoint..."
HEALTH=$(curl -s --fail --max-time 30 "$PROD_URL/api/health" 2>/dev/null) || {
    echo "ERROR: Failed to reach health endpoint"
    exit 1
}

STATUS=$(echo "$HEALTH" | jq -r '.status // "unknown"')
DATABASE=$(echo "$HEALTH" | jq -r '.database // "unknown"')
VERSION=$(echo "$HEALTH" | jq -r '.version // "unknown"')
TIMESTAMP=$(echo "$HEALTH" | jq -r '.timestamp // "unknown"')

echo "  Status:    $STATUS"
echo "  Database:  $DATABASE"
echo "  Version:   $VERSION"
echo "  Timestamp: $TIMESTAMP"
echo ""

# Check system metrics (if verbose)
if [ "$VERBOSE" = "--verbose" ]; then
    echo "Checking system metrics..."
    METRICS=$(curl -s --max-time 30 "$PROD_URL/metrics/system" 2>/dev/null) || {
        echo "  WARNING: Could not fetch system metrics"
        METRICS="{}"
    }

    CPU=$(echo "$METRICS" | jq -r '.cpu_percent // "N/A"')
    MEMORY=$(echo "$METRICS" | jq -r '.memory_percent // "N/A"')
    DISK=$(echo "$METRICS" | jq -r '.disk_percent // "N/A"')

    echo "  CPU:    $CPU%"
    echo "  Memory: $MEMORY%"
    echo "  Disk:   $DISK%"
    echo ""
fi

# Determine result
if [ "$STATUS" = "healthy" ] && [ "$DATABASE" = "connected" ]; then
    echo "RESULT: Production is HEALTHY"
    exit 0
elif [ "$STATUS" = "degraded" ]; then
    echo "RESULT: Production is DEGRADED (database: $DATABASE)"
    exit 1
else
    echo "RESULT: Production is UNHEALTHY"
    echo "Full response: $HEALTH"
    exit 1
fi
