"""
Discord bot for Polymarket monitoring alerts.

Handles connection, commands, and alert delivery.
"""

import discord
from discord import app_commands
from discord.ext import tasks
import asyncio
from typing import Optional, List
from datetime import datetime, timedelta

from database.repository import DatabaseRepository
from bot.formatters import AlertFormatter
from utils.logger import get_logger

logger = get_logger(__name__)


class PolymarketBot(discord.Client):
    """Discord bot for Polymarket monitoring."""

    def __init__(
        self,
        db: DatabaseRepository,
        alert_channel_id: int,
        color_config: Optional[dict] = None,
        max_alerts_per_hour: int = 60,
        max_alerts_per_batch: int = 2,
        delay_between_alerts: int = 15
    ):
        """
        Initialize Polymarket Discord bot.

        Args:
            db: Database repository
            alert_channel_id: Discord channel ID for alerts
            color_config: Color configuration for embeds
            max_alerts_per_hour: Maximum alerts per hour (default: 60)
            max_alerts_per_batch: Maximum alerts per check cycle (default: 2)
            delay_between_alerts: Seconds between individual alerts (default: 15)
        """
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(intents=intents)

        self.db = db
        self.alert_channel_id = alert_channel_id
        self.formatter = AlertFormatter(color_config)
        self.tree = app_commands.CommandTree(self)
        self.is_ready = False
        self.alert_channel: Optional[discord.TextChannel] = None

        # Statistics
        self.start_time = datetime.utcnow()
        self.alerts_sent = 0
        self.errors_count = 0

        # Rate limiting (configurable)
        self.alerts_sent_last_hour = []  # Track timestamps of sent alerts
        self.max_alerts_per_hour = max_alerts_per_hour
        self.max_alerts_per_batch = max_alerts_per_batch
        self.delay_between_alerts = delay_between_alerts

        logger.info(f"Polymarket bot initialized with rate limiting: "
                   f"{max_alerts_per_hour}/hour, {max_alerts_per_batch}/batch, "
                   f"{delay_between_alerts}s delay")

    async def setup_hook(self):
        """Set up bot commands and tasks."""
        # Register slash commands
        await self._register_commands()

        # Start background tasks
        self.check_alerts_task.start()

        logger.info("Bot setup hook complete")

    async def on_ready(self):
        """Event handler for when bot is ready."""
        logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")

        # Get alert channel
        try:
            self.alert_channel = self.get_channel(self.alert_channel_id)
            if self.alert_channel is None:
                self.alert_channel = await self.fetch_channel(self.alert_channel_id)

            if self.alert_channel:
                logger.info(f"Alert channel found: {self.alert_channel.name}")
            else:
                logger.error(f"Alert channel not found: {self.alert_channel_id}")

        except Exception as e:
            logger.error(f"Error fetching alert channel: {e}", exc_info=True)

        # Sync commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Error syncing commands: {e}", exc_info=True)

        self.is_ready = True

        # Send startup message
        if self.alert_channel:
            await self._send_startup_message()

    async def on_error(self, event_method: str, *args, **kwargs):
        """Event handler for errors."""
        logger.error(f"Discord error in {event_method}", exc_info=True)
        self.errors_count += 1

    async def _send_startup_message(self):
        """Send bot startup message to alert channel."""
        try:
            embed = discord.Embed(
                title="✅ Polymarket Monitor Bot Online",
                description="Bot is now monitoring for suspicious betting activity.",
                color=0x00FF00,
                timestamp=datetime.utcnow()
            )

            embed.add_field(
                name="Status",
                value="🟢 All systems operational",
                inline=False
            )

            await self.alert_channel.send(embed=embed)
            logger.info("Startup message sent")

        except Exception as e:
            logger.error(f"Error sending startup message: {e}", exc_info=True)

    async def _register_commands(self):
        """Register slash commands."""

        @self.tree.command(name="status", description="Show bot status and statistics")
        async def status_command(interaction: discord.Interaction):
            """Show bot status."""
            await self._handle_status_command(interaction)

        @self.tree.command(name="markets", description="List currently monitored markets")
        async def markets_command(interaction: discord.Interaction):
            """List monitored markets."""
            await self._handle_markets_command(interaction)

        @self.tree.command(name="alerts", description="Show recent alerts")
        @app_commands.describe(timeframe="Time period (1h, 24h, 7d)")
        async def alerts_command(interaction: discord.Interaction, timeframe: str = "24h"):
            """Show recent alerts."""
            await self._handle_alerts_command(interaction, timeframe)

        logger.info("Commands registered")

    async def _handle_status_command(self, interaction: discord.Interaction):
        """Handle /status command."""
        try:
            await interaction.response.defer()

            uptime = datetime.utcnow() - self.start_time
            uptime_hours = uptime.total_seconds() / 3600

            # Get statistics
            markets = self.db.get_active_markets(limit=100)
            recent_alerts = self.db.get_recent_alerts(hours=24)

            embed = discord.Embed(
                title="📊 Bot Status",
                color=0x0099FF,
                timestamp=datetime.utcnow()
            )

            embed.add_field(
                name="🟢 Status",
                value="Online and Monitoring",
                inline=True
            )

            embed.add_field(
                name="⏱️ Uptime",
                value=f"{uptime_hours:.1f} hours",
                inline=True
            )

            embed.add_field(
                name="📈 Markets Monitored",
                value=f"{len(markets)}",
                inline=True
            )

            embed.add_field(
                name="🔔 Alerts (24h)",
                value=f"{len(recent_alerts)}",
                inline=True
            )

            embed.add_field(
                name="📤 Total Alerts Sent",
                value=f"{self.alerts_sent}",
                inline=True
            )

            embed.add_field(
                name="❌ Errors",
                value=f"{self.errors_count}",
                inline=True
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error handling status command: {e}", exc_info=True)
            await interaction.followup.send("Error retrieving status", ephemeral=True)

    async def _handle_markets_command(self, interaction: discord.Interaction):
        """Handle /markets command."""
        try:
            await interaction.response.defer()

            markets = self.db.get_active_markets(limit=25)

            if not markets:
                await interaction.followup.send("No active markets found", ephemeral=True)
                return

            embed = discord.Embed(
                title="📊 Monitored Markets",
                description=f"Showing top {len(markets)} markets by volume",
                color=0x0099FF,
                timestamp=datetime.utcnow()
            )

            for i, market in enumerate(markets[:10], 1):
                volume_text = f"${market.total_volume:,.0f}" if market.total_volume > 0 else "N/A"
                embed.add_field(
                    name=f"{i}. {market.question[:60]}...",
                    value=f"Volume: {volume_text}",
                    inline=False
                )

            if len(markets) > 10:
                embed.set_footer(text=f"Showing 10 of {len(markets)} markets")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error handling markets command: {e}", exc_info=True)
            await interaction.followup.send("Error retrieving markets", ephemeral=True)

    async def _handle_alerts_command(self, interaction: discord.Interaction, timeframe: str):
        """Handle /alerts command."""
        try:
            await interaction.response.defer()

            # Parse timeframe
            timeframe_hours = {
                '1h': 1,
                '24h': 24,
                '7d': 168,
            }.get(timeframe.lower(), 24)

            alerts = self.db.get_recent_alerts(hours=timeframe_hours, limit=20)

            if not alerts:
                await interaction.followup.send(
                    f"No alerts in the last {timeframe}",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"🔔 Recent Alerts ({timeframe})",
                description=f"Found {len(alerts)} alert(s)",
                color=0xFFD700,
                timestamp=datetime.utcnow()
            )

            # Group by severity
            by_severity = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
            by_type = {}

            for alert in alerts:
                by_severity[alert.severity] = by_severity.get(alert.severity, 0) + 1
                by_type[alert.alert_type] = by_type.get(alert.alert_type, 0) + 1

            # Severity breakdown
            severity_text = "\n".join(
                f"{'🔴' if s=='critical' else '🟠' if s=='high' else '🟡' if s=='medium' else '🟢'} "
                f"{s.title()}: {count}"
                for s, count in by_severity.items() if count > 0
            )

            embed.add_field(
                name="⚠️ By Severity",
                value=severity_text or "None",
                inline=True
            )

            # Type breakdown
            type_text = "\n".join(
                f"• {t.replace('_', ' ').title()}: {count}"
                for t, count in sorted(by_type.items(), key=lambda x: -x[1])
            )

            embed.add_field(
                name="📋 By Type",
                value=type_text or "None",
                inline=True
            )

            # Recent alerts
            recent_text = []
            for alert in alerts[:5]:
                time_ago = datetime.utcnow() - alert.created_at
                mins_ago = int(time_ago.total_seconds() / 60)

                if mins_ago < 60:
                    time_str = f"{mins_ago}m ago"
                else:
                    time_str = f"{mins_ago // 60}h ago"

                recent_text.append(
                    f"#{alert.id} - {alert.alert_type.replace('_', ' ').title()} "
                    f"({alert.severity}) - {time_str}"
                )

            if recent_text:
                embed.add_field(
                    name="🕒 Most Recent",
                    value="\n".join(recent_text),
                    inline=False
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error handling alerts command: {e}", exc_info=True)
            await interaction.followup.send("Error retrieving alerts", ephemeral=True)

    @tasks.loop(seconds=60)  # Check every 60 seconds instead of 10
    async def check_alerts_task(self):
        """Background task to check for unsent alerts with rate limiting."""
        if not self.is_ready or not self.alert_channel:
            return

        try:
            # Clean up old timestamps (older than 1 hour)
            now = datetime.utcnow()
            self.alerts_sent_last_hour = [
                ts for ts in self.alerts_sent_last_hour
                if (now - ts).total_seconds() < 3600
            ]

            # Check if we've hit the hourly limit
            alerts_remaining = self.max_alerts_per_hour - len(self.alerts_sent_last_hour)
            if alerts_remaining <= 0:
                logger.warning(f"Rate limit reached: {self.max_alerts_per_hour} alerts sent in last hour")
                return

            # Get unsent alerts, prioritizing by severity
            # Limit to max_alerts_per_batch and remaining hourly quota
            fetch_limit = min(self.max_alerts_per_batch, alerts_remaining)
            unsent_alerts = self.db.get_unsent_alerts(limit=fetch_limit)

            # Filter and sort by severity (critical, high, medium, low)
            severity_priority = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
            unsent_alerts_sorted = sorted(
                unsent_alerts,
                key=lambda a: severity_priority.get(a.severity, 999)
            )

            # Send alerts with rate limiting
            for i, alert in enumerate(unsent_alerts_sorted):
                # Check hourly limit before each send
                if len(self.alerts_sent_last_hour) >= self.max_alerts_per_hour:
                    logger.warning("Hourly rate limit reached mid-batch, stopping")
                    break

                await self.send_alert(alert)

                # Record timestamp
                self.alerts_sent_last_hour.append(datetime.utcnow())

                # Wait before next alert (except for last one)
                if i < len(unsent_alerts_sorted) - 1:
                    await asyncio.sleep(self.delay_between_alerts)

            # Log rate limit status
            if unsent_alerts:
                logger.info(
                    f"Rate limiter: {len(self.alerts_sent_last_hour)}/{self.max_alerts_per_hour} "
                    f"alerts sent in last hour"
                )

        except Exception as e:
            logger.error(f"Error in check_alerts task: {e}", exc_info=True)

    @check_alerts_task.before_loop
    async def before_check_alerts(self):
        """Wait for bot to be ready before starting task."""
        await self.wait_until_ready()

    async def send_alert(self, alert):
        """
        Send an alert to Discord.

        Args:
            alert: Alert database object
        """
        try:
            if not self.alert_channel:
                logger.error("Alert channel not available")
                return

            # Get market info
            market = self.db.get_market(alert.market_id)
            market_question = market.question if market else "Unknown Market"

            # Format alert
            alert_data = {
                'id': alert.id,
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'details': alert.details
            }

            embed = self.formatter.format_alert(alert_data, market_question)

            # Send to Discord
            message = await self.alert_channel.send(embed=embed)

            # Mark as sent
            self.db.mark_alert_sent(alert.id, discord_message_id=str(message.id))

            self.alerts_sent += 1
            logger.info(
                f"Alert sent to Discord: #{alert.id} ({alert.alert_type})",
                extra={'alert_id': alert.id, 'message_id': message.id}
            )

        except Exception as e:
            logger.error(f"Error sending alert {alert.id}: {e}", exc_info=True)
            self.errors_count += 1

    async def shutdown(self):
        """Gracefully shutdown bot."""
        logger.info("Shutting down Discord bot...")

        # Stop background tasks
        if self.check_alerts_task.is_running():
            self.check_alerts_task.cancel()

        # Send shutdown message
        if self.alert_channel:
            try:
                embed = discord.Embed(
                    title="⏸️ Bot Shutting Down",
                    description="Monitoring bot is going offline.",
                    color=0xFF0000,
                    timestamp=datetime.utcnow()
                )
                await self.alert_channel.send(embed=embed)
            except:
                pass

        # Close connection
        await self.close()

        logger.info("Discord bot shutdown complete")
