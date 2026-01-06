"""
Structured logging configuration for Polymarket monitoring bot.

Provides JSON and text logging formats with rotation support.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from pythonjsonlogger.jsonlogger import JsonFormatter
from typing import Optional


class CustomJsonFormatter(JsonFormatter):
    """Custom JSON formatter with additional fields."""

    def add_fields(self, log_record, record, message_dict):
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record['timestamp'] = self.formatTime(record, self.datefmt)
        log_record['level'] = record.levelname
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno

        # Include exception info if present
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)


def setup_logger(
    name: str = 'polymarket_bot',
    log_level: str = 'INFO',
    log_format: str = 'json',
    log_file_path: Optional[str] = None,
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5,
    console_output: bool = True
) -> logging.Logger:
    """
    Set up structured logger with file rotation and optional console output.

    Args:
        name: Logger name
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type ('json' or 'text')
        log_file_path: Path to log file (None for no file logging)
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
        console_output: Whether to output logs to console

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter based on format type
    if log_format == 'json':
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler with rotation
    if log_file_path:
        # Ensure log directory exists
        log_path = Path(log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = 'polymarket_bot') -> logging.Logger:
    """
    Get logger instance by name.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Module-level logger for utils
_logger: Optional[logging.Logger] = None


def init_logging(
    log_level: str = 'INFO',
    log_format: str = 'json',
    log_file_path: Optional[str] = None,
    max_bytes: int = 10485760,
    backup_count: int = 5,
    console_output: bool = True
) -> logging.Logger:
    """
    Initialize global logging configuration.

    Args:
        log_level: Logging level
        log_format: Format type ('json' or 'text')
        log_file_path: Path to log file
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
        console_output: Whether to output logs to console

    Returns:
        Configured logger instance
    """
    global _logger
    _logger = setup_logger(
        name='polymarket_bot',
        log_level=log_level,
        log_format=log_format,
        log_file_path=log_file_path,
        max_bytes=max_bytes,
        backup_count=backup_count,
        console_output=console_output
    )
    return _logger


def log_with_context(logger: logging.Logger, level: str, message: str, **context):
    """
    Log message with additional context fields.

    Args:
        logger: Logger instance
        level: Log level ('debug', 'info', 'warning', 'error', 'critical')
        message: Log message
        **context: Additional context fields to include in log

    Example:
        >>> log_with_context(
        ...     logger,
        ...     'info',
        ...     'Fetched trades',
        ...     market_id='0x123',
        ...     trade_count=15,
        ...     duration_ms=234
        ... )
    """
    log_func = getattr(logger, level.lower())
    log_func(message, extra={'context': context})
