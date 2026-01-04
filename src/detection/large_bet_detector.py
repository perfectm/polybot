"""
Large bet detection system.

Implements 3-tier detection:
1. Absolute threshold (e.g., >$100k = critical)
2. Market-relative (e.g., >5% of market volume)
3. Statistical (e.g., >3 sigma from mean)
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from ..database.repository import DatabaseRepository
from ..database.models import Bet
from .anomaly_algorithms import is_outlier_by_zscore
from .statistics_calculator import MarketStatisticsCalculator
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LargeBetDetection:
    """Result of large bet detection."""
    is_large_bet: bool
    severity: str  # 'critical', 'high', 'medium', 'low'
    triggered_tiers: List[str]  # Which detection tiers triggered
    bet: Bet
    market_id: str
    details: Dict[str, Any]


class LargeBetDetector:
    """Detect unusually large bets using multi-tier system."""

    def __init__(
        self,
        db: DatabaseRepository,
        thresholds: Optional[Dict[str, float]] = None,
        volume_percentage_threshold: float = 5.0,
        statistical_sigma_threshold: float = 3.0
    ):
        """
        Initialize large bet detector.

        Args:
            db: Database repository
            thresholds: Absolute bet size thresholds (critical, high, medium)
            volume_percentage_threshold: Market volume percentage threshold
            statistical_sigma_threshold: Z-score threshold for statistical detection
        """
        self.db = db
        self.stats_calculator = MarketStatisticsCalculator(db)

        # Default thresholds
        self.thresholds = thresholds or {
            'critical': 100000,  # $100k+
            'high': 50000,       # $50k+
            'medium': 10000,     # $10k+
        }

        self.volume_percentage_threshold = volume_percentage_threshold
        self.statistical_sigma_threshold = statistical_sigma_threshold

        logger.info(
            "Large bet detector initialized",
            extra={
                'thresholds': self.thresholds,
                'volume_pct': volume_percentage_threshold,
                'sigma': statistical_sigma_threshold
            }
        )

    def detect(self, bet: Bet) -> Optional[LargeBetDetection]:
        """
        Detect if a bet is unusually large.

        Args:
            bet: Bet to analyze

        Returns:
            LargeBetDetection if bet is large, None otherwise
        """
        triggered_tiers = []
        severity = 'low'
        details = {
            'bet_size': bet.size,
            'market_id': bet.market_id,
            'timestamp': bet.timestamp.isoformat() if bet.timestamp else None,
        }

        # Tier 1: Absolute threshold detection
        absolute_severity = self._check_absolute_threshold(bet.size)
        if absolute_severity:
            triggered_tiers.append('absolute_threshold')
            severity = absolute_severity
            details['absolute_threshold'] = {
                'severity': absolute_severity,
                'threshold': self.thresholds[absolute_severity]
            }

        # Tier 2: Market-relative detection
        market_relative_result = self._check_market_relative(bet)
        if market_relative_result['triggered']:
            triggered_tiers.append('market_relative')
            if self._compare_severity(market_relative_result['severity'], severity) > 0:
                severity = market_relative_result['severity']
            details['market_relative'] = market_relative_result

        # Tier 3: Statistical detection
        statistical_result = self._check_statistical_anomaly(bet)
        if statistical_result['triggered']:
            triggered_tiers.append('statistical_anomaly')
            if self._compare_severity(statistical_result['severity'], severity) > 0:
                severity = statistical_result['severity']
            details['statistical_anomaly'] = statistical_result

        # If any tier triggered, it's a large bet
        if triggered_tiers:
            logger.info(
                f"Large bet detected: ${bet.size:,.2f} on market {bet.market_id}",
                extra={
                    'bet_size': bet.size,
                    'market_id': bet.market_id,
                    'severity': severity,
                    'tiers': triggered_tiers
                }
            )

            return LargeBetDetection(
                is_large_bet=True,
                severity=severity,
                triggered_tiers=triggered_tiers,
                bet=bet,
                market_id=bet.market_id,
                details=details
            )

        return None

    def _check_absolute_threshold(self, bet_size: float) -> Optional[str]:
        """
        Check if bet exceeds absolute thresholds.

        Args:
            bet_size: Size of bet in USD

        Returns:
            Severity level if threshold exceeded, None otherwise
        """
        if bet_size >= self.thresholds['critical']:
            return 'critical'
        elif bet_size >= self.thresholds['high']:
            return 'high'
        elif bet_size >= self.thresholds['medium']:
            return 'medium'
        return None

    def _check_market_relative(self, bet: Bet) -> Dict[str, Any]:
        """
        Check if bet is large relative to market volume.

        Args:
            bet: Bet to analyze

        Returns:
            Dictionary with detection results
        """
        result = {
            'triggered': False,
            'severity': 'low',
            'percentage': 0.0,
            'market_volume': 0.0,
            'threshold': self.volume_percentage_threshold
        }

        try:
            # Get market from database
            market = self.db.get_market(bet.market_id)

            if not market or market.total_volume == 0:
                result['error'] = 'market_not_found_or_zero_volume'
                return result

            # Calculate percentage of market volume
            percentage = (bet.size / market.total_volume) * 100

            result['percentage'] = percentage
            result['market_volume'] = market.total_volume

            # Check if exceeds threshold
            if percentage >= self.volume_percentage_threshold:
                result['triggered'] = True

                # Determine severity based on how much it exceeds
                if percentage >= self.volume_percentage_threshold * 3:  # 15%+
                    result['severity'] = 'critical'
                elif percentage >= self.volume_percentage_threshold * 2:  # 10%+
                    result['severity'] = 'high'
                else:
                    result['severity'] = 'medium'

        except Exception as e:
            logger.error(f"Error in market-relative detection: {e}", exc_info=True)
            result['error'] = str(e)

        return result

    def _check_statistical_anomaly(self, bet: Bet) -> Dict[str, Any]:
        """
        Check if bet is statistical anomaly compared to market history.

        Args:
            bet: Bet to analyze

        Returns:
            Dictionary with detection results
        """
        result = {
            'triggered': False,
            'severity': 'low',
            'z_score': 0.0,
            'threshold': self.statistical_sigma_threshold
        }

        try:
            # Get market statistics
            stats = self.db.get_market_statistics(bet.market_id, window_hours=24)

            if not stats or stats.total_bets < 10:
                result['error'] = 'insufficient_statistics'
                return result

            # Check if bet is outlier by z-score
            is_outlier, z_score = is_outlier_by_zscore(
                value=bet.size,
                mean=stats.mean_bet_size,
                std_dev=stats.std_dev_bet_size,
                threshold=self.statistical_sigma_threshold
            )

            result['z_score'] = z_score
            result['mean'] = stats.mean_bet_size
            result['std_dev'] = stats.std_dev_bet_size

            if is_outlier:
                result['triggered'] = True

                # Determine severity based on how many sigmas
                if z_score >= self.statistical_sigma_threshold * 2:  # 6+ sigma
                    result['severity'] = 'critical'
                elif z_score >= self.statistical_sigma_threshold * 1.5:  # 4.5+ sigma
                    result['severity'] = 'high'
                else:
                    result['severity'] = 'medium'

        except Exception as e:
            logger.error(f"Error in statistical anomaly detection: {e}", exc_info=True)
            result['error'] = str(e)

        return result

    def _compare_severity(self, severity1: str, severity2: str) -> int:
        """
        Compare two severity levels.

        Args:
            severity1: First severity
            severity2: Second severity

        Returns:
            1 if severity1 > severity2, -1 if severity1 < severity2, 0 if equal
        """
        severity_order = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
        s1 = severity_order.get(severity1, 0)
        s2 = severity_order.get(severity2, 0)

        if s1 > s2:
            return 1
        elif s1 < s2:
            return -1
        return 0

    def analyze_bet(self, bet: Bet) -> Dict[str, Any]:
        """
        Perform complete analysis of a bet.

        Args:
            bet: Bet to analyze

        Returns:
            Dictionary with full analysis results
        """
        detection = self.detect(bet)

        analysis = {
            'bet_id': bet.id,
            'bet_size': bet.size,
            'market_id': bet.market_id,
            'address': bet.address,
            'timestamp': bet.timestamp.isoformat() if bet.timestamp else None,
            'is_large_bet': detection is not None,
        }

        if detection:
            analysis.update({
                'severity': detection.severity,
                'triggered_tiers': detection.triggered_tiers,
                'details': detection.details
            })

        return analysis

    def scan_recent_bets(
        self,
        market_id: Optional[str] = None,
        hours: int = 1,
        limit: Optional[int] = None
    ) -> List[LargeBetDetection]:
        """
        Scan recent bets for large bet activity.

        Args:
            market_id: Optional market ID to filter by
            hours: Number of hours to look back
            limit: Maximum number of bets to check

        Returns:
            List of large bet detections
        """
        from datetime import timedelta

        since = datetime.utcnow() - timedelta(hours=hours)
        detections = []

        try:
            if market_id:
                bets = self.db.get_bets_by_market(market_id, since=since, limit=limit)
            else:
                # Get recent bets across all markets
                # This is a simplified approach - in production you'd want pagination
                markets = self.db.get_active_markets(limit=50)
                bets = []
                for market in markets:
                    market_bets = self.db.get_bets_by_market(market.id, since=since, limit=20)
                    bets.extend(market_bets)

            logger.info(f"Scanning {len(bets)} recent bets for large bet activity")

            for bet in bets:
                detection = self.detect(bet)
                if detection:
                    detections.append(detection)

            logger.info(f"Found {len(detections)} large bets out of {len(bets)} scanned")

        except Exception as e:
            logger.error(f"Error scanning recent bets: {e}", exc_info=True)

        return detections
