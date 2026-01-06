# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python Discord bot that monitors Polymarket for suspicious betting activity. The bot continuously polls Polymarket's API, runs detection algorithms on bets, stores data in SQLite, and sends real-time alerts to Discord.

## Key Commands

### Running the Bot
```bash
# Activate virtual environment
source venv/bin/activate

# Run the main bot
python src/main.py
```

### Testing
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=src tests/

# Run single test file
pytest tests/test_detectors.py -v
```

### Code Quality
```bash
# Format code
black src/ tests/

# Lint
flake8 src/ tests/

# Type checking
mypy src/
```

## Architecture Overview

The application runs two concurrent async loops:

1. **Monitoring Loop** (`src/main.py:monitoring_loop`): Polls Polymarket API every 45s, stores bets in database, runs detection algorithms, creates alerts
2. **Discord Bot Loop** (`src/main.py:discord_bot_loop`): Maintains Discord connection, handles slash commands, periodically checks for unsent alerts and sends them

### Core Components

**Detection Pipeline** (`src/detection/detection_orchestrator.py`):
- Entry point: `DetectionOrchestrator.analyze_bet()` runs all detectors on a single bet
- Combines results from 3 detector types: `LargeBetDetector`, `PatternDetector`, `NewAccountDetector`
- Returns `UnifiedDetection` if any detector triggers
- Creates alerts via `create_alert_from_detection()`

**Data Flow**:
1. `PolymarketDataCollector` fetches markets and trades from Polymarket CLOB API
2. Trades stored as `Bet` records in database via `DatabaseRepository`
3. Each bet passed to `DetectionOrchestrator.analyze_bet()`
4. Detections create `Alert` records (marked `sent_to_discord=False`)
5. Discord bot's background task (`check_alerts_task`) polls for unsent alerts and sends embeds

**Database Layer** (`src/database/`):
- Models: `Market`, `Bet`, `Alert`, `MarketStatistics`, `SystemState`
- Repository pattern: All DB operations go through `DatabaseRepository`
- SQLite with SQLAlchemy ORM

**Discord Integration** (`src/bot/`):
- `PolymarketBot`: Main bot class with slash commands (`/status`, `/markets`, `/alerts`, `/stats`)
- `AlertFormatter`: Creates Discord embeds from alert data
- Background task periodically checks for unsent alerts and sends them to configured channel

### Detection Algorithms

**Large Bet Detection** (`src/detection/large_bet_detector.py`):
- Three tiers: absolute thresholds ($10k/$50k/$100k), market volume percentage (>5%), statistical sigma (>3σ from mean)
- Requires `MarketStatistics` to be computed for statistical detection

**Pattern Detection** (`src/detection/pattern_detector.py`):
- Rapid succession: Same wallet, N bets in M minutes (default: 5 bets in 5 min)
- Statistical anomaly: Z-score and IQR methods comparing bet to market statistics

**New Account Detection** (`src/detection/new_account_detector.py`):
- Detects wallets' first N bets (default: first 10 bets within 72 hours of first activity)
- Flags large first bets (>$10k) or suspicious first bets (>$50k)

### Configuration

All thresholds and settings in `config/config.yaml`. Key sections:
- `monitoring`: Poll intervals, batch sizes
- `detection`: Enable/disable detectors, configure thresholds
- `database`: DB path and connection settings
- `discord`: Embed colors, message formatting
- `api.polymarket`: Rate limiting, retries, timeouts

Environment variables in `.env` (required):
- `DISCORD_BOT_TOKEN`: Discord bot authentication
- `DISCORD_CHANNEL_ID`: Channel for alerts
- `POLYMARKET_API_KEY`: Optional Polymarket API key

## Important Implementation Details

**Async Architecture**:
- Main entry point uses `asyncio.gather()` to run monitoring and Discord loops concurrently
- Polymarket client (`py-clob-client`) is synchronous, so wrapped with `loop.run_in_executor()`
- Graceful shutdown via `shutdown_event` triggered by SIGINT/SIGTERM

**Statistics Updates**:
- `MarketStatistics` updated every 5 polls (not every poll) for performance
- Statistics required for statistical-based detection methods
- Calculated by `MarketStatisticsCalculator` over 24-hour rolling window

**Alert Deduplication**:
- Bot stores alerts in database first, then Discord bot sends them
- This allows monitoring loop to continue even if Discord is down
- Discord bot task periodically checks for unsent alerts

**Database Indexing**:
- Heavy indexing on common query patterns (market_id, timestamp, address)
- Composite indexes on `(market_id, timestamp)` for efficient bet lookups

## Testing Notes

- Test fixtures in `tests/fixtures/`
- Main test file: `tests/test_detectors.py`
- Tests use in-memory SQLite database
- Mock Polymarket API responses for integration tests
