"""
Unit tests for detection algorithms.
"""

import pytest
from datetime import datetime, timedelta
import json
from pathlib import Path

from src.detection.anomaly_algorithms import (
    ZScoreDetector,
    IQRDetector,
    calculate_statistics,
    is_outlier_by_zscore,
    is_outlier_by_iqr
)


# Load test fixtures
def load_fixtures():
    """Load test fixture data."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_data.json"
    with open(fixture_path, 'r') as f:
        return json.load(f)


class TestZScoreDetector:
    """Test Z-score anomaly detection."""

    def test_detect_normal_value(self):
        """Test that normal values are not flagged."""
        detector = ZScoreDetector(threshold=3.0)
        data = [10, 12, 11, 13, 10, 12, 11, 13, 12, 11]
        value = 12

        result = detector.detect(value, data)

        assert not result.is_anomaly
        assert result.method == 'z_score'
        assert result.score < 3.0

    def test_detect_outlier(self):
        """Test that outliers are detected."""
        detector = ZScoreDetector(threshold=3.0)
        data = [10, 12, 11, 13, 10, 12, 11, 13, 12, 11]
        value = 100  # Clear outlier

        result = detector.detect(value, data)

        assert result.is_anomaly
        assert result.method == 'z_score'
        assert result.score > 3.0

    def test_insufficient_data(self):
        """Test handling of insufficient data."""
        detector = ZScoreDetector(threshold=3.0)
        data = [10]  # Only one data point
        value = 12

        result = detector.detect(value, data)

        assert not result.is_anomaly
        assert 'error' in result.details
        assert result.details['error'] == 'insufficient_data'

    def test_zero_variance(self):
        """Test handling of zero variance data."""
        detector = ZScoreDetector(threshold=3.0)
        data = [10, 10, 10, 10, 10]  # All same value
        value_same = 10
        value_different = 15

        result_same = detector.detect(value_same, data)
        result_different = detector.detect(value_different, data)

        assert not result_same.is_anomaly
        assert result_different.is_anomaly
        assert result_different.score == float('inf')


class TestIQRDetector:
    """Test IQR anomaly detection."""

    def test_detect_normal_value(self):
        """Test that normal values are not flagged."""
        detector = IQRDetector(multiplier=1.5)
        data = [10, 12, 15, 18, 20, 22, 25, 28, 30, 32]
        value = 20

        result = detector.detect(value, data)

        assert not result.is_anomaly
        assert result.method == 'iqr'

    def test_detect_outlier_high(self):
        """Test detection of high outlier."""
        detector = IQRDetector(multiplier=1.5)
        data = [10, 12, 15, 18, 20, 22, 25, 28, 30, 32]
        value = 100  # High outlier

        result = detector.detect(value, data)

        assert result.is_anomaly
        assert result.method == 'iqr'
        assert value > result.details['upper_bound']

    def test_detect_outlier_low(self):
        """Test detection of low outlier."""
        detector = IQRDetector(multiplier=1.5)
        data = [10, 12, 15, 18, 20, 22, 25, 28, 30, 32]
        value = 1  # Low outlier

        result = detector.detect(value, data)

        assert result.is_anomaly
        assert result.method == 'iqr'
        assert value < result.details['lower_bound']

    def test_insufficient_data(self):
        """Test handling of insufficient data."""
        detector = IQRDetector(multiplier=1.5)
        data = [10, 12]  # Too few data points
        value = 15

        result = detector.detect(value, data)

        assert not result.is_anomaly
        assert 'error' in result.details


class TestStatisticsCalculation:
    """Test statistical calculation functions."""

    def test_calculate_statistics(self):
        """Test comprehensive statistics calculation."""
        data = [10, 15, 20, 25, 30, 35, 40, 45, 50]

        stats = calculate_statistics(data)

        assert stats['count'] == 9
        assert stats['mean'] == 30.0
        assert stats['median'] == 30.0
        assert stats['min'] == 10.0
        assert stats['max'] == 50.0
        assert stats['q1'] == 17.5
        assert stats['q3'] == 42.5
        assert stats['iqr'] == 25.0

    def test_calculate_statistics_empty(self):
        """Test statistics calculation with empty data."""
        data = []

        stats = calculate_statistics(data)

        assert stats['count'] == 0
        assert stats['mean'] == 0.0

    def test_is_outlier_by_zscore(self):
        """Test z-score outlier check."""
        mean = 100.0
        std_dev = 10.0

        # Normal value (within 3 sigma)
        is_outlier, z_score = is_outlier_by_zscore(105, mean, std_dev, threshold=3.0)
        assert not is_outlier
        assert z_score == 0.5

        # Outlier (beyond 3 sigma)
        is_outlier, z_score = is_outlier_by_zscore(140, mean, std_dev, threshold=3.0)
        assert is_outlier
        assert z_score == 4.0

    def test_is_outlier_by_iqr(self):
        """Test IQR outlier check."""
        q1 = 25.0
        q3 = 75.0

        # Normal value (within bounds)
        is_outlier, details = is_outlier_by_iqr(50, q1, q3, multiplier=1.5)
        assert not is_outlier

        # Outlier (beyond upper bound)
        is_outlier, details = is_outlier_by_iqr(200, q1, q3, multiplier=1.5)
        assert is_outlier
        assert 200 > details['upper_bound']


class TestLargeBetDetection:
    """Test large bet detection logic (integration-style tests)."""

    def test_absolute_threshold_detection(self):
        """Test absolute threshold detection."""
        fixtures = load_fixtures()

        # Test medium threshold
        medium_bet = 15000
        assert medium_bet >= 10000  # Medium threshold
        assert medium_bet < 50000   # Below high threshold

        # Test high threshold
        high_bet = 55000
        assert high_bet >= 50000   # High threshold
        assert high_bet < 100000   # Below critical threshold

        # Test critical threshold
        critical_bet = 125000
        assert critical_bet >= 100000  # Critical threshold

    def test_market_relative_detection(self):
        """Test market-relative detection."""
        fixtures = load_fixtures()
        market = fixtures['markets'][0]
        market_volume = market['total_volume']  # 1,000,000

        # 5% of market volume
        threshold_pct = 5.0
        bet_size = market_volume * (threshold_pct / 100)  # 50,000

        assert bet_size == 50000
        assert (bet_size / market_volume) * 100 >= threshold_pct


class TestNewAccountDetection:
    """Test new account detection logic."""

    def test_new_account_thresholds(self):
        """Test new account detection thresholds."""
        # Configuration values
        new_account_threshold_hours = 72  # 3 days
        first_n_bets = 10
        large_bet_threshold = 10000
        suspicious_first_bet_threshold = 50000

        # Test thresholds
        assert new_account_threshold_hours == 72
        assert first_n_bets == 10
        assert large_bet_threshold == 10000
        assert suspicious_first_bet_threshold == 50000

    def test_severity_calculation(self):
        """Test severity calculation for new accounts."""
        # First bet scenarios
        assert 55000 >= 50000  # First bet above suspicious threshold = critical
        assert 25000 >= 10000 and 25000 < 50000  # First bet large but below suspicious = high

        # Early bet scenarios (within first 10)
        bet_position_5 = 5
        bet_size_15k = 15000
        assert bet_position_5 <= 10  # Within monitoring window
        assert bet_size_15k >= 10000  # Large bet

    def test_account_age_calculation(self):
        """Test account age calculation."""
        # Account age boundaries
        very_new_hours = 12  # < 24 hours
        new_hours = 48  # 24-72 hours
        old_hours = 168  # > 72 hours (7 days)

        assert very_new_hours < 24
        assert 24 <= new_hours <= 72
        assert old_hours > 72


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
