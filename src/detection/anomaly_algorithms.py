"""
Statistical anomaly detection algorithms.

Provides methods for detecting outliers and anomalies in betting data:
- Z-score method: Standard deviation-based detection
- IQR method: Interquartile range-based detection
- Moving average: Trend-based detection
"""

from typing import List, Tuple, Optional
import numpy as np
from dataclasses import dataclass


@dataclass
class AnomalyResult:
    """Result of anomaly detection."""
    is_anomaly: bool
    score: float
    threshold: float
    method: str
    details: dict


class ZScoreDetector:
    """Detect anomalies using z-score (standard deviation) method."""

    def __init__(self, threshold: float = 3.0):
        """
        Initialize z-score detector.

        Args:
            threshold: Number of standard deviations to consider anomalous
        """
        self.threshold = threshold

    def detect(self, value: float, data: List[float]) -> AnomalyResult:
        """
        Detect if value is anomalous compared to data.

        Args:
            value: Value to test
            data: Historical data for comparison

        Returns:
            AnomalyResult with detection details
        """
        if not data or len(data) < 2:
            return AnomalyResult(
                is_anomaly=False,
                score=0.0,
                threshold=self.threshold,
                method='z_score',
                details={'error': 'insufficient_data', 'data_size': len(data)}
            )

        # Calculate mean and standard deviation
        mean = np.mean(data)
        std_dev = np.std(data, ddof=1)  # Sample standard deviation

        # Handle zero standard deviation
        if std_dev == 0:
            return AnomalyResult(
                is_anomaly=value != mean,
                score=float('inf') if value != mean else 0.0,
                threshold=self.threshold,
                method='z_score',
                details={'mean': mean, 'std_dev': 0.0, 'note': 'zero_variance'}
            )

        # Calculate z-score
        z_score = abs((value - mean) / std_dev)

        return AnomalyResult(
            is_anomaly=z_score > self.threshold,
            score=z_score,
            threshold=self.threshold,
            method='z_score',
            details={
                'mean': float(mean),
                'std_dev': float(std_dev),
                'z_score': float(z_score),
                'value': value,
                'data_size': len(data)
            }
        )


class IQRDetector:
    """Detect anomalies using IQR (Interquartile Range) method."""

    def __init__(self, multiplier: float = 1.5):
        """
        Initialize IQR detector.

        Args:
            multiplier: IQR multiplier for outlier bounds (1.5 = standard, 3.0 = extreme)
        """
        self.multiplier = multiplier

    def detect(self, value: float, data: List[float]) -> AnomalyResult:
        """
        Detect if value is anomalous using IQR method.

        Args:
            value: Value to test
            data: Historical data for comparison

        Returns:
            AnomalyResult with detection details
        """
        if not data or len(data) < 4:
            return AnomalyResult(
                is_anomaly=False,
                score=0.0,
                threshold=self.multiplier,
                method='iqr',
                details={'error': 'insufficient_data', 'data_size': len(data)}
            )

        # Calculate quartiles
        q1 = np.percentile(data, 25)
        q3 = np.percentile(data, 75)
        iqr = q3 - q1

        # Calculate bounds
        lower_bound = q1 - (self.multiplier * iqr)
        upper_bound = q3 + (self.multiplier * iqr)

        # Calculate how far outside bounds (if at all)
        if value < lower_bound:
            distance = lower_bound - value
            score = distance / iqr if iqr > 0 else float('inf')
        elif value > upper_bound:
            distance = value - upper_bound
            score = distance / iqr if iqr > 0 else float('inf')
        else:
            score = 0.0

        is_anomaly = value < lower_bound or value > upper_bound

        return AnomalyResult(
            is_anomaly=is_anomaly,
            score=float(score),
            threshold=self.multiplier,
            method='iqr',
            details={
                'q1': float(q1),
                'q3': float(q3),
                'iqr': float(iqr),
                'lower_bound': float(lower_bound),
                'upper_bound': float(upper_bound),
                'value': value,
                'data_size': len(data)
            }
        )


class MovingAverageDetector:
    """Detect anomalies using moving average deviation method."""

    def __init__(self, window_size: int = 24, threshold: float = 2.5):
        """
        Initialize moving average detector.

        Args:
            window_size: Number of data points for moving average
            threshold: Deviation threshold (as multiple of std dev)
        """
        self.window_size = window_size
        self.threshold = threshold

    def detect(self, value: float, data: List[float]) -> AnomalyResult:
        """
        Detect if value deviates significantly from moving average.

        Args:
            value: Value to test
            data: Historical data (should be time-ordered)

        Returns:
            AnomalyResult with detection details
        """
        if not data or len(data) < self.window_size:
            return AnomalyResult(
                is_anomaly=False,
                score=0.0,
                threshold=self.threshold,
                method='moving_average',
                details={'error': 'insufficient_data', 'data_size': len(data), 'required': self.window_size}
            )

        # Take last window_size points
        window_data = data[-self.window_size:]

        # Calculate moving average and std dev
        ma = np.mean(window_data)
        ma_std = np.std(window_data, ddof=1)

        # Handle zero standard deviation
        if ma_std == 0:
            return AnomalyResult(
                is_anomaly=value != ma,
                score=float('inf') if value != ma else 0.0,
                threshold=self.threshold,
                method='moving_average',
                details={'ma': ma, 'ma_std': 0.0, 'note': 'zero_variance'}
            )

        # Calculate deviation score
        deviation = abs((value - ma) / ma_std)

        return AnomalyResult(
            is_anomaly=deviation > self.threshold,
            score=float(deviation),
            threshold=self.threshold,
            method='moving_average',
            details={
                'moving_average': float(ma),
                'ma_std': float(ma_std),
                'deviation': float(deviation),
                'value': value,
                'window_size': self.window_size,
                'data_size': len(data)
            }
        )


