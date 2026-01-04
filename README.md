# Polymarket Discord Monitoring Bot

A Python Discord bot that monitors Polymarket for suspicious betting activity including large bets and unusual patterns.

## Features

- **Large Bet Detection**: Multi-tiered detection system
  - Absolute thresholds ($10k, $50k, $100k+)
  - Market-relative detection (>5% of market volume)
  - Statistical detection (>3σ from mean)

- **Pattern Detection**: Identify unusual betting behavior
  - Rapid successive bets (same wallet, short timeframe)
  - Statistical anomalies (z-score, IQR methods)

- **Discord Integration**: Real-time alerts with rich embeds
  - Color-coded severity (Critical, High, Medium, Low)
  - Detailed bet context and market statistics
  - Interactive slash commands

- **Data Persistence**: SQLite database with full trade history
  - Track markets, bets, alerts, and statistics
  - Efficient indexing for fast queries

## Architecture

```
poly/
├── src/
│   ├── bot/               # Discord bot integration
│   ├── monitoring/        # Polymarket API monitoring
│   ├── detection/         # Anomaly detection algorithms
│   ├── database/          # Database models and repository
│   └── utils/             # Logging, rate limiting, etc.
├── config/                # Configuration files
├── tests/                 # Unit and integration tests
└── data/                  # Database and logs
```

## Prerequisites

- Python 3.11 or higher
- Discord bot token ([Create a bot](https://discord.com/developers/applications))
- Discord channel ID for alerts

## Installation

1. **Clone or navigate to the repository:**
   ```bash
   cd /Users/closet/projects/poly
   ```

2. **Create and activate virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env and add your Discord bot token and channel ID
   ```

5. **Configure detection settings (optional):**
   ```bash
   # Edit config/config.yaml to adjust thresholds
   ```

## Configuration

### Environment Variables (.env)

```bash
# Required
DISCORD_BOT_TOKEN=your_discord_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_for_alerts

# Optional
POLYMARKET_API_KEY=optional_polymarket_api_key
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### Detection Settings (config/config.yaml)

Key configurable parameters:

- `monitoring.poll_interval_seconds`: How often to check for new bets (default: 45s)
- `detection.large_bet.thresholds`: Alert thresholds for bet sizes
- `detection.rapid_succession.bet_count`: Number of bets to trigger rapid succession alert
- `detection.statistical_anomaly.z_score_threshold`: Z-score threshold for anomalies

## Usage

### Running the Bot

```bash
# Activate virtual environment
source venv/bin/activate

# Run the bot
python src/main.py
```

### Discord Commands

Once the bot is running, use these slash commands in Discord:

- `/status` - Show bot health and monitoring statistics
- `/markets` - List currently monitored markets
- `/alerts [timeframe]` - View recent alerts (1h, 24h, 7d)
- `/stats <market_id>` - Show detailed statistics for a market

## Development

### Project Structure

- **`src/database/models.py`**: SQLAlchemy ORM models
- **`src/monitoring/data_collector.py`**: Polymarket API integration
- **`src/detection/large_bet_detector.py`**: Large bet detection logic
- **`src/detection/pattern_detector.py`**: Pattern detection algorithms
- **`src/bot/discord_bot.py`**: Discord bot implementation
- **`src/main.py`**: Application entry point

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest tests/

# Run with coverage
pytest --cov=src tests/
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

## Database Schema

The bot uses SQLite with the following tables:

- **markets**: Polymarket market metadata
- **bets**: Individual bet/trade records
- **alerts**: Alerts sent to Discord
- **market_statistics**: Rolling statistics for anomaly detection
- **system_state**: System state tracking

## Deployment

### Using systemd (Linux)

1. Create systemd service file:

```ini
[Unit]
Description=Polymarket Discord Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/poly
ExecStart=/path/to/poly/venv/bin/python src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

2. Enable and start:

```bash
sudo systemctl enable polymarket-bot
sudo systemctl start polymarket-bot
sudo systemctl status polymarket-bot
```

### Using Docker

```bash
# Build image
docker build -t polymarket-bot .

# Run container
docker run -d --name polymarket-bot \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  polymarket-bot
```

## Monitoring

Logs are written to `data/logs/bot.log` in JSON format by default.

View logs:
```bash
tail -f data/logs/bot.log | jq
```

## Troubleshooting

### Bot won't start
- Verify `.env` file has correct Discord token and channel ID
- Check that virtual environment is activated
- Ensure all dependencies are installed: `pip install -r requirements.txt`

### No alerts appearing
- Verify Discord channel ID is correct
- Check bot has permissions to send messages in the channel
- Adjust detection thresholds in `config/config.yaml` if too restrictive

### Database errors
- Ensure `data/` directory exists and is writable
- Delete `data/polymarket.db` to reset database (will lose history)

## Future Enhancements

- Machine learning-based anomaly detection
- Web dashboard with real-time charts
- Multi-platform support (Telegram, SMS)
- Wallet reputation tracking
- Advanced pattern detection (coordinated activity, market impact)

## License

MIT License - See LICENSE file for details

## Support

For issues and feature requests, please open an issue on GitHub.
