#!/bin/bash

# Polymarket Bot - Status Script
# Shows bot status and runtime information

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
PID_FILE="$PROJECT_DIR/data/bot.pid"
LOG_FILE="$PROJECT_DIR/data/logs/bot_console.log"
DB_FILE="$PROJECT_DIR/data/polymarket.db"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "═══════════════════════════════════════════════════"
echo "    🤖 Polymarket Bot Status"
echo "═══════════════════════════════════════════════════"
echo ""

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo -e "Status: ${RED}●${NC} Not Running"
    echo ""
    exit 0
fi

# Read PID
PID=$(cat "$PID_FILE")

# Check if process is running
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo -e "Status: ${RED}●${NC} Not Running (stale PID file)"
    echo "PID File: $PID_FILE"
    echo ""
    echo "⚠️  Clean up with: rm $PID_FILE"
    exit 0
fi

# Bot is running - show details
echo -e "Status: ${GREEN}●${NC} Running"
echo "PID: $PID"
echo ""

# Show process info
echo "─── Process Info ───"
ps -p "$PID" -o pid,ppid,etime,pcpu,pmem,vsz,rss,command | tail -n +2 | awk '{
    printf "  CPU: %s%%\n", $4
    printf "  Memory: %s%% (%s KB)\n", $5, $7
    printf "  Uptime: %s\n", $3
}'
echo ""

# Show database stats
if [ -f "$DB_FILE" ]; then
    echo "─── Database Stats ───"

    # Get market count
    MARKET_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM markets;" 2>/dev/null || echo "0")
    echo "  Markets: $MARKET_COUNT"

    # Get bet count
    BET_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM bets;" 2>/dev/null || echo "0")
    echo "  Bets: $BET_COUNT"

    # Get alert count
    ALERT_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM alerts;" 2>/dev/null || echo "0")
    SENT_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM alerts WHERE sent_to_discord = 1;" 2>/dev/null || echo "0")
    PENDING_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM alerts WHERE sent_to_discord = 0;" 2>/dev/null || echo "0")
    echo "  Alerts: $ALERT_COUNT (Sent: $SENT_COUNT, Pending: $PENDING_COUNT)"

    # Get last bet timestamp
    LAST_BET=$(sqlite3 "$DB_FILE" "SELECT timestamp FROM bets ORDER BY timestamp DESC LIMIT 1;" 2>/dev/null || echo "None")
    echo "  Last Bet: $LAST_BET"

    echo ""
fi

# Show recent log tail
if [ -f "$LOG_FILE" ]; then
    echo "─── Recent Logs (last 5 lines) ───"
    tail -n 5 "$LOG_FILE" | sed 's/^/  /'
    echo ""
    echo "📄 Full logs: $LOG_FILE"
fi

echo ""
echo "─── Commands ───"
echo "  Stop:    ./scripts/stop.sh"
echo "  Restart: ./scripts/restart.sh"
echo "  Logs:    tail -f $LOG_FILE"
echo ""
