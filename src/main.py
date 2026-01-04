"""
Polymarket Discord Monitoring Bot - Main Entry Point

This bot monitors Polymarket for suspicious betting activity and sends
alerts to Discord.
"""

import asyncio
import signal
import sys
from pathlib import Path

from monitoring.config import init_config, get_config
from database.repository import DatabaseRepository
from utils.logger import init_logging, get_logger


# Global flag for graceful shutdown
shutdown_event = asyncio.Event()


def signal_handler(signum, frame):
    """Handle shutdown signals (SIGTERM, SIGINT)."""
    logger = get_logger()
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()


async def initialize_bot() -> tuple:
    """
    Initialize bot components.

    Returns:
        Tuple of (config, database_repository, logger)
    """
    # Initialize configuration
    config = init_config()
    print(f"Configuration loaded from config/config.yaml")
    print(f"Environment: {config.environment}")
    print(f"Log level: {config.log_level}")

    # Initialize logging
    logger = init_logging(
        log_level=config.log_level,
        log_format=config.log_format,
        log_file_path=config.log_file_path,
        max_bytes=config.log_max_bytes,
        backup_count=config.log_backup_count,
        console_output=config.log_console_output
    )
    logger.info("Polymarket Discord Monitoring Bot starting...")
    logger.info(f"Environment: {config.environment}")

    # Ensure data directory exists
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    (data_dir / "logs").mkdir(exist_ok=True)

    # Initialize database
    db = DatabaseRepository(
        database_path=config.database_path,
        echo=config.database_echo
    )
    db.create_tables()
    logger.info(f"Database initialized at {config.database_path}")

    return config, db, logger


async def monitoring_loop(config, db, logger):
    """
    Main monitoring loop - polls Polymarket and detects suspicious activity.

    This is a placeholder for Phase 4 implementation.

    Args:
        config: Configuration instance
        db: Database repository instance
        logger: Logger instance
    """
    logger.info("Starting monitoring loop...")
    logger.info(f"Poll interval: {config.poll_interval_seconds} seconds")

    # TODO: Phase 2 - Implement detection engine
    # TODO: Phase 3 - Implement Discord integration
    # TODO: Phase 4 - Implement full monitoring loop

    from monitoring.data_collector import PolymarketDataCollector

    # Initialize data collector
    collector = PolymarketDataCollector(
        base_url=config.polymarket_base_url,
        api_key=config.polymarket_api_key,
        timeout_seconds=config.api_timeout_seconds,
        max_retries=config.api_max_retries,
        backoff_factor=config.api_backoff_factor
    )

    # Health check
    is_healthy = await collector.health_check()
    if not is_healthy:
        logger.error("Polymarket API health check failed. Continuing anyway...")

    # Main monitoring loop
    poll_count = 0
    while not shutdown_event.is_set():
        try:
            poll_count += 1
            logger.info(f"Poll #{poll_count}: Fetching markets and trades...")

            # Fetch active markets
            markets = await collector.fetch_active_markets(limit=config.max_markets)
            logger.info(f"Found {len(markets)} active markets")

            # Store markets in database
            for market in markets[:5]:  # Limit to top 5 for testing
                try:
                    db.upsert_market(market)
                    logger.debug(f"Stored market: {market['question'][:50]}...")
                except Exception as e:
                    logger.error(f"Error storing market: {e}")

            # Fetch recent trades for top markets
            if markets:
                market_ids = [m['id'] for m in markets[:5]]
                trades = await collector.fetch_all_recent_trades(
                    market_ids=market_ids,
                    limit_per_market=10
                )
                logger.info(f"Found {len(trades)} recent trades")

                # Store trades in database
                for trade in trades[:20]:  # Limit for testing
                    try:
                        db.insert_bet(trade)
                        logger.debug(
                            f"Stored bet: ${trade['size']:.2f} on {trade['market_id'][:10]}..."
                        )
                    except Exception as e:
                        logger.error(f"Error storing bet: {e}")

            logger.info(f"Poll #{poll_count} complete. Waiting {config.poll_interval_seconds}s...")

            # Wait for next poll (or shutdown signal)
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=config.poll_interval_seconds
                )
            except asyncio.TimeoutError:
                # Timeout is expected - continue to next poll
                pass

        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}", exc_info=True)
            # Wait before retrying
            await asyncio.sleep(10)

    logger.info("Monitoring loop stopped")


async def discord_bot_loop(config, db, logger):
    """
    Discord bot loop - handles Discord connection and commands.

    This is a placeholder for Phase 3 implementation.

    Args:
        config: Configuration instance
        db: Database repository instance
        logger: Logger instance
    """
    logger.info("Discord bot loop placeholder (Phase 3)")

    # TODO: Phase 3 - Implement Discord bot
    # - Initialize discord.py bot
    # - Connect to Discord
    # - Register slash commands
    # - Listen for unsent alerts and send them

    # For now, just wait for shutdown
    await shutdown_event.wait()
    logger.info("Discord bot loop stopped")


async def main():
    """Main async entry point."""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize bot components
        config, db, logger = await initialize_bot()

        logger.info("Bot initialization complete")
        logger.info("=" * 60)
        logger.info("Polymarket Discord Monitoring Bot is running")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)

        # Run monitoring and Discord loops concurrently
        await asyncio.gather(
            monitoring_loop(config, db, logger),
            # discord_bot_loop(config, db, logger),  # Enable in Phase 3
            return_exceptions=True
        )

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    finally:
        # Cleanup
        logger.info("Shutting down...")
        if 'db' in locals():
            db.close()
        logger.info("Shutdown complete")

    return 0


if __name__ == "__main__":
    """Entry point when running as script."""
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
