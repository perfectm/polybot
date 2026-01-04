"""
Market statistics calculator.

Calculates rolling statistics for markets to enable anomaly detection.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import numpy as np

from ..database.repository import DatabaseRepository
from ..database.models import Bet
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MarketStatisticsCalculator:
    """Calculate and store rolling statistics for markets."""

    def __init__(self, db: DatabaseRepository):
        """
        Initialize statistics calculator.

        Args:
            db: Database repository instance
        """
        self.db = db

    def calculate_market_statistics(
        self,
        market_id: str,
        window_hours: int = 24
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate statistics for a market over a time window.

        Args:
            market_id: Market ID
            window_hours: Time window in hours

        Returns:
            Dictionary with statistics or None if insufficient data
        """
        # Get bets within time window
        since = datetime.utcnow() - timedelta(hours=window_hours)
        bets = self.db.get_bets_by_market(market_id, since=since)

        if not bets or len(bets) < 2:
            logger.debug(
                f"Insufficient data for market statistics",
                extra={'market_id': market_id, 'bet_count': len(bets) if bets else 0}
            )
            return None

        # Extract bet sizes
        bet_sizes = [bet.size for bet in bets]
        addresses = set(bet.address for bet in bets)

        # Calculate statistics
        bet_sizes_arr = np.array(bet_sizes)

        mean = float(np.mean(bet_sizes_arr))
        std_dev = float(np.std(bet_sizes_arr, ddof=1))
        median = float(np.median(bet_sizes_arr))
        q1 = float(np.percentile(bet_sizes_arr, 25))
        q3 = float(np.percentile(bet_sizes_arr, 75))
        iqr = q3 - q1
        total_volume = float(np.sum(bet_sizes_arr))

        stats = {
            'market_id': market_id,
            'window_hours': window_hours,
            'mean_bet_size': mean,
            'std_dev_bet_size': std_dev,
            'median_bet_size': median,
            'q1': q1,
            'q3': q3,
            'iqr': iqr,
            'total_bets': len(bets),
            'total_volume': total_volume,
            'unique_addresses': len(addresses),
            'window_start': since,
            'window_end': datetime.utcnow(),
        }

        logger.debug(
            f"Calculated statistics for market {market_id}",
            extra={
                'market_id': market_id,
                'window_hours': window_hours,
                'bet_count': len(bets),
                'mean': mean,
                'std_dev': std_dev
            }
        )

        return stats

    def update_market_statistics(
        self,
        market_id: str,
        window_hours: int = 24
    ) -> bool:
        """
        Calculate and store market statistics in database.

        Args:
            market_id: Market ID
            window_hours: Time window in hours

        Returns:
            True if statistics were updated, False otherwise
        """
        try:
            stats = self.calculate_market_statistics(market_id, window_hours)

            if stats:
                self.db.upsert_market_statistics(stats)
                logger.info(
                    f"Updated statistics for market {market_id}",
                    extra={'market_id': market_id, 'window_hours': window_hours}
                )
                return True
            else:
                logger.debug(
                    f"No statistics update for market {market_id} - insufficient data",
                    extra={'market_id': market_id}
                )
                return False

        except Exception as e:
            logger.error(
                f"Error updating market statistics: {e}",
                extra={'market_id': market_id, 'window_hours': window_hours},
                exc_info=True
            )
            return False

    def update_all_active_markets(
        self,
        window_hours: int = 24,
        max_markets: Optional[int] = None
    ) -> int:
        """
        Update statistics for all active markets.

        Args:
            window_hours: Time window in hours
            max_markets: Maximum number of markets to process

        Returns:
            Number of markets updated
        """
        try:
            markets = self.db.get_active_markets(limit=max_markets)
            updated_count = 0

            for market in markets:
                if self.update_market_statistics(market.id, window_hours):
                    updated_count += 1

            logger.info(
                f"Updated statistics for {updated_count}/{len(markets)} markets",
                extra={'updated': updated_count, 'total': len(markets)}
            )

            return updated_count

        except Exception as e:
            logger.error(f"Error updating all market statistics: {e}", exc_info=True)
            return 0

    def get_bet_sizes_for_analysis(
        self,
        market_id: str,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[float]:
        """
        Get list of bet sizes for statistical analysis.

        Args:
            market_id: Market ID
            since: Only include bets after this timestamp
            limit: Maximum number of bets to return

        Returns:
            List of bet sizes
        """
        bets = self.db.get_bets_by_market(market_id, since=since, limit=limit)
        return [bet.size for bet in bets]

    def get_recent_bet_sizes(
        self,
        market_id: str,
        hours: int = 24
    ) -> List[float]:
        """
        Get bet sizes for recent time period.

        Args:
            market_id: Market ID
            hours: Number of hours to look back

        Returns:
            List of bet sizes
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        return self.get_bet_sizes_for_analysis(market_id, since=since)

    def calculate_percentile_rank(
        self,
        value: float,
        market_id: str,
        hours: int = 24
    ) -> float:
        """
        Calculate what percentile a bet size represents.

        Args:
            value: Bet size to rank
            market_id: Market ID
            hours: Time window in hours

        Returns:
            Percentile rank (0-100)
        """
        bet_sizes = self.get_recent_bet_sizes(market_id, hours)

        if not bet_sizes:
            return 0.0

        # Calculate percentile
        percentile = (sum(1 for size in bet_sizes if size <= value) / len(bet_sizes)) * 100

        return float(percentile)
