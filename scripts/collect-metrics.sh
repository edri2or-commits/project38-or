#!/bin/bash
#
# Metrics Collection Script for project38-or
# Usage: ./scripts/collect-metrics.sh [--json]
#
# Collects and displays all available metrics from production.
#

set -e

PROD_URL="${PROD_URL:-https://or-infra.com}"
JSON_OUTPUT=${1:-""}

echo "=== Metrics Collection ==="
echo "URL: $PROD_URL"
echo "Time: $(date -Iseconds)"
echo ""

# Collect health
echo "--- Health Status ---"
HEALTH=$(curl -s --max-time 30 "$PROD_URL/api/health" 2>/dev/null) || HEALTH='{"error": "unreachable"}'
if [ "$JSON_OUTPUT" = "--json" ]; then
    echo "$HEALTH"
else
    echo "$HEALTH" | jq .
fi
echo ""

# Collect system metrics
echo "--- System Metrics ---"
SYSTEM=$(curl -s --max-time 30 "$PROD_URL/metrics/system" 2>/dev/null) || SYSTEM='{"error": "unreachable"}'
if [ "$JSON_OUTPUT" = "--json" ]; then
    echo "$SYSTEM"
else
    echo "$SYSTEM" | jq .
fi
echo ""

# Collect summary metrics
echo "--- Summary Metrics ---"
SUMMARY=$(curl -s --max-time 30 "$PROD_URL/metrics/summary" 2>/dev/null) || SUMMARY='{"error": "unreachable"}'
if [ "$JSON_OUTPUT" = "--json" ]; then
    echo "$SUMMARY"
else
    echo "$SUMMARY" | jq .
fi
echo ""

# Summary table
if [ "$JSON_OUTPUT" != "--json" ]; then
    echo "=== Quick Summary ==="
    STATUS=$(echo "$HEALTH" | jq -r '.status // "unknown"')
    DATABASE=$(echo "$HEALTH" | jq -r '.database // "unknown"')
    CPU=$(echo "$SYSTEM" | jq -r '.cpu_percent // "N/A"')
    MEMORY=$(echo "$SYSTEM" | jq -r '.memory_percent // "N/A"')
    DISK=$(echo "$SYSTEM" | jq -r '.disk_percent // "N/A"')

    printf "%-15s %s\n" "Status:" "$STATUS"
    printf "%-15s %s\n" "Database:" "$DATABASE"
    printf "%-15s %s%%\n" "CPU:" "$CPU"
    printf "%-15s %s%%\n" "Memory:" "$MEMORY"
    printf "%-15s %s%%\n" "Disk:" "$DISK"
    echo ""

    # Health assessment
    echo "=== Health Assessment ==="
    ISSUES=0

    if [ "$STATUS" != "healthy" ]; then
        echo "WARNING: Status is not healthy ($STATUS)"
        ISSUES=$((ISSUES + 1))
    fi

    if [ "$DATABASE" != "connected" ]; then
        echo "ERROR: Database not connected ($DATABASE)"
        ISSUES=$((ISSUES + 1))
    fi

    # Check resource thresholds (if values are numbers)
    if [[ "$CPU" =~ ^[0-9]+(\.[0-9]+)?$ ]] && (( $(echo "$CPU > 80" | bc -l) )); then
        echo "WARNING: CPU usage high ($CPU%)"
        ISSUES=$((ISSUES + 1))
    fi

    if [[ "$MEMORY" =~ ^[0-9]+(\.[0-9]+)?$ ]] && (( $(echo "$MEMORY > 85" | bc -l) )); then
        echo "WARNING: Memory usage high ($MEMORY%)"
        ISSUES=$((ISSUES + 1))
    fi

    if [[ "$DISK" =~ ^[0-9]+(\.[0-9]+)?$ ]] && (( $(echo "$DISK > 90" | bc -l) )); then
        echo "WARNING: Disk usage high ($DISK%)"
        ISSUES=$((ISSUES + 1))
    fi

    if [ $ISSUES -eq 0 ]; then
        echo "All systems operational"
    else
        echo ""
        echo "Total issues found: $ISSUES"
    fi
fi
