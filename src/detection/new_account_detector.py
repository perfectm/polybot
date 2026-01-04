"""
New account detection for early large bet activity.

Detects suspicious patterns where newly seen wallet addresses place
large bets within their first few transactions.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..database.repository import DatabaseRepository
from ..database.models import Bet
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class NewAccountDetection:
    """Result of new account detection."""
    is_new_account_alert: bool
    severity: str  # 'critical', 'high', 'medium', 'low'
    address: str
    bet: Bet
    account_age_hours: float
    total_bets_count: int
    bet_position: int  # Position of this bet in account history (1-based)
    total_volume: float
    avg_bet_size: float
    details: Dict[str, Any]


class NewAccountDetector:
    """Detect new accounts placing large bets early in their activity."""

    def __init__(
        self,
        db: DatabaseRepository,
        new_account_threshold_hours: int = 72,  # 3 days
        first_n_bets: int = 10,
        large_bet_threshold: float = 10000.0,
        suspicious_first_bet_threshold: float = 50000.0
    ):
        """
        Initialize new account detector.

        Args:
            db: Database repository
            new_account_threshold_hours: Hours to consider account "new"
            first_n_bets: Number of first bets to monitor
            large_bet_threshold: What constitutes a "large" bet
            suspicious_first_bet_threshold: Higher threshold for very first bet
        """
        self.db = db
        self.new_account_threshold_hours = new_account_threshold_hours
        self.first_n_bets = first_n_bets
        self.large_bet_threshold = large_bet_threshold
        self.suspicious_first_bet_threshold = suspicious_first_bet_threshold

        logger.info(
            "New account detector initialized",
            extra={
                'new_account_hours': new_account_threshold_hours,
                'first_n_bets': first_n_bets,
                'large_bet_threshold': large_bet_threshold,
                'suspicious_first_bet_threshold': suspicious_first_bet_threshold
            }
        )

    def get_account_info(self, address: str) -> Dict[str, Any]:
        """
        Get comprehensive account information.

        Args:
            address: Wallet address

        Returns:
            Dictionary with account information
        """
        # Get all bets from this address (ordered by timestamp)
        all_bets = self.db.get_bets_by_address(address, limit=None)

        if not all_bets:
            return {
                'exists': False,
                'first_seen': None,
                'total_bets': 0,
                'total_volume': 0.0,
                'avg_bet_size': 0.0,
                'account_age_hours': 0.0,
                'markets_traded': 0,
            }

        # Sort by timestamp to get chronological order
        all_bets.sort(key=lambda b: b.timestamp)

        # Calculate account statistics
        first_bet_time = all_bets[0].timestamp
        account_age = datetime.utcnow() - first_bet_time
        account_age_hours = account_age.total_seconds() / 3600

        total_volume = sum(bet.size for bet in all_bets)
        unique_markets = set(bet.market_id for bet in all_bets)

        return {
            'exists': True,
            'first_seen': first_bet_time,
            'total_bets': len(all_bets),
            'total_volume': total_volume,
            'avg_bet_size': total_volume / len(all_bets),
            'account_age_hours': account_age_hours,
            'markets_traded': len(unique_markets),
            'all_bets': all_bets,
        }

    def is_new_account(self, address: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if account is considered "new".

        Args:
            address: Wallet address

        Returns:
            Tuple of (is_new, account_info)
        """
        account_info = self.get_account_info(address)

        if not account_info['exists']:
            # Never seen before - brand new
            return (True, account_info)

        # Check if account age is within threshold
        is_new = account_info['account_age_hours'] <= self.new_account_threshold_hours

        return (is_new, account_info)

    def detect(self, bet: Bet) -> Optional[NewAccountDetection]:
        """
        Detect if a bet represents suspicious new account activity.

        Args:
            bet: Bet to analyze

        Returns:
            NewAccountDetection if pattern found, None otherwise
        """
        # Get account information
        is_new, account_info = self.is_new_account(bet.address)

        # If account is old or doesn't exist yet, no detection
        if not is_new and account_info['exists']:
            return None

        # For brand new accounts (first bet we've seen)
        if not account_info['exists']:
            # Check if first bet is suspiciously large
            if bet.size >= self.suspicious_first_bet_threshold:
                logger.warning(
                    f"New account placing very large first bet: {bet.address}",
                    extra={
                        'address': bet.address,
                        'bet_size': bet.size,
                        'market_id': bet.market_id
                    }
                )

                return NewAccountDetection(
                    is_new_account_alert=True,
                    severity='critical',
                    address=bet.address,
                    bet=bet,
                    account_age_hours=0.0,
                    total_bets_count=1,
                    bet_position=1,
                    total_volume=bet.size,
                    avg_bet_size=bet.size,
                    details={
                        'alert_reason': 'first_bet_very_large',
                        'bet_size': bet.size,
                        'threshold': self.suspicious_first_bet_threshold,
                        'first_seen': bet.timestamp.isoformat() if bet.timestamp else None,
                    }
                )
            elif bet.size >= self.large_bet_threshold:
                logger.info(
                    f"New account placing large first bet: {bet.address}",
                    extra={
                        'address': bet.address,
                        'bet_size': bet.size,
                        'market_id': bet.market_id
                    }
                )

                return NewAccountDetection(
                    is_new_account_alert=True,
                    severity='high',
                    address=bet.address,
                    bet=bet,
                    account_age_hours=0.0,
                    total_bets_count=1,
                    bet_position=1,
                    total_volume=bet.size,
                    avg_bet_size=bet.size,
                    details={
                        'alert_reason': 'first_bet_large',
                        'bet_size': bet.size,
                        'threshold': self.large_bet_threshold,
                        'first_seen': bet.timestamp.isoformat() if bet.timestamp else None,
                    }
                )

        # For new accounts (within threshold hours)
        else:
            all_bets = account_info['all_bets']

            # Find position of current bet in chronological order
            bet_position = None
            for i, historical_bet in enumerate(all_bets, start=1):
                if historical_bet.order_id == bet.order_id:
                    bet_position = i
                    break

            # If we can't find the bet position, it's a new bet
            if bet_position is None:
                bet_position = len(all_bets) + 1

            # Check if bet is within first N bets
            if bet_position <= self.first_n_bets:
                # Check if bet size is large
                if bet.size >= self.large_bet_threshold:
                    # Calculate severity based on position and size
                    severity = self._calculate_severity(
                        bet_position=bet_position,
                        bet_size=bet.size,
                        account_age_hours=account_info['account_age_hours']
                    )

                    logger.info(
                        f"New account large bet detected: position {bet_position}/{account_info['total_bets']}",
                        extra={
                            'address': bet.address,
                            'bet_size': bet.size,
                            'bet_position': bet_position,
                            'account_age_hours': account_info['account_age_hours'],
                            'severity': severity
                        }
                    )

                    return NewAccountDetection(
                        is_new_account_alert=True,
                        severity=severity,
                        address=bet.address,
                        bet=bet,
                        account_age_hours=account_info['account_age_hours'],
                        total_bets_count=account_info['total_bets'],
                        bet_position=bet_position,
                        total_volume=account_info['total_volume'],
                        avg_bet_size=account_info['avg_bet_size'],
                        details={
                            'alert_reason': 'early_large_bet',
                            'bet_size': bet.size,
                            'bet_position': bet_position,
                            'first_n_threshold': self.first_n_bets,
                            'account_age_hours': account_info['account_age_hours'],
                            'age_threshold_hours': self.new_account_threshold_hours,
                            'first_seen': account_info['first_seen'].isoformat(),
                            'markets_traded': account_info['markets_traded'],
                        }
                    )

        return None

    def _calculate_severity(
        self,
        bet_position: int,
        bet_size: float,
        account_age_hours: float
    ) -> str:
        """
        Calculate severity based on bet position, size, and account age.

        Args:
            bet_position: Position of bet in account history (1-based)
            bet_size: Size of bet
            account_age_hours: Age of account in hours

        Returns:
            Severity level
        """
        # First bet gets higher severity
        if bet_position == 1:
            if bet_size >= self.suspicious_first_bet_threshold:
                return 'critical'
            elif bet_size >= self.large_bet_threshold * 2:
                return 'high'
            else:
                return 'high'  # Any large first bet is at least high

        # Very new accounts (< 24 hours)
        if account_age_hours < 24:
            if bet_size >= self.suspicious_first_bet_threshold:
                return 'critical'
            elif bet_size >= self.large_bet_threshold * 2:
                return 'high'
            else:
                return 'medium'

        # Newer accounts (24-72 hours)
        if bet_position <= 5:
            if bet_size >= self.suspicious_first_bet_threshold:
                return 'high'
            else:
                return 'medium'

        # Within first 10 bets but older account
        return 'medium'

    def scan_recent_bets_for_new_accounts(
        self,
        hours: int = 24,
        limit: Optional[int] = None
    ) -> List[NewAccountDetection]:
        """
        Scan recent bets across all markets for new account activity.

        Args:
            hours: Hours to look back
            limit: Maximum number of markets to check

        Returns:
            List of new account detections
        """
        detections = []
        since = datetime.utcnow() - timedelta(hours=hours)

        try:
            # Get active markets
            markets = self.db.get_active_markets(limit=limit)

            logger.info(f"Scanning {len(markets)} markets for new account activity")

            for market in markets:
                # Get recent bets for this market
                bets = self.db.get_bets_by_market(market.id, since=since)

                for bet in bets:
                    detection = self.detect(bet)
                    if detection:
                        detections.append(detection)

            logger.info(
                f"Found {len(detections)} new account alerts in last {hours} hours",
                extra={'detection_count': len(detections), 'hours': hours}
            )

        except Exception as e:
            logger.error(f"Error scanning for new accounts: {e}", exc_info=True)

        return detections

    def get_account_risk_profile(self, address: str) -> Dict[str, Any]:
        """
        Generate risk profile for an account.

        Args:
            address: Wallet address

        Returns:
            Risk profile dictionary
        """
        is_new, account_info = self.is_new_account(address)

        if not account_info['exists']:
            return {
                'address': address,
                'risk_level': 'unknown',
                'reason': 'no_history',
                'recommendations': ['Monitor first bet closely']
            }

        risk_factors = []
        risk_score = 0

        # Factor 1: Account age
        if account_info['account_age_hours'] < 24:
            risk_factors.append('very_new_account')
            risk_score += 3
        elif account_info['account_age_hours'] < 72:
            risk_factors.append('new_account')
            risk_score += 2

        # Factor 2: Average bet size
        if account_info['avg_bet_size'] > 50000:
            risk_factors.append('very_large_avg_bet')
            risk_score += 3
        elif account_info['avg_bet_size'] > 10000:
            risk_factors.append('large_avg_bet')
            risk_score += 2

        # Factor 3: Few bets but high volume
        if account_info['total_bets'] <= 5 and account_info['total_volume'] > 100000:
            risk_factors.append('few_bets_high_volume')
            risk_score += 2

        # Factor 4: Single market focus (potential manipulation)
        if account_info['markets_traded'] == 1 and account_info['total_bets'] >= 5:
            risk_factors.append('single_market_focus')
            risk_score += 1

        # Determine risk level
        if risk_score >= 6:
            risk_level = 'critical'
        elif risk_score >= 4:
            risk_level = 'high'
        elif risk_score >= 2:
            risk_level = 'medium'
        else:
            risk_level = 'low'

        return {
            'address': address,
            'risk_level': risk_level,
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'account_age_hours': account_info['account_age_hours'],
            'total_bets': account_info['total_bets'],
            'total_volume': account_info['total_volume'],
            'avg_bet_size': account_info['avg_bet_size'],
            'markets_traded': account_info['markets_traded'],
            'is_new': is_new,
        }

    def get_new_accounts_summary(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get summary of new account activity.

        Args:
            hours: Hours to look back

        Returns:
            Summary dictionary
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        summary = {
            'total_new_accounts': 0,
            'total_new_account_volume': 0.0,
            'by_severity': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0},
            'accounts': [],
        }

        try:
            # Get all unique addresses with bets in time window
            markets = self.db.get_active_markets(limit=50)
            addresses_seen = set()

            for market in markets:
                bets = self.db.get_bets_by_market(market.id, since=since)
                for bet in bets:
                    addresses_seen.add(bet.address)

            # Check each address
            for address in addresses_seen:
                is_new, account_info = self.is_new_account(address)

                if is_new:
                    risk_profile = self.get_account_risk_profile(address)

                    summary['total_new_accounts'] += 1
                    summary['total_new_account_volume'] += account_info['total_volume']
                    summary['by_severity'][risk_profile['risk_level']] += 1
                    summary['accounts'].append({
                        'address': address,
                        'risk_level': risk_profile['risk_level'],
                        'account_age_hours': account_info['account_age_hours'],
                        'total_bets': account_info['total_bets'],
                        'total_volume': account_info['total_volume'],
                    })

            # Sort by risk level and volume
            summary['accounts'].sort(
                key=lambda x: (
                    {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}[x['risk_level']],
                    -x['total_volume']
                )
            )

        except Exception as e:
            logger.error(f"Error generating new accounts summary: {e}", exc_info=True)
            summary['error'] = str(e)

        return summary
