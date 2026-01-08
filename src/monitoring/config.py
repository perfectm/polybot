"""
Configuration management for Polymarket monitoring bot.

Loads configuration from:
- config/config.yaml: Business logic (thresholds, intervals, etc.)
- .env: Secrets (API keys, tokens)
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv


class Config:
    """Configuration manager that loads from YAML and environment variables."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialize configuration.

        Args:
            config_path: Path to YAML configuration file
        """
        # Load environment variables from .env file
        load_dotenv()

        # Load YAML configuration
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(self.config_path, 'r') as f:
            self._config: Dict[str, Any] = yaml.safe_load(f)

        # Validate required environment variables
        self._validate_env_vars()

    def _validate_env_vars(self):
        """Validate that required environment variables are set."""
        required_vars = [
            'DISCORD_BOT_TOKEN',
            'DISCORD_CHANNEL_ID',
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}. "
                f"Please check your .env file."
            )

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Args:
            key_path: Dot-separated path to config value (e.g., 'detection.large_bet.thresholds.critical')
            default: Default value if key not found

        Returns:
            Configuration value

        Example:
            >>> config.get('monitoring.poll_interval_seconds')
            45
        """
        keys = key_path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    # Environment variable getters
    @property
    def discord_bot_token(self) -> str:
        """Get Discord bot token from environment."""
        return os.getenv('DISCORD_BOT_TOKEN', '')

    @property
    def discord_channel_id(self) -> int:
        """Get Discord channel ID from environment."""
        return int(os.getenv('DISCORD_CHANNEL_ID', '0'))

    @property
    def polymarket_api_key(self) -> str:
        """Get Polymarket API key from environment (optional)."""
        return os.getenv('POLYMARKET_API_KEY', '')

    @property
    def polymarket_api_secret(self) -> str:
        """Get Polymarket API secret from environment (optional)."""
        return os.getenv('POLYMARKET_API_SECRET', '')

    @property
    def polymarket_passphrase(self) -> str:
        """Get Polymarket API passphrase from environment (optional)."""
        return os.getenv('POLYMARKET_PASSPHRASE', '')

    @property
    def polymarket_private_key(self) -> str:
        """Get Polymarket private key from environment (optional)."""
        return os.getenv('POLYMARKET_PRIVATE_KEY', '')

    @property
    def environment(self) -> str:
        """Get environment (development, production, etc.)."""
        return os.getenv('ENVIRONMENT', 'development')

    @property
    def log_level(self) -> str:
        """Get log level from environment."""
        return os.getenv('LOG_LEVEL', 'INFO').upper()

    @property
    def database_path(self) -> str:
        """Get database path."""
        return os.getenv('DATABASE_PATH', self.get('database.path', 'data/polymarket.db'))

    # Monitoring configuration
    @property
    def poll_interval_seconds(self) -> int:
        """Get polling interval in seconds."""
        return self.get('monitoring.poll_interval_seconds', 45)

    @property
    def batch_size(self) -> int:
        """Get batch size for fetching trades."""
        return self.get('monitoring.batch_size', 100)

    @property
    def max_markets(self) -> int:
        """Get maximum number of markets to monitor."""
        return self.get('monitoring.max_markets', 50)

    # Detection configuration
    def get_large_bet_thresholds(self) -> Dict[str, float]:
        """Get large bet detection thresholds."""
        return {
            'critical': self.get('detection.large_bet.thresholds.critical', 100000),
            'high': self.get('detection.large_bet.thresholds.high', 50000),
            'medium': self.get('detection.large_bet.thresholds.medium', 10000),
        }

    @property
    def large_bet_volume_percentage(self) -> float:
        """Get volume percentage threshold for large bets."""
        return self.get('detection.large_bet.volume_percentage', 5.0)

    @property
    def large_bet_statistical_sigma(self) -> float:
        """Get statistical sigma threshold for large bets."""
        return self.get('detection.large_bet.statistical_sigma', 3.0)

    @property
    def rapid_succession_bet_count(self) -> int:
        """Get bet count threshold for rapid succession detection."""
        return self.get('detection.rapid_succession.bet_count', 5)

    @property
    def rapid_succession_time_window_minutes(self) -> int:
        """Get time window in minutes for rapid succession detection."""
        return self.get('detection.rapid_succession.time_window_minutes', 5)

    @property
    def statistical_anomaly_z_score(self) -> float:
        """Get z-score threshold for statistical anomaly detection."""
        return self.get('detection.statistical_anomaly.z_score_threshold', 3.0)

    @property
    def statistical_anomaly_iqr_multiplier(self) -> float:
        """Get IQR multiplier for anomaly detection."""
        return self.get('detection.statistical_anomaly.iqr_multiplier', 1.5)

    @property
    def statistical_anomaly_ma_window_hours(self) -> int:
        """Get moving average window in hours for anomaly detection."""
        return self.get('detection.statistical_anomaly.ma_window_hours', 24)

    @property
    def new_account_threshold_hours(self) -> int:
        """Get new account threshold in hours."""
        return self.get('detection.new_account.new_account_threshold_hours', 72)

    @property
    def new_account_first_n_bets(self) -> int:
        """Get number of first bets to monitor for new accounts."""
        return self.get('detection.new_account.first_n_bets', 10)

    @property
    def new_account_large_bet_threshold(self) -> float:
        """Get large bet threshold for new accounts."""
        return self.get('detection.new_account.large_bet_threshold', 10000)

    @property
    def new_account_suspicious_first_bet_threshold(self) -> float:
        """Get suspicious first bet threshold for new accounts."""
        return self.get('detection.new_account.suspicious_first_bet_threshold', 50000)

    # API configuration
    @property
    def polymarket_base_url(self) -> str:
        """Get Polymarket API base URL."""
        return self.get('api.polymarket.base_url', 'https://clob.polymarket.com')

    @property
    def api_timeout_seconds(self) -> int:
        """Get API timeout in seconds."""
        return self.get('api.polymarket.timeout_seconds', 30)

    @property
    def api_max_retries(self) -> int:
        """Get maximum API retry attempts."""
        return self.get('api.polymarket.max_retries', 3)

    @property
    def api_rate_limit_calls(self) -> int:
        """Get API rate limit (calls per period)."""
        return self.get('api.polymarket.rate_limit_calls', 60)

    @property
    def api_rate_limit_period_seconds(self) -> int:
        """Get API rate limit period in seconds."""
        return self.get('api.polymarket.rate_limit_period_seconds', 60)

    @property
    def api_backoff_factor(self) -> int:
        """Get exponential backoff factor for retries."""
        return self.get('api.polymarket.backoff_factor', 2)

    # Discord configuration
    def get_discord_embed_color(self, severity: str) -> int:
        """
        Get Discord embed color for alert severity.

        Args:
            severity: Alert severity ('critical', 'high', 'medium', 'low')

        Returns:
            Hex color code as integer
        """
        color_map = {
            'critical': self.get('discord.embed_color.critical', 0xFF0000),
            'high': self.get('discord.embed_color.high', 0xFF6B35),
            'medium': self.get('discord.embed_color.medium', 0xFFD700),
            'low': self.get('discord.embed_color.low', 0x4169E1),
        }
        return color_map.get(severity.lower(), 0x808080)  # Default gray

    # Database configuration
    @property
    def database_echo(self) -> bool:
        """Get database echo setting (SQL query logging)."""
        return self.get('database.echo', False)

    @property
    def database_pool_size(self) -> int:
        """Get database connection pool size."""
        return self.get('database.pool_size', 5)

    @property
    def database_max_overflow(self) -> int:
        """Get database max overflow connections."""
        return self.get('database.max_overflow', 10)

    # Logging configuration
    @property
    def log_format(self) -> str:
        """Get logging format ('json' or 'text')."""
        return self.get('logging.format', 'json')

    @property
    def log_file_path(self) -> str:
        """Get log file path."""
        return self.get('logging.file_path', 'data/logs/bot.log')

    @property
    def log_max_bytes(self) -> int:
        """Get maximum log file size in bytes."""
        return self.get('logging.max_bytes', 10485760)  # 10MB

    @property
    def log_backup_count(self) -> int:
        """Get number of log file backups to keep."""
        return self.get('logging.backup_count', 5)

    @property
    def log_console_output(self) -> bool:
        """Get console logging setting."""
        return self.get('logging.console_output', True)

    def __repr__(self):
        return f"<Config(environment='{self.environment}', config_path='{self.config_path}')>"


# Global config instance (will be initialized in main.py)
_config_instance: Config | None = None


def get_config() -> Config:
    """
    Get global configuration instance.

    Returns:
        Config instance

    Raises:
        RuntimeError: If config not initialized
    """
    if _config_instance is None:
        raise RuntimeError("Configuration not initialized. Call init_config() first.")
    return _config_instance


def init_config(config_path: str = "config/config.yaml") -> Config:
    """
    Initialize global configuration.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Initialized Config instance
    """
    global _config_instance
    _config_instance = Config(config_path)
    return _config_instance
