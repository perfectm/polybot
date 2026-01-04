"""
Detection orchestrator - unified interface for all detection systems.

Coordinates large bet detection, pattern detection, and new account detection.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import json

from ..database.repository import DatabaseRepository
from ..database.models import Bet
from .large_bet_detector import LargeBetDetector, LargeBetDetection
from .pattern_detector import PatternDetector, PatternDetection
from .new_account_detector import NewAccountDetector, NewAccountDetection
from .statistics_calculator import MarketStatisticsCalculator
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class UnifiedDetection:
    """Unified detection result combining all detection types."""
    bet_id: int
    market_id: str
    address: str
    bet_size: float
    timestamp: datetime
    detections: List[str]  # Types of detections triggered
    max_severity: str  # Highest severity across all detections
    large_bet: Optional[Dict[str, Any]] = None
    patterns: Optional[List[Dict[str, Any]]] = None
    new_account: Optional[Dict[str, Any]] = None


class DetectionOrchestrator:
    """Orchestrate all detection systems."""

    def __init__(
        self,
        db: DatabaseRepository,
        large_bet_thresholds: Optional[Dict[str, float]] = None,
        volume_percentage_threshold: float = 5.0,
        statistical_sigma_threshold: float = 3.0,
        rapid_succession_bet_count: int = 5,
        rapid_succession_time_window_minutes: int = 5,
        z_score_threshold: float = 3.0,
        iqr_multiplier: float = 1.5,
        new_account_threshold_hours: int = 72,
        new_account_first_n_bets: int = 10,
        new_account_large_bet_threshold: float = 10000.0,
        new_account_suspicious_first_bet_threshold: float = 50000.0
    ):
        """
        Initialize detection orchestrator.

        Args:
            db: Database repository
            large_bet_thresholds: Thresholds for large bet detection
            volume_percentage_threshold: Market volume percentage threshold
            statistical_sigma_threshold: Statistical sigma threshold
            rapid_succession_bet_count: Rapid succession bet count
            rapid_succession_time_window_minutes: Rapid succession time window
            z_score_threshold: Z-score threshold
            iqr_multiplier: IQR multiplier
            new_account_threshold_hours: New account threshold hours
            new_account_first_n_bets: First N bets to monitor for new accounts
            new_account_large_bet_threshold: Large bet threshold for new accounts
            new_account_suspicious_first_bet_threshold: Suspicious first bet threshold
        """
        self.db = db
        self.stats_calculator = MarketStatisticsCalculator(db)

        # Initialize all detectors
        self.large_bet_detector = LargeBetDetector(
            db=db,
            thresholds=large_bet_thresholds,
            volume_percentage_threshold=volume_percentage_threshold,
            statistical_sigma_threshold=statistical_sigma_threshold
        )

        self.pattern_detector = PatternDetector(
            db=db,
            rapid_succession_bet_count=rapid_succession_bet_count,
            rapid_succession_time_window_minutes=rapid_succession_time_window_minutes,
            z_score_threshold=z_score_threshold,
            iqr_multiplier=iqr_multiplier
        )

        self.new_account_detector = NewAccountDetector(
            db=db,
            new_account_threshold_hours=new_account_threshold_hours,
            first_n_bets=new_account_first_n_bets,
            large_bet_threshold=new_account_large_bet_threshold,
            suspicious_first_bet_threshold=new_account_suspicious_first_bet_threshold
        )

        logger.info("Detection orchestrator initialized with all detectors")

    def analyze_bet(self, bet: Bet) -> Optional[UnifiedDetection]:
        """
        Run all detection systems on a bet.

        Args:
            bet: Bet to analyze

        Returns:
            UnifiedDetection if any detector triggered, None otherwise
        """
        detections = []
        severities = []
        results = {}

        # Large bet detection
        large_bet_result = self.large_bet_detector.detect(bet)
        if large_bet_result:
            detections.append('large_bet')
            severities.append(large_bet_result.severity)
            results['large_bet'] = {
                'severity': large_bet_result.severity,
                'triggered_tiers': large_bet_result.triggered_tiers,
                'details': large_bet_result.details
            }

        # Pattern detection (rapid succession and statistical anomalies)
        rapid_pattern = self.pattern_detector.detect_rapid_succession(
            market_id=bet.market_id,
            address=bet.address
        )
        if rapid_pattern:
            detections.append('rapid_succession')
            severities.append(rapid_pattern.severity)

        statistical_pattern = self.pattern_detector.detect_statistical_anomaly(
            bet=bet,
            method='z_score'
        )
        if statistical_pattern:
            detections.append('statistical_anomaly')
            severities.append(statistical_pattern.severity)

        # Combine patterns
        patterns_list = []
        if rapid_pattern:
            patterns_list.append({
                'type': rapid_pattern.pattern_type,
                'severity': rapid_pattern.severity,
                'details': rapid_pattern.details
            })
        if statistical_pattern:
            patterns_list.append({
                'type': statistical_pattern.pattern_type,
                'severity': statistical_pattern.severity,
                'details': statistical_pattern.details
            })

        if patterns_list:
            results['patterns'] = patterns_list

        # New account detection
        new_account_result = self.new_account_detector.detect(bet)
        if new_account_result:
            detections.append('new_account')
            severities.append(new_account_result.severity)
            results['new_account'] = {
                'severity': new_account_result.severity,
                'account_age_hours': new_account_result.account_age_hours,
                'total_bets_count': new_account_result.total_bets_count,
                'bet_position': new_account_result.bet_position,
                'details': new_account_result.details
            }

        # If any detection triggered, create unified result
        if detections:
            max_severity = self._get_max_severity(severities)

            logger.info(
                f"Unified detection triggered: {', '.join(detections)}",
                extra={
                    'bet_id': bet.id,
                    'market_id': bet.market_id,
                    'address': bet.address,
                    'bet_size': bet.size,
                    'detections': detections,
                    'max_severity': max_severity
                }
            )

            return UnifiedDetection(
                bet_id=bet.id,
                market_id=bet.market_id,
                address=bet.address,
                bet_size=bet.size,
                timestamp=bet.timestamp,
                detections=detections,
                max_severity=max_severity,
                **results
            )

        return None

    def _get_max_severity(self, severities: List[str]) -> str:
        """
        Get maximum severity from list.

        Args:
            severities: List of severity levels

        Returns:
            Highest severity
        """
        severity_order = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
        max_level = max(severity_order.get(s, 0) for s in severities)

        for severity, level in severity_order.items():
            if level == max_level:
                return severity

        return 'low'

    def create_alert_from_detection(
        self,
        detection: UnifiedDetection
    ) -> Optional[int]:
        """
        Create database alert from unified detection.

        Args:
            detection: Unified detection result

        Returns:
            Alert ID if created, None otherwise
        """
        try:
            # Prepare alert details
            alert_details = {
                'bet_id': detection.bet_id,
                'bet_size': detection.bet_size,
                'address': detection.address,
                'timestamp': detection.timestamp.isoformat(),
                'detections': detection.detections,
                'large_bet': detection.large_bet,
                'patterns': detection.patterns,
                'new_account': detection.new_account,
            }

            # Determine primary alert type
            if 'large_bet' in detection.detections:
                alert_type = 'large_bet'
            elif 'new_account' in detection.detections:
                alert_type = 'new_account'
            elif 'rapid_succession' in detection.detections:
                alert_type = 'rapid_succession'
            elif 'statistical_anomaly' in detection.detections:
                alert_type = 'statistical_anomaly'
            else:
                alert_type = 'composite'

            # Create alert in database
            alert = self.db.create_alert({
                'alert_type': alert_type,
                'severity': detection.max_severity,
                'market_id': detection.market_id,
                'bet_id': detection.bet_id,
                'details': json.dumps(alert_details),
                'sent_to_discord': False,
            })

            logger.info(
                f"Alert created: {alert_type} (severity: {detection.max_severity})",
                extra={
                    'alert_id': alert.id,
                    'alert_type': alert_type,
                    'severity': detection.max_severity,
                    'market_id': detection.market_id
                }
            )

            return alert.id

        except Exception as e:
            logger.error(f"Error creating alert from detection: {e}", exc_info=True)
            return None

    def process_bet(self, bet: Bet) -> Optional[int]:
        """
        Process a bet through all detection systems and create alert if needed.

        Args:
            bet: Bet to process

        Returns:
            Alert ID if alert created, None otherwise
        """
        # Run detection
        detection = self.analyze_bet(bet)

        # Create alert if detection triggered
        if detection:
            return self.create_alert_from_detection(detection)

        return None

    def process_recent_bets(
        self,
        hours: int = 1,
        max_markets: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process recent bets across all markets.

        Args:
            hours: Hours to look back
            max_markets: Maximum number of markets to process

        Returns:
            Summary of processing results
        """
        from datetime import timedelta

        since = datetime.utcnow() - timedelta(hours=hours)
        summary = {
            'processed_bets': 0,
            'detections': 0,
            'alerts_created': 0,
            'by_type': {},
            'by_severity': {},
        }

        try:
            markets = self.db.get_active_markets(limit=max_markets)

            for market in markets:
                bets = self.db.get_bets_by_market(market.id, since=since)

                for bet in bets:
                    summary['processed_bets'] += 1

                    detection = self.analyze_bet(bet)
                    if detection:
                        summary['detections'] += 1

                        # Count by type
                        for det_type in detection.detections:
                            summary['by_type'][det_type] = summary['by_type'].get(det_type, 0) + 1

                        # Count by severity
                        summary['by_severity'][detection.max_severity] = \
                            summary['by_severity'].get(detection.max_severity, 0) + 1

                        # Create alert
                        alert_id = self.create_alert_from_detection(detection)
                        if alert_id:
                            summary['alerts_created'] += 1

            logger.info(
                f"Processed {summary['processed_bets']} bets, "
                f"found {summary['detections']} detections, "
                f"created {summary['alerts_created']} alerts"
            )

        except Exception as e:
            logger.error(f"Error processing recent bets: {e}", exc_info=True)
            summary['error'] = str(e)

        return summary

    def update_market_statistics(
        self,
        max_markets: Optional[int] = None
    ) -> int:
        """
        Update statistics for all active markets.

        Args:
            max_markets: Maximum number of markets to update

        Returns:
            Number of markets updated
        """
        return self.stats_calculator.update_all_active_markets(
            window_hours=24,
            max_markets=max_markets
        )
