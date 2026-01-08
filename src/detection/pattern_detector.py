"""
Pattern detection for unusual betting behavior.

Detects:
1. Rapid successive bets (same address, short timeframe)
2. Statistical anomalies (z-score, IQR methods)
3. Other suspicious patterns
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

from database.repository import DatabaseRepository
from database.models import Bet
from detection.anomaly_algorithms import ZScoreDetector, IQRDetector, calculate_statistics
from detection.statistics_calculator import MarketStatisticsCalculator
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PatternDetection:
    """Result of pattern detection."""
    pattern_type: str  # 'rapid_succession', 'statistical_anomaly', etc.
    severity: str  # 'critical', 'high', 'medium', 'low'
    market_id: str
    address: Optional[str]  # Wallet address if applicable
    bets: List[Bet]  # Bets involved in pattern
    details: Dict[str, Any]
    detected_at: datetime


class PatternDetector:
    """Detect unusual betting patterns."""

    def __init__(
        self,
        db: DatabaseRepository,
        rapid_succession_bet_count: int = 5,
        rapid_succession_time_window_minutes: int = 5,
        z_score_threshold: float = 3.0,
        iqr_multiplier: float = 1.5
    ):
        """
        Initialize pattern detector.

        Args:
            db: Database repository
            rapid_succession_bet_count: Number of bets to trigger rapid succession
            rapid_succession_time_window_minutes: Time window for rapid succession
            z_score_threshold: Z-score threshold for anomaly detection
            iqr_multiplier: IQR multiplier for anomaly detection
        """
        self.db = db
        self.stats_calculator = MarketStatisticsCalculator(db)

        self.rapid_succession_bet_count = rapid_succession_bet_count
        self.rapid_succession_time_window_minutes = rapid_succession_time_window_minutes

        self.z_score_detector = ZScoreDetector(z_score_threshold)
        self.iqr_detector = IQRDetector(iqr_multiplier)

        logger.info(
            "Pattern detector initialized",
            extra={
                'rapid_bet_count': rapid_succession_bet_count,
                'rapid_time_window': rapid_succession_time_window_minutes,
                'z_score_threshold': z_score_threshold,
                'iqr_multiplier': iqr_multiplier
            }
        )

    def detect_rapid_succession(
        self,
        market_id: str,
        address: str,
        lookback_minutes: Optional[int] = None
    ) -> Optional[PatternDetection]:
        """
        Detect rapid successive bets from same address.

        Args:
            market_id: Market ID
            address: Wallet address
            lookback_minutes: Minutes to look back (defaults to config value)

        Returns:
            PatternDetection if pattern found, None otherwise
        """
        if lookback_minutes is None:
            lookback_minutes = self.rapid_succession_time_window_minutes

        # Get recent bets from this address on this market
        since = datetime.utcnow() - timedelta(minutes=lookback_minutes)
        bets = self.db.get_bets_by_address(address, market_id=market_id, since=since)

        if len(bets) < self.rapid_succession_bet_count:
            return None

        # Check if bets are within time window
        bets_sorted = sorted(bets, key=lambda b: b.timestamp)

        # Find clusters of bets within time window
        for i in range(len(bets_sorted) - self.rapid_succession_bet_count + 1):
            cluster = bets_sorted[i:i + self.rapid_succession_bet_count]
            time_span = (cluster[-1].timestamp - cluster[0].timestamp).total_seconds() / 60

            if time_span <= lookback_minutes:
                # Rapid succession detected
                total_volume = sum(bet.size for bet in cluster)
                avg_bet_size = total_volume / len(cluster)

                # Determine severity based on bet count and volume
                severity = self._calculate_rapid_succession_severity(
                    bet_count=len(cluster),
                    total_volume=total_volume,
                    time_span_minutes=time_span
                )

                logger.info(
                    f"Rapid succession detected: {len(cluster)} bets in {time_span:.1f} minutes",
                    extra={
                        'market_id': market_id,
                        'address': address,
                        'bet_count': len(cluster),
                        'time_span_minutes': time_span,
                        'total_volume': total_volume
                    }
                )

                return PatternDetection(
                    pattern_type='rapid_succession',
                    severity=severity,
                    market_id=market_id,
                    address=address,
                    bets=cluster,
                    details={
                        'bet_count': len(cluster),
                        'time_span_minutes': time_span,
                        'total_volume': total_volume,
                        'avg_bet_size': avg_bet_size,
                        'first_bet_time': cluster[0].timestamp.isoformat(),
                        'last_bet_time': cluster[-1].timestamp.isoformat(),
                        'outcomes': [bet.outcome for bet in cluster]
                    },
                    detected_at=datetime.utcnow()
                )

        return None

    def detect_statistical_anomaly(
        self,
        bet: Bet,
        method: str = 'z_score'
    ) -> Optional[PatternDetection]:
        """
        Detect if bet is statistical anomaly.

        Args:
            bet: Bet to analyze
            method: Detection method ('z_score' or 'iqr')

        Returns:
            PatternDetection if anomaly found, None otherwise
        """
        # Get historical bet sizes for this market
        bet_sizes = self.stats_calculator.get_recent_bet_sizes(bet.market_id, hours=24)

        if len(bet_sizes) < 10:
            logger.debug(
                f"Insufficient data for statistical anomaly detection",
                extra={'market_id': bet.market_id, 'data_points': len(bet_sizes)}
            )
            return None

        # Detect anomaly
        if method == 'z_score':
            result = self.z_score_detector.detect(bet.size, bet_sizes)
        elif method == 'iqr':
            result = self.iqr_detector.detect(bet.size, bet_sizes)
        else:
            logger.warning(f"Unknown detection method: {method}")
            return None

        if result.is_anomaly:
            # Determine severity based on score
            severity = self._calculate_anomaly_severity(result.score, method)

            logger.info(
                f"Statistical anomaly detected: ${bet.size:,.2f} ({method})",
                extra={
                    'market_id': bet.market_id,
                    'bet_size': bet.size,
                    'method': method,
                    'score': result.score,
                    'severity': severity
                }
            )

            return PatternDetection(
                pattern_type=f'statistical_anomaly_{method}',
                severity=severity,
                market_id=bet.market_id,
                address=bet.address,
                bets=[bet],
                details={
                    'method': method,
                    'score': result.score,
                    'threshold': result.threshold,
                    'bet_size': bet.size,
                    **result.details
                },
                detected_at=datetime.utcnow()
            )

        return None

    def scan_market_for_patterns(
        self,
        market_id: str,
        hours: int = 1
    ) -> List[PatternDetection]:
        """
        Scan a market for all pattern types.

        Args:
            market_id: Market ID
            hours: Hours to look back

        Returns:
            List of detected patterns
        """
        detections = []
        since = datetime.utcnow() - timedelta(hours=hours)

        try:
            # Get recent bets
            bets = self.db.get_bets_by_market(market_id, since=since)

            if not bets:
                logger.debug(f"No recent bets for market {market_id}")
                return detections

            logger.info(f"Scanning {len(bets)} bets for patterns on market {market_id}")

            # Group bets by address for rapid succession detection
            bets_by_address = defaultdict(list)
            for bet in bets:
                bets_by_address[bet.address].append(bet)

            # Check for rapid succession patterns
            for address, address_bets in bets_by_address.items():
                if len(address_bets) >= self.rapid_succession_bet_count:
                    pattern = self.detect_rapid_succession(market_id, address)
                    if pattern:
                        detections.append(pattern)

            # Check for statistical anomalies
            for bet in bets:
                # Z-score method
                pattern = self.detect_statistical_anomaly(bet, method='z_score')
                if pattern:
                    detections.append(pattern)

                # IQR method (optional, may duplicate)
                # Uncomment if you want both methods
                # pattern = self.detect_statistical_anomaly(bet, method='iqr')
                # if pattern:
                #     detections.append(pattern)

            logger.info(
                f"Found {len(detections)} patterns in market {market_id}",
                extra={'market_id': market_id, 'pattern_count': len(detections)}
            )

        except Exception as e:
            logger.error(f"Error scanning market for patterns: {e}", exc_info=True)

        return detections

    def scan_address_activity(
        self,
        address: str,
        hours: int = 24
    ) -> List[PatternDetection]:
        """
        Scan all activity from an address for patterns.

        Args:
            address: Wallet address
            hours: Hours to look back

        Returns:
            List of detected patterns
        """
        detections = []
        since = datetime.utcnow() - timedelta(hours=hours)

        try:
            # Get all bets from this address
            bets = self.db.get_bets_by_address(address, since=since)

            if not bets:
                return detections

            logger.info(f"Scanning {len(bets)} bets from address {address}")

            # Group bets by market
            bets_by_market = defaultdict(list)
            for bet in bets:
                bets_by_market[bet.market_id].append(bet)

            # Check each market for rapid succession
            for market_id, market_bets in bets_by_market.items():
                if len(market_bets) >= self.rapid_succession_bet_count:
                    pattern = self.detect_rapid_succession(market_id, address)
                    if pattern:
                        detections.append(pattern)

            logger.info(
                f"Found {len(detections)} patterns for address {address}",
                extra={'address': address, 'pattern_count': len(detections)}
            )

        except Exception as e:
            logger.error(f"Error scanning address activity: {e}", exc_info=True)

        return detections

    def _calculate_rapid_succession_severity(
        self,
        bet_count: int,
        total_volume: float,
        time_span_minutes: float
    ) -> str:
        """
        Calculate severity for rapid succession pattern.

        Args:
            bet_count: Number of bets
            total_volume: Total volume
            time_span_minutes: Time span in minutes

        Returns:
            Severity level
        """
        # Higher bet count or volume = higher severity
        if bet_count >= 10 or total_volume >= 100000:
            return 'high'
        elif bet_count >= 7 or total_volume >= 50000:
            return 'medium'
        else:
            return 'medium'  # Default for detected patterns

    def _calculate_anomaly_severity(self, score: float, method: str) -> str:
        """
        Calculate severity for statistical anomaly.

        Args:
            score: Anomaly score
            method: Detection method

        Returns:
            Severity level
        """
        if method == 'z_score':
            if score >= 6.0:
                return 'critical'
            elif score >= 4.5:
                return 'high'
            else:
                return 'medium'
        elif method == 'iqr':
            if score >= 3.0:
                return 'high'
            elif score >= 2.0:
                return 'medium'
            else:
                return 'medium'
        return 'medium'

    def get_pattern_summary(
        self,
        hours: int = 24,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get summary of recent pattern detections.

        Args:
            hours: Hours to look back
            limit: Maximum number of markets to check

        Returns:
            Summary dictionary
        """
        summary = {
            'total_patterns': 0,
            'by_type': defaultdict(int),
            'by_severity': defaultdict(int),
            'markets_scanned': 0,
            'patterns': []
        }

        try:
            markets = self.db.get_active_markets(limit=limit)
            summary['markets_scanned'] = len(markets)

            for market in markets:
                patterns = self.scan_market_for_patterns(market.id, hours=hours)

                for pattern in patterns:
                    summary['total_patterns'] += 1
                    summary['by_type'][pattern.pattern_type] += 1
                    summary['by_severity'][pattern.severity] += 1
                    summary['patterns'].append({
                        'type': pattern.pattern_type,
                        'severity': pattern.severity,
                        'market_id': pattern.market_id,
                        'address': pattern.address,
                        'bet_count': len(pattern.bets),
                        'details': pattern.details
                    })

        except Exception as e:
            logger.error(f"Error generating pattern summary: {e}", exc_info=True)
            summary['error'] = str(e)

        return summary