class CompositeDetector:
    """Combine multiple detection methods for robust anomaly detection."""

    def __init__(
        self,
        z_score_threshold: float = 3.0,
        iqr_multiplier: float = 1.5,
        ma_window: int = 24,
        ma_threshold: float = 2.5,
        min_methods_agree: int = 2
    ):
        """
        Initialize composite detector.

        Args:
            z_score_threshold: Z-score threshold
            iqr_multiplier: IQR multiplier
            ma_window: Moving average window size
            ma_threshold: Moving average deviation threshold
            min_methods_agree: Minimum number of methods that must agree
        """
        self.z_score = ZScoreDetector(z_score_threshold)
        self.iqr = IQRDetector(iqr_multiplier)
        self.ma = MovingAverageDetector(ma_window, ma_threshold)
        self.min_methods_agree = min_methods_agree

    def detect(self, value: float, data: List[float]) -> AnomalyResult:
        """
        Detect anomalies using multiple methods.

        Args:
            value: Value to test
            data: Historical data

        Returns:
            AnomalyResult combining all methods
        """
        # Run all detection methods
        results = {
            'z_score': self.z_score.detect(value, data),
            'iqr': self.iqr.detect(value, data),
            'moving_average': self.ma.detect(value, data)
        }

        # Count how many methods detected anomaly
        anomaly_count = sum(1 for r in results.values() if r.is_anomaly)

        # Composite decision
        is_anomaly = anomaly_count >= self.min_methods_agree

        # Calculate composite score (average of non-zero scores)
        scores = [r.score for r in results.values() if r.score > 0]
        composite_score = np.mean(scores) if scores else 0.0

        return AnomalyResult(
            is_anomaly=is_anomaly,
            score=float(composite_score),
            threshold=float(self.min_methods_agree),
            method='composite',
            details={
                'methods_detected': anomaly_count,
                'methods_total': len(results),
                'required_agreement': self.min_methods_agree,
                'individual_results': {
                    method: {
                        'is_anomaly': r.is_anomaly,
                        'score': r.score,
                        'details': r.details
                    }
                    for method, r in results.items()
                }
            }
        )


def calculate_statistics(data: List[float]) -> dict:
    """
    Calculate comprehensive statistics for a dataset.

    Args:
        data: List of numerical values

    Returns:
        Dictionary with statistical measures
    """
    if not data:
        return {
            'count': 0,
            'mean': 0.0,
            'median': 0.0,
            'std_dev': 0.0,
            'min': 0.0,
            'max': 0.0,
            'q1': 0.0,
            'q3': 0.0,
            'iqr': 0.0
        }

    arr = np.array(data)

    return {
        'count': len(data),
        'mean': float(np.mean(arr)),
        'median': float(np.median(arr)),
        'std_dev': float(np.std(arr, ddof=1)) if len(data) > 1 else 0.0,
        'min': float(np.min(arr)),
        'max': float(np.max(arr)),
        'q1': float(np.percentile(arr, 25)),
        'q3': float(np.percentile(arr, 75)),
        'iqr': float(np.percentile(arr, 75) - np.percentile(arr, 25))
    }


def is_outlier_by_zscore(value: float, mean: float, std_dev: float, threshold: float = 3.0) -> Tuple[bool, float]:
    """
    Quick helper to check if value is outlier by z-score.

    Args:
        value: Value to test
        mean: Population mean
        std_dev: Population standard deviation
        threshold: Z-score threshold

    Returns:
        Tuple of (is_outlier, z_score)
    """
    if std_dev == 0:
        return (value != mean, float('inf') if value != mean else 0.0)

    z_score = abs((value - mean) / std_dev)
    return (z_score > threshold, z_score)


def is_outlier_by_iqr(value: float, q1: float, q3: float, multiplier: float = 1.5) -> Tuple[bool, dict]:
    """
    Quick helper to check if value is outlier by IQR.

    Args:
        value: Value to test
        q1: First quartile
        q3: Third quartile
        multiplier: IQR multiplier

    Returns:
        Tuple of (is_outlier, details_dict)
    """
    iqr = q3 - q1
    lower_bound = q1 - (multiplier * iqr)
    upper_bound = q3 + (multiplier * iqr)

    is_outlier = value < lower_bound or value > upper_bound

    return (is_outlier, {
        'lower_bound': lower_bound,
        'upper_bound': upper_bound,
        'iqr': iqr
    })
