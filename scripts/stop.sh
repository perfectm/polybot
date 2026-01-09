#!/bin/bash

# Polymarket Bot - Stop Script
# Gracefully stops the bot

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
PID_FILE="$PROJECT_DIR/data/bot.pid"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🛑 Stopping Polymarket Bot..."

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo -e "${YELLOW}⚠️  Bot is not running (no PID file found)${NC}"
    exit 0
fi

# Read PID
PID=$(cat "$PID_FILE")

# Check if process is actually running
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Bot process not found (PID: $PID)${NC}"
    echo "Cleaning up stale PID file..."
    rm "$PID_FILE"
    exit 0
fi

# Send SIGTERM for graceful shutdown
echo "📤 Sending shutdown signal to process $PID..."
kill -TERM "$PID"

# Wait for process to stop (max 30 seconds)
WAIT_TIME=0
MAX_WAIT=30

while ps -p "$PID" > /dev/null 2>&1; do
    if [ $WAIT_TIME -ge $MAX_WAIT ]; then
        echo -e "${RED}⚠️  Process did not stop gracefully, forcing shutdown...${NC}"
        kill -9 "$PID"
        sleep 1
        break
    fi
    sleep 1
    WAIT_TIME=$((WAIT_TIME + 1))
    echo -n "."
done

echo ""

# Clean up PID file
rm "$PID_FILE" 2>/dev/null

# Verify process stopped
if ps -p "$PID" > /dev/null 2>&1; then
    echo -e "${RED}❌ Failed to stop bot (PID: $PID)${NC}"
    exit 1
else
    echo -e "${GREEN}✅ Bot stopped successfully${NC}"
fi
