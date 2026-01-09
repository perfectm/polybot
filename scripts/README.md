# Bot Management Scripts

Shell scripts to easily manage the Polymarket Discord monitoring bot.

## Scripts

### 🚀 start.sh
Starts the bot in the background.

```bash
./scripts/start.sh
```

**Features:**
- Checks if bot is already running
- Activates virtual environment automatically
- Runs bot as background process
- Saves PID to `data/bot.pid`
- Logs output to `data/logs/bot_console.log`

**Output:**
```
🤖 Starting Polymarket Bot...
✅ Bot started successfully (PID: 12345)
📄 Logs: /Users/closet/projects/poly/data/logs/bot_console.log
🔍 Use './scripts/status.sh' to check status
🛑 Use './scripts/stop.sh' to stop the bot
```

---

### 🛑 stop.sh
Gracefully stops the bot.

```bash
./scripts/stop.sh
```

**Features:**
- Sends SIGTERM for graceful shutdown
- Waits up to 30 seconds for clean exit
- Forces shutdown if needed (SIGKILL)
- Cleans up PID file

**Output:**
```
🛑 Stopping Polymarket Bot...
📤 Sending shutdown signal to process 12345...
.....
✅ Bot stopped successfully
```

---

### 🔄 restart.sh
Restarts the bot (stop + start).

```bash
./scripts/restart.sh
```

Equivalent to running `stop.sh` followed by `start.sh`.

---

### 🔍 status.sh
Shows detailed bot status and statistics.

```bash
./scripts/status.sh
```

**Displays:**
- Running status (PID, CPU, Memory, Uptime)
- Database statistics (Markets, Bets, Alerts)
- Recent log entries
- Last bet timestamp

**Example Output:**
```
═══════════════════════════════════════════════════
    🤖 Polymarket Bot Status
═══════════════════════════════════════════════════

Status: ● Running
PID: 12345

─── Process Info ───
  CPU: 0.5%
  Memory: 1.2% (45678 KB)
  Uptime: 02:34:12

─── Database Stats ───
  Markets: 50
  Bets: 342
  Alerts: 26 (Sent: 26, Pending: 0)
  Last Bet: 2026-01-09 12:08:42

─── Recent Logs (last 5 lines) ───
  Poll #10 complete. Waiting 45s...
  ...

📄 Full logs: /Users/closet/projects/poly/data/logs/bot_console.log

─── Commands ───
  Stop:    ./scripts/stop.sh
  Restart: ./scripts/restart.sh
  Logs:    tail -f /Users/closet/projects/poly/data/logs/bot_console.log
```

---

## Common Workflows

### Starting the bot for the first time
```bash
# Make sure virtual environment is set up
source venv/bin/activate
pip install -r requirements.txt

# Start the bot
./scripts/start.sh
```

### Checking if bot is running
```bash
./scripts/status.sh
```

### Viewing live logs
```bash
tail -f data/logs/bot_console.log

# Or for JSON logs:
tail -f data/logs/bot.log | jq .
```

### Applying configuration changes
```bash
# Edit configuration
nano config/config.yaml

# Restart bot to apply changes
./scripts/restart.sh
```

### Troubleshooting
```bash
# Check status
./scripts/status.sh

# View recent logs
tail -n 50 data/logs/bot_console.log

# View JSON logs with jq
tail -n 50 data/logs/bot.log | jq .

# Stop and restart
./scripts/stop.sh
./scripts/start.sh
```

---

## Files Created

- **data/bot.pid** - Process ID of running bot
- **data/logs/bot_console.log** - Console output (stdout/stderr)
- **data/logs/bot.log** - Structured JSON logs

---

## Requirements

- Bash shell
- Python 3.11+
- Virtual environment set up in `venv/`
- SQLite3 (for status script database queries)

---

## Notes

- All scripts should be run from the project root directory
- The bot must be properly configured with `.env` file before starting
- Logs are appended, not overwritten (use logrotate for production)
- PID file prevents multiple instances from running simultaneously
