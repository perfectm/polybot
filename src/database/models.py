"""
Database models for Polymarket monitoring bot.

Defines SQLAlchemy ORM models for:
- Market: Polymarket market metadata
- Bet: Individual bet/trade records
- Alert: Alerts sent to Discord
- MarketStatistics: Rolling statistics for anomaly detection
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Index, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Market(Base):
    """Polymarket market information."""

    __tablename__ = 'markets'

    id = Column(String, primary_key=True)  # Polymarket market ID/condition_id
    question = Column(String, nullable=False)
    slug = Column(String, unique=True)
    total_volume = Column(Float, default=0.0)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Additional metadata
    end_date = Column(DateTime, nullable=True)
    category = Column(String, nullable=True)

    __table_args__ = (
        Index('idx_market_active', 'active'),
        Index('idx_market_slug', 'slug'),
    )

    def __repr__(self):
        return f"<Market(id='{self.id}', question='{self.question[:50]}...')>"


class Bet(Base):
    """Individual bet/trade records from Polymarket."""

    __tablename__ = 'bets'

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, unique=True, nullable=False)  # Polymarket order/trade ID
    market_id = Column(String, nullable=False)  # FK to markets.id
    address = Column(String, nullable=False)  # Wallet address
    outcome = Column(String, nullable=False)  # YES/NO or outcome token
    size = Column(Float, nullable=False)  # Bet size in USD
    price = Column(Float, nullable=False)  # Price at execution (0-1)
    side = Column(String, nullable=True)  # BUY/SELL
    timestamp = Column(DateTime, nullable=False)  # When bet was placed
    detected_at = Column(DateTime, default=datetime.utcnow)  # When we detected it

    # Additional trade metadata
    fee = Column(Float, nullable=True)
    asset_id = Column(String, nullable=True)  # Token ID

    __table_args__ = (
        Index('idx_bet_market', 'market_id'),
        Index('idx_bet_address', 'address'),
        Index('idx_bet_timestamp', 'timestamp'),
        Index('idx_bet_market_timestamp', 'market_id', 'timestamp'),
        Index('idx_bet_order_id', 'order_id'),
    )

    def __repr__(self):
        return f"<Bet(id={self.id}, market_id='{self.market_id}', size=${self.size}, address='{self.address[:10]}...')>"


class Alert(Base):
    """Alerts sent to Discord."""

    __tablename__ = 'alerts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String, nullable=False)  # 'large_bet', 'rapid_succession', 'statistical_anomaly'
    severity = Column(String, nullable=False)  # 'low', 'medium', 'high', 'critical'
    market_id = Column(String, nullable=False)
    details = Column(Text, nullable=False)  # JSON string with alert details
    sent_to_discord = Column(Boolean, default=False)
    discord_message_id = Column(String, nullable=True)  # Discord message ID for tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)

    # Reference to the bet that triggered this alert (if applicable)
    bet_id = Column(Integer, nullable=True)

    __table_args__ = (
        Index('idx_alert_type', 'alert_type'),
        Index('idx_alert_severity', 'severity'),
        Index('idx_alert_created', 'created_at'),
        Index('idx_alert_market', 'market_id'),
    )

    def __repr__(self):
        return f"<Alert(id={self.id}, type='{self.alert_type}', severity='{self.severity}', sent={self.sent_to_discord})>"


class MarketStatistics(Base):
    """Rolling statistics for each market to detect anomalies."""

    __tablename__ = 'market_statistics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_id = Column(String, nullable=False)
    window_hours = Column(Integer, nullable=False, default=24)  # Statistics window

    # Statistical measures
    mean_bet_size = Column(Float, nullable=False)
    std_dev_bet_size = Column(Float, nullable=False)
    median_bet_size = Column(Float, nullable=False)
    q1 = Column(Float, nullable=False)  # First quartile (25th percentile)
    q3 = Column(Float, nullable=False)  # Third quartile (75th percentile)
    iqr = Column(Float, nullable=False)  # Interquartile range (Q3 - Q1)

    # Additional metrics
    total_bets = Column(Integer, nullable=False)
    total_volume = Column(Float, nullable=False)
    unique_addresses = Column(Integer, nullable=False)

    # Calculation metadata
    calculated_at = Column(DateTime, default=datetime.utcnow)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('idx_stats_market', 'market_id'),
        Index('idx_stats_calculated', 'calculated_at'),
        Index('idx_stats_market_window', 'market_id', 'window_hours'),
    )

    def __repr__(self):
        return f"<MarketStatistics(market_id='{self.market_id}', mean=${self.mean_bet_size:.2f}, total_bets={self.total_bets})>"


class SystemState(Base):
    """Track system state and metadata."""

    __tablename__ = 'system_state'

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, nullable=False)  # e.g., 'last_poll_timestamp', 'last_processed_trade_id'
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_system_state_key', 'key'),
    )

    def __repr__(self):
        return f"<SystemState(key='{self.key}', value='{self.value}')>"
