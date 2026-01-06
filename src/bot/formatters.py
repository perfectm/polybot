"""
Discord message formatters for alerts.

Creates rich embeds with color-coding and comprehensive information.
"""

import discord
from datetime import datetime
from typing import Dict, Any, Optional
import json

from utils.logger import get_logger

logger = get_logger(__name__)


class AlertFormatter:
    """Format alerts as Discord embeds."""

    def __init__(self, color_config: Optional[Dict[str, int]] = None):
        """
        Initialize alert formatter.

        Args:
            color_config: Color configuration for severities
        """
        self.colors = color_config or {
            'critical': 0xFF0000,  # Red
            'high': 0xFF6B35,      # Orange
            'medium': 0xFFD700,    # Gold
            'low': 0x4169E1,       # Blue
        }

    def format_large_bet_alert(
        self,
        alert_data: Dict[str, Any],
        market_question: str
    ) -> discord.Embed:
        """
        Format large bet alert as Discord embed.

        Args:
            alert_data: Alert details from database
            market_question: Market question text

        Returns:
            Discord embed
        """
        severity = alert_data.get('severity', 'medium')
        details = alert_data.get('details', {})

        # Parse details if it's a JSON string
        if isinstance(details, str):
            details = json.loads(details)

        bet_size = details.get('bet_size', 0)
        address = details.get('address', 'unknown')

        # Create embed
        embed = discord.Embed(
            title="🚨 Large Bet Detected",
            description=f"**Market**: {market_question[:200]}",
            color=self.colors.get(severity, 0x808080),
            timestamp=datetime.utcnow()
        )

        # Bet details
        embed.add_field(
            name="💰 Bet Size",
            value=f"**${bet_size:,.2f} USD**",
            inline=True
        )

        embed.add_field(
            name="📊 Severity",
            value=f"**{severity.upper()}**",
            inline=True
        )

        # Wallet address (shortened)
        short_address = f"{address[:6]}...{address[-4:]}" if len(address) > 10 else address
        embed.add_field(
            name="👛 Wallet",
            value=f"`{short_address}`",
            inline=True
        )

        # Detection tiers
        large_bet_info = details.get('large_bet', {})
        if large_bet_info:
            triggered_tiers = large_bet_info.get('triggered_tiers', [])
            tier_text = ", ".join(t.replace('_', ' ').title() for t in triggered_tiers)

            context_parts = []

            # Absolute threshold
            if 'absolute_threshold' in triggered_tiers:
                threshold_info = large_bet_info.get('details', {}).get('absolute_threshold', {})
                thresh_severity = threshold_info.get('severity', '')
                context_parts.append(f"• Absolute: {thresh_severity.title()} threshold")

            # Market relative
            if 'market_relative' in triggered_tiers:
                market_rel = large_bet_info.get('details', {}).get('market_relative', {})
                pct = market_rel.get('percentage', 0)
                context_parts.append(f"• Market Volume: {pct:.1f}% of total")

            # Statistical
            if 'statistical_anomaly' in triggered_tiers:
                stats = large_bet_info.get('details', {}).get('statistical_anomaly', {})
                z_score = stats.get('z_score', 0)
                context_parts.append(f"• Statistical: {z_score:.1f}σ above mean")

            if context_parts:
                embed.add_field(
                    name="🎯 Triggered Detection",
                    value="\n".join(context_parts),
                    inline=False
                )

        # Market context
        market_context_parts = []
        if large_bet_info:
            market_rel = large_bet_info.get('details', {}).get('market_relative', {})
            if market_rel:
                market_vol = market_rel.get('market_volume', 0)
                if market_vol > 0:
                    market_context_parts.append(f"• Total Volume: ${market_vol:,.0f}")

            stats = large_bet_info.get('details', {}).get('statistical_anomaly', {})
            if stats and not stats.get('error'):
                mean = stats.get('mean', 0)
                std_dev = stats.get('std_dev', 0)
                market_context_parts.append(f"• 24h Mean: ${mean:,.2f}")
                market_context_parts.append(f"• Std Dev: ${std_dev:,.2f}")

        if market_context_parts:
            embed.add_field(
                name="📈 Market Context",
                value="\n".join(market_context_parts),
                inline=False
            )

        # Footer
        timestamp_str = details.get('timestamp', '')
        embed.set_footer(text=f"Alert ID: #{alert_data.get('id', 0)} • {timestamp_str}")

        return embed

    def format_new_account_alert(
        self,
        alert_data: Dict[str, Any],
        market_question: str
    ) -> discord.Embed:
        """
        Format new account alert as Discord embed.

        Args:
            alert_data: Alert details from database
            market_question: Market question text

        Returns:
            Discord embed
        """
        severity = alert_data.get('severity', 'medium')
        details = alert_data.get('details', {})

        # Parse details if it's a JSON string
        if isinstance(details, str):
            details = json.loads(details)

        bet_size = details.get('bet_size', 0)
        address = details.get('address', 'unknown')

        new_account_info = details.get('new_account', {})
        account_age_hours = new_account_info.get('account_age_hours', 0)
        bet_position = new_account_info.get('bet_position', 1)
        total_bets = new_account_info.get('total_bets_count', 1)

        # Create embed
        embed = discord.Embed(
            title="⚠️ New Account Alert",
            description=f"**Market**: {market_question[:200]}",
            color=self.colors.get(severity, 0x808080),
            timestamp=datetime.utcnow()
        )

        # Account details
        if account_age_hours < 1:
            age_text = "**< 1 hour** (Brand New!)"
        elif account_age_hours < 24:
            age_text = f"**{account_age_hours:.1f} hours**"
        else:
            age_text = f"**{account_age_hours / 24:.1f} days**"

        embed.add_field(
            name="⏱️ Account Age",
            value=age_text,
            inline=True
        )

        embed.add_field(
            name="🔢 Bet Position",
            value=f"**{bet_position} of {total_bets}**",
            inline=True
        )

        embed.add_field(
            name="💰 Bet Size",
            value=f"**${bet_size:,.2f}**",
            inline=True
        )

        # Wallet address
        short_address = f"{address[:6]}...{address[-4:]}" if len(address) > 10 else address
        embed.add_field(
            name="👛 Wallet",
            value=f"`{short_address}`",
            inline=False
        )

        # Alert reason
        alert_reason = new_account_info.get('details', {}).get('alert_reason', '')
        reason_text = {
            'first_bet_very_large': '🔴 Very large first bet (>$50k)',
            'first_bet_large': '🟠 Large first bet (>$10k)',
            'early_large_bet': '🟡 Large bet within first 10 transactions'
        }.get(alert_reason, 'Suspicious early activity')

        embed.add_field(
            name="🎯 Alert Reason",
            value=reason_text,
            inline=False
        )

        # Risk assessment
        risk_emoji = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢'
        }.get(severity, '⚪')

        embed.add_field(
            name="⚠️ Risk Level",
            value=f"{risk_emoji} **{severity.upper()}**",
            inline=True
        )

        # Footer
        embed.set_footer(text=f"Alert ID: #{alert_data.get('id', 0)} • Monitor this wallet closely")

        return embed

    def format_pattern_alert(
        self,
        alert_data: Dict[str, Any],
        market_question: str
    ) -> discord.Embed:
        """
        Format pattern detection alert as Discord embed.

        Args:
            alert_data: Alert details from database
            market_question: Market question text

        Returns:
            Discord embed
        """
        severity = alert_data.get('severity', 'medium')
        details = alert_data.get('details', {})

        # Parse details if it's a JSON string
        if isinstance(details, str):
            details = json.loads(details)

        alert_type = alert_data.get('alert_type', 'pattern')
        address = details.get('address', 'unknown')

        # Create embed
        title_map = {
            'rapid_succession': '⚡ Rapid Succession Pattern Detected',
            'statistical_anomaly': '📊 Statistical Anomaly Detected',
            'pattern': '🔍 Unusual Pattern Detected'
        }

        embed = discord.Embed(
            title=title_map.get(alert_type, '🔍 Pattern Detected'),
            description=f"**Market**: {market_question[:200]}",
            color=self.colors.get(severity, 0x808080),
            timestamp=datetime.utcnow()
        )

        # Pattern-specific details
        patterns = details.get('patterns', [])
        if patterns and len(patterns) > 0:
            pattern = patterns[0]
            pattern_type = pattern.get('type', '')
            pattern_details = pattern.get('details', {})

            if 'rapid_succession' in pattern_type:
                bet_count = pattern_details.get('bet_count', 0)
                time_span = pattern_details.get('time_span_minutes', 0)
                total_volume = pattern_details.get('total_volume', 0)

                embed.add_field(
                    name="📈 Pattern Details",
                    value=f"• **{bet_count} bets** in **{time_span:.1f} minutes**\n"
                          f"• Total Volume: **${total_volume:,.2f}**\n"
                          f"• Avg per bet: **${total_volume/bet_count:,.2f}**",
                    inline=False
                )

            elif 'statistical_anomaly' in pattern_type:
                method = pattern_details.get('method', 'unknown')
                score = pattern_details.get('score', 0)
                bet_size = pattern_details.get('bet_size', 0)

                method_name = {
                    'z_score': 'Z-Score',
                    'iqr': 'IQR'
                }.get(method, method)

                embed.add_field(
                    name="📊 Anomaly Details",
                    value=f"• Method: **{method_name}**\n"
                          f"• Score: **{score:.2f}**\n"
                          f"• Bet Size: **${bet_size:,.2f}**",
                    inline=False
                )

        # Wallet address
        short_address = f"{address[:6]}...{address[-4:]}" if len(address) > 10 else address
        embed.add_field(
            name="👛 Wallet",
            value=f"`{short_address}`",
            inline=True
        )

        embed.add_field(
            name="⚠️ Severity",
            value=f"**{severity.upper()}**",
            inline=True
        )

        # Footer
        embed.set_footer(text=f"Alert ID: #{alert_data.get('id', 0)}")

        return embed

    def format_composite_alert(
        self,
        alert_data: Dict[str, Any],
        market_question: str
    ) -> discord.Embed:
        """
        Format composite alert (multiple detection types) as Discord embed.

        Args:
            alert_data: Alert details from database
            market_question: Market question text

        Returns:
            Discord embed
        """
        severity = alert_data.get('severity', 'medium')
        details = alert_data.get('details', {})

        # Parse details if it's a JSON string
        if isinstance(details, str):
            details = json.loads(details)

        detections = details.get('detections', [])
        bet_size = details.get('bet_size', 0)
        address = details.get('address', 'unknown')

        # Create embed
        embed = discord.Embed(
            title="🚨 Multiple Suspicious Signals Detected",
            description=f"**Market**: {market_question[:200]}",
            color=self.colors.get(severity, 0x808080),
            timestamp=datetime.utcnow()
        )

        # Detection types
        detection_icons = {
            'large_bet': '💰',
            'new_account': '⚠️',
            'rapid_succession': '⚡',
            'statistical_anomaly': '📊'
        }

        detection_text = "\n".join(
            f"{detection_icons.get(d, '•')} {d.replace('_', ' ').title()}"
            for d in detections
        )

        embed.add_field(
            name="🎯 Detected Patterns",
            value=detection_text,
            inline=False
        )

        # Key metrics
        embed.add_field(
            name="💰 Bet Size",
            value=f"**${bet_size:,.2f}**",
            inline=True
        )

        embed.add_field(
            name="⚠️ Severity",
            value=f"**{severity.upper()}**",
            inline=True
        )

        # Wallet
        short_address = f"{address[:6]}...{address[-4:]}" if len(address) > 10 else address
        embed.add_field(
            name="👛 Wallet",
            value=f"`{short_address}`",
            inline=True
        )

        # Additional context from each detection type
        context_parts = []

        if 'large_bet' in detections and details.get('large_bet'):
            lb = details['large_bet']
            tiers = lb.get('triggered_tiers', [])
            context_parts.append(f"**Large Bet**: {', '.join(t.replace('_', ' ').title() for t in tiers)}")

        if 'new_account' in detections and details.get('new_account'):
            na = details['new_account']
            age = na.get('account_age_hours', 0)
            pos = na.get('bet_position', 1)
            context_parts.append(f"**New Account**: {age:.1f}h old, bet #{pos}")

        if 'rapid_succession' in detections and details.get('patterns'):
            for p in details['patterns']:
                if 'rapid' in p.get('type', ''):
                    pd = p.get('details', {})
                    count = pd.get('bet_count', 0)
                    mins = pd.get('time_span_minutes', 0)
                    context_parts.append(f"**Rapid Succession**: {count} bets in {mins:.1f}min")

        if context_parts:
            embed.add_field(
                name="📋 Details",
                value="\n".join(context_parts),
                inline=False
            )

        # Footer
        embed.set_footer(text=f"Alert ID: #{alert_data.get('id', 0)} • High priority - multiple signals")

        return embed

    def format_alert(
        self,
        alert_data: Dict[str, Any],
        market_question: str
    ) -> discord.Embed:
        """
        Format alert based on type.

        Args:
            alert_data: Alert details from database
            market_question: Market question text

        Returns:
            Discord embed
        """
        alert_type = alert_data.get('alert_type', 'composite')

        try:
            if alert_type == 'large_bet':
                return self.format_large_bet_alert(alert_data, market_question)
            elif alert_type == 'new_account':
                return self.format_new_account_alert(alert_data, market_question)
            elif alert_type in ['rapid_succession', 'statistical_anomaly']:
                return self.format_pattern_alert(alert_data, market_question)
            else:
                return self.format_composite_alert(alert_data, market_question)

        except Exception as e:
            logger.error(f"Error formatting alert: {e}", exc_info=True)
            # Return basic fallback embed
            return self._create_fallback_embed(alert_data, market_question)

    def _create_fallback_embed(
        self,
        alert_data: Dict[str, Any],
        market_question: str
    ) -> discord.Embed:
        """Create basic fallback embed if formatting fails."""
        embed = discord.Embed(
            title="🔔 Alert",
            description=f"**Market**: {market_question[:200]}",
            color=0x808080,
            timestamp=datetime.utcnow()
        )

        embed.add_field(
            name="Type",
            value=alert_data.get('alert_type', 'unknown'),
            inline=True
        )

        embed.add_field(
            name="Severity",
            value=alert_data.get('severity', 'unknown').upper(),
            inline=True
        )

        embed.set_footer(text=f"Alert ID: #{alert_data.get('id', 0)}")

        return embed
