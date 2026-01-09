"""
Database repository layer for Polymarket monitoring bot.

Provides data access methods for all database operations.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, desc, and_, func, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import json

from .models import Base, Market, Bet, Alert, MarketStatistics, SystemState
from utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseRepository:
    """Repository for database operations."""

    def __init__(self, database_path: str, echo: bool = False):
        """
        Initialize database repository.

        Args:
            database_path: Path to SQLite database file
            echo: Whether to echo SQL queries to console
        """
        self.database_path = database_path
        self.engine = create_engine(
            f'sqlite:///{database_path}',
            echo=echo,
            connect_args={'check_same_thread': False}  # Needed for SQLite with threads
        )

        # Enable WAL mode for better concurrency
        with self.engine.connect() as conn:
            conn.execute(text('PRAGMA journal_mode=WAL'))
            conn.commit()

        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created successfully")

    def get_session(self) -> Session:
        """Get new database session."""
        return self.SessionLocal()

    # Market operations
    def upsert_market(self, market_data: Dict[str, Any]) -> Market:
        """
        Insert or update market.

        Args:
            market_data: Market data dictionary

        Returns:
            Market instance
        """
        session = self.get_session()
        try:
            market = session.query(Market).filter_by(id=market_data['id']).first()

            if market:
                # Update existing market
                for key, value in market_data.items():
                    setattr(market, key, value)
                market.last_updated = datetime.utcnow()
            else:
                # Create new market
                market = Market(**market_data)
                session.add(market)

            session.commit()
            session.refresh(market)
            return market

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error upserting market: {e}", extra={'market_id': market_data.get('id')})
            raise
        finally:
            session.close()

    def get_market(self, market_id: str) -> Optional[Market]:
        """Get market by ID."""
        session = self.get_session()
        try:
            return session.query(Market).filter_by(id=market_id).first()
        finally:
            session.close()

    def get_active_markets(self, limit: Optional[int] = None) -> List[Market]:
        """
        Get all active markets.

        Args:
            limit: Maximum number of markets to return

        Returns:
            List of Market instances
        """
        session = self.get_session()
        try:
            query = session.query(Market).filter_by(active=True).order_by(desc(Market.total_volume))
            if limit:
                query = query.limit(limit)
            return query.all()
        finally:
            session.close()

    # Bet operations
    def insert_bet(self, bet_data: Dict[str, Any]) -> tuple[Bet, bool]:
        """
        Insert new bet.

        Args:
            bet_data: Bet data dictionary

        Returns:
            Tuple of (Bet instance, is_new boolean)
        """
        session = self.get_session()
        try:
            # Check if bet already exists (avoid duplicates)
            existing = session.query(Bet).filter_by(order_id=bet_data['order_id']).first()
            if existing:
                logger.debug(f"Bet already exists: {bet_data['order_id']}")
                return existing, False

            bet = Bet(**bet_data)
            session.add(bet)
            session.commit()
            session.refresh(bet)
            return bet, True

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error inserting bet: {e}", extra={'order_id': bet_data.get('order_id')})
            raise
        finally:
            session.close()

    def get_bets_by_market(
        self,
        market_id: str,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Bet]:
        """
        Get bets for a market.

        Args:
            market_id: Market ID
            since: Only return bets after this timestamp
            limit: Maximum number of bets to return

        Returns:
            List of Bet instances
        """
        session = self.get_session()
        try:
            query = session.query(Bet).filter_by(market_id=market_id)

            if since:
                query = query.filter(Bet.timestamp >= since)

            query = query.order_by(desc(Bet.timestamp))

            if limit:
                query = query.limit(limit)

            return query.all()
        finally:
            session.close()

    def get_bets_by_address(
        self,
        address: str,
        market_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Bet]:
        """
        Get bets by wallet address.

        Args:
            address: Wallet address
            market_id: Optional market ID filter
            since: Only return bets after this timestamp
            limit: Maximum number of bets to return

        Returns:
            List of Bet instances
        """
        session = self.get_session()
        try:
            filters = [Bet.address == address]

            if market_id:
                filters.append(Bet.market_id == market_id)

            if since:
                filters.append(Bet.timestamp >= since)

            query = session.query(Bet).filter(and_(*filters)).order_by(desc(Bet.timestamp))

            if limit:
                query = query.limit(limit)

            return query.all()
        finally:
            session.close()

    # Alert operations
    def create_alert(self, alert_data: Dict[str, Any]) -> Alert:
        """
        Create new alert.

        Args:
            alert_data: Alert data dictionary

        Returns:
            Alert instance
        """
        session = self.get_session()
        try:
            # Convert details dict to JSON string if needed
            if isinstance(alert_data.get('details'), dict):
                alert_data['details'] = json.dumps(alert_data['details'])

            alert = Alert(**alert_data)
            session.add(alert)
            session.commit()
            session.refresh(alert)
            return alert

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error creating alert: {e}")
            raise
        finally:
            session.close()

    def mark_alert_sent(self, alert_id: int, discord_message_id: Optional[str] = None):
        """
        Mark alert as sent to Discord.

        Args:
            alert_id: Alert ID
            discord_message_id: Discord message ID (optional)
        """
        session = self.get_session()
        try:
            alert = session.query(Alert).filter_by(id=alert_id).first()
            if alert:
                alert.sent_to_discord = True
                alert.sent_at = datetime.utcnow()
                if discord_message_id:
                    alert.discord_message_id = discord_message_id
                session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error marking alert as sent: {e}", extra={'alert_id': alert_id})
            raise
        finally:
            session.close()

    def get_unsent_alerts(self, limit: Optional[int] = None) -> List[Alert]:
        """Get alerts that haven't been sent to Discord yet."""
        session = self.get_session()
        try:
            query = session.query(Alert).filter_by(sent_to_discord=False).order_by(Alert.created_at)
            if limit:
                query = query.limit(limit)
            return query.all()
        finally:
            session.close()

    def get_recent_alerts(self, hours: int = 24, limit: Optional[int] = None) -> List[Alert]:
        """
        Get recent alerts.

        Args:
            hours: Number of hours to look back
            limit: Maximum number of alerts to return

        Returns:
            List of Alert instances
        """
        session = self.get_session()
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            query = session.query(Alert).filter(Alert.created_at >= since).order_by(desc(Alert.created_at))

            if limit:
                query = query.limit(limit)

            return query.all()
        finally:
            session.close()

    # MarketStatistics operations
    def upsert_market_statistics(self, stats_data: Dict[str, Any]) -> MarketStatistics:
        """
        Insert or update market statistics.

        Args:
            stats_data: Statistics data dictionary

        Returns:
            MarketStatistics instance
        """
        session = self.get_session()
        try:
            # Find existing stats for this market and window
            stats = session.query(MarketStatistics).filter_by(
                market_id=stats_data['market_id'],
                window_hours=stats_data['window_hours']
            ).order_by(desc(MarketStatistics.calculated_at)).first()

            if stats:
                # Update existing stats
                for key, value in stats_data.items():
                    setattr(stats, key, value)
                stats.calculated_at = datetime.utcnow()
            else:
                # Create new stats
                stats = MarketStatistics(**stats_data)
                session.add(stats)

            session.commit()
            session.refresh(stats)
            return stats

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error upserting market statistics: {e}", extra={'market_id': stats_data.get('market_id')})
            raise
        finally:
            session.close()

    def get_market_statistics(
        self,
        market_id: str,
        window_hours: int = 24
    ) -> Optional[MarketStatistics]:
        """
        Get most recent market statistics.

        Args:
            market_id: Market ID
            window_hours: Statistics window in hours

        Returns:
            MarketStatistics instance or None
        """
        session = self.get_session()
        try:
            return session.query(MarketStatistics).filter_by(
                market_id=market_id,
                window_hours=window_hours
            ).order_by(desc(MarketStatistics.calculated_at)).first()
        finally:
            session.close()

    # SystemState operations
    def set_system_state(self, key: str, value: str):
        """
        Set system state value.

        Args:
            key: State key
            value: State value
        """
        session = self.get_session()
        try:
            state = session.query(SystemState).filter_by(key=key).first()

            if state:
                state.value = value
                state.updated_at = datetime.utcnow()
            else:
                state = SystemState(key=key, value=value)
                session.add(state)

            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error setting system state: {e}", extra={'key': key})
            raise
        finally:
            session.close()

    def get_system_state(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get system state value.

        Args:
            key: State key
            default: Default value if key not found

        Returns:
            State value or default
        """
        session = self.get_session()
        try:
            state = session.query(SystemState).filter_by(key=key).first()
            return state.value if state else default
        finally:
            session.close()

    # Analytics/aggregation queries
    def get_market_bet_count(self, market_id: str, since: Optional[datetime] = None) -> int:
        """Get total number of bets for a market."""
        session = self.get_session()
        try:
            query = session.query(func.count(Bet.id)).filter_by(market_id=market_id)

            if since:
                query = query.filter(Bet.timestamp >= since)

            return query.scalar() or 0
        finally:
            session.close()

    def get_market_total_volume(self, market_id: str, since: Optional[datetime] = None) -> float:
        """Get total volume for a market."""
        session = self.get_session()
        try:
            query = session.query(func.sum(Bet.size)).filter_by(market_id=market_id)

            if since:
                query = query.filter(Bet.timestamp >= since)

            return query.scalar() or 0.0
        finally:
            session.close()

    def get_unique_addresses_count(self, market_id: str, since: Optional[datetime] = None) -> int:
        """Get count of unique addresses for a market."""
        session = self.get_session()
        try:
            query = session.query(func.count(func.distinct(Bet.address))).filter_by(market_id=market_id)

            if since:
                query = query.filter(Bet.timestamp >= since)

            return query.scalar() or 0
        finally:
            session.close()

    def close(self):
        """Close database connection."""
        self.engine.dispose()
        logger.info("Database connection closed")
