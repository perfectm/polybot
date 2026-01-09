#!/bin/bash

# Polymarket Bot - Restart Script
# Stops and then starts the bot

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔄 Restarting Polymarket Bot...${NC}"
echo ""

# Stop the bot
"$SCRIPT_DIR/stop.sh"

# Wait a moment
sleep 2

echo ""

# Start the bot
"$SCRIPT_DIR/start.sh"
