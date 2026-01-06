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

    Args:
        config: Configuration instance
        db: Database repository instance
        logger: Logger instance
    """
    logger.info("Starting monitoring loop...")
    logger.info(f"Poll interval: {config.poll_interval_seconds} seconds")

    from monitoring.data_collector import PolymarketDataCollector
    from detection.detection_orchestrator import DetectionOrchestrator

    # Initialize data collector
    collector = PolymarketDataCollector(
        base_url=config.polymarket_base_url,
        api_key=config.polymarket_api_key,
        timeout_seconds=config.api_timeout_seconds,
        max_retries=config.api_max_retries,
        backoff_factor=config.api_backoff_factor
    )

    # Initialize detection orchestrator
    detector = DetectionOrchestrator(
        db=db,
        large_bet_thresholds=config.get_large_bet_thresholds(),
        volume_percentage_threshold=config.large_bet_volume_percentage,
        statistical_sigma_threshold=config.large_bet_statistical_sigma,
        rapid_succession_bet_count=config.rapid_succession_bet_count,
        rapid_succession_time_window_minutes=config.rapid_succession_time_window_minutes,
        z_score_threshold=config.statistical_anomaly_z_score,
        iqr_multiplier=config.statistical_anomaly_iqr_multiplier,
        new_account_threshold_hours=config.new_account_threshold_hours,
        new_account_first_n_bets=config.new_account_first_n_bets,
        new_account_large_bet_threshold=config.new_account_large_bet_threshold,
        new_account_suspicious_first_bet_threshold=config.new_account_suspicious_first_bet_threshold
    )

    # Health check
    is_healthy = await collector.health_check()
    if not is_healthy:
        logger.error("Polymarket API health check failed. Continuing anyway...")

    # Main monitoring loop
    poll_count = 0
    stats_update_interval = 5  # Update statistics every 5 polls

    while not shutdown_event.is_set():
        try:
            poll_count += 1
            logger.info(f"Poll #{poll_count}: Fetching markets and trades...")

            # Update market statistics periodically
            if poll_count % stats_update_interval == 0:
                logger.info("Updating market statistics...")
                updated = detector.update_market_statistics(max_markets=config.max_markets)
                logger.info(f"Updated statistics for {updated} markets")

            # Fetch active markets
            markets = await collector.fetch_active_markets(limit=config.max_markets)
            logger.info(f"Found {len(markets)} active markets")

            # Store markets in database
            for market in markets:
                try:
                    db.upsert_market(market)
                except Exception as e:
                    logger.error(f"Error storing market: {e}")

            # Fetch recent trades for markets
            if markets:
                market_ids = [m['id'] for m in markets]
                trades = await collector.fetch_all_recent_trades(
                    market_ids=market_ids,
                    limit_per_market=20
                )
                logger.info(f"Found {len(trades)} recent trades")

                # Process each trade through detection system
                detections_count = 0
                alerts_created = 0

                for trade in trades:
                    try:
                        # Store bet in database
                        bet = db.insert_bet(trade)

                        # Run detection on bet
                        detection = detector.analyze_bet(bet)

                        if detection:
                            detections_count += 1
                            # Create alert
                            alert_id = detector.create_alert_from_detection(detection)
                            if alert_id:
                                alerts_created += 1

                    except Exception as e:
                        logger.error(f"Error processing bet: {e}")

                if detections_count > 0:
                    logger.info(
                        f"Poll #{poll_count}: Found {detections_count} detections, "
                        f"created {alerts_created} alerts"
                    )

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

    Args:
        config: Configuration instance
        db: Database repository instance
        logger: Logger instance
    """
    logger.info("Starting Discord bot...")

    try:
        from bot.discord_bot import PolymarketBot
        logger.info("Discord bot module imported")

        # Get color configuration
        color_config = {
            'critical': config.get_discord_embed_color('critical'),
            'high': config.get_discord_embed_color('high'),
            'medium': config.get_discord_embed_color('medium'),
            'low': config.get_discord_embed_color('low'),
        }
        logger.info("Color configuration loaded")

        # Initialize bot
        bot = PolymarketBot(
            db=db,
            alert_channel_id=config.discord_channel_id,
            color_config=color_config
        )
        logger.info("Bot instance created")

        # Start bot
        logger.info("Connecting to Discord...")
        token_preview = config.discord_bot_token[:20] + "..." if len(config.discord_bot_token) > 20 else "EMPTY_TOKEN"
        logger.info(f"Using Discord token: {token_preview}")
        logger.info(f"Alert channel ID: {config.discord_channel_id}")
        await bot.start(config.discord_bot_token)

    except Exception as e:
        logger.error(f"Discord bot error: {e}", exc_info=True)

    finally:
        if 'bot' in locals() and not bot.is_closed():
            await bot.shutdown()

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
            discord_bot_loop(config, db, logger),
            return_exceptions=True
        )

    except KeyboardInterrupt:
        if 'logger' in locals():
            logger.info("Keyboard interrupt received")
        else:
            print("Keyboard interrupt received")
    except Exception as e:
        if 'logger' in locals():
            logger.error(f"Fatal error: {e}", exc_info=True)
        else:
            print(f"Fatal error during initialization: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        return 1
    finally:
        # Cleanup
        if 'logger' in locals():
            logger.info("Shutting down...")
        if 'db' in locals():
            db.close()
        if 'logger' in locals():
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
