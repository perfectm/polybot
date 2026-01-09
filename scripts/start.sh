#!/bin/bash

# Polymarket Bot - Start Script
# Starts the bot in the background

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
PID_FILE="$PROJECT_DIR/data/bot.pid"
LOG_FILE="$PROJECT_DIR/data/logs/bot_console.log"
VENV_DIR="$PROJECT_DIR/venv"
PYTHON_SCRIPT="$PROJECT_DIR/src/main.py"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🤖 Starting Polymarket Bot..."

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Bot is already running (PID: $PID)${NC}"
        exit 1
    else
        echo -e "${YELLOW}⚠️  Stale PID file found, removing...${NC}"
        rm "$PID_FILE"
    fi
fi

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}❌ Virtual environment not found at $VENV_DIR${NC}"
    echo "Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Create data directory if it doesn't exist
mkdir -p "$PROJECT_DIR/data/logs"

# Activate virtual environment and start the bot
cd "$PROJECT_DIR"
source "$VENV_DIR/bin/activate"

# Start bot in background, redirect output to log file
nohup python "$PYTHON_SCRIPT" >> "$LOG_FILE" 2>&1 &
BOT_PID=$!

# Save PID to file
echo "$BOT_PID" > "$PID_FILE"

# Wait a moment to check if it started successfully
sleep 2

if ps -p "$BOT_PID" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Bot started successfully (PID: $BOT_PID)${NC}"
    echo "📄 Logs: $LOG_FILE"
    echo "🔍 Use './scripts/status.sh' to check status"
    echo "🛑 Use './scripts/stop.sh' to stop the bot"
else
    echo -e "${RED}❌ Bot failed to start${NC}"
    echo "Check logs at: $LOG_FILE"
    rm "$PID_FILE" 2>/dev/null
    exit 1
fi
