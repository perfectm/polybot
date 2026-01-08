"""
Polymarket data collector using py-clob-client.

Fetches market data and trades from Polymarket CLOB API.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import TradeParams, ApiCreds
import aiohttp

from utils.logger import get_logger

logger = get_logger(__name__)


class PolymarketDataCollector:
    """Collector for Polymarket market and trade data."""

    def __init__(
        self,
        base_url: str = "https://clob.polymarket.com",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_passphrase: Optional[str] = None,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        backoff_factor: int = 2
    ):
        """
        Initialize Polymarket data collector.

        Args:
            base_url: Polymarket CLOB API base URL
            api_key: Optional API key for authenticated requests
            api_secret: Optional API secret for authenticated requests
            api_passphrase: Optional API passphrase for authenticated requests
            timeout_seconds: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            backoff_factor: Exponential backoff factor for retries
        """
        self.base_url = base_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.client = None  # Lazy initialization

        logger.info("Polymarket data collector initialized", extra={'base_url': base_url})

    def _get_client(self) -> ClobClient:
        """Get or create the CLOB client (lazy initialization)."""
        if self.client is None:
            # Check if we have API credentials (key + secret + passphrase)
            has_api_creds = self.api_key and self.api_secret and self.api_passphrase

            if has_api_creds:
                # Use ApiCreds for authenticated access
                creds = ApiCreds(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    api_passphrase=self.api_passphrase
                )
                self.client = ClobClient(
                    host=self.base_url,
                    key="",  # Empty for API creds mode
                    chain_id=137,  # Polygon mainnet
                    creds=creds
                )
                logger.info("CLOB client initialized with API credentials (authenticated)")
            else:
                # Read-only mode
                self.client = ClobClient(
                    host=self.base_url,
                    key="",
                    chain_id=137
                )
                logger.info("CLOB client initialized (read-only mode)")
        return self.client

    async def fetch_active_markets(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch active markets from Polymarket.

        Args:
            limit: Maximum number of markets to fetch

        Returns:
            List of market dictionaries
        """
        try:
            loop = asyncio.get_event_loop()

            # Get markets using py-clob-client (runs in thread pool since it's synchronous)
            markets_raw = await loop.run_in_executor(
                None,
                lambda: self._get_client().get_markets()
            )

            if not markets_raw:
                logger.warning("No markets returned from Polymarket API")
                return []

            # Parse and filter active markets
            markets = []
            # Handle both list and dict responses
            market_list = markets_raw if isinstance(markets_raw, list) else markets_raw.get('data', [])
            for i, market in enumerate(market_list):
                if i >= limit:  # Limit results
                    break
                try:
                    parsed_market = self._parse_market(market)
                    if parsed_market:
                        markets.append(parsed_market)
                except Exception as e:
                    logger.error(f"Error parsing market: {e}", extra={'market': str(market)[:100]})
                    continue

            logger.info(f"Fetched {len(markets)} active markets from Polymarket")
            return markets

        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []

    def _parse_market(self, market_raw: Any) -> Optional[Dict[str, Any]]:
        """
        Parse raw market data into standardized format.

        Args:
            market_raw: Raw market data from API

        Returns:
            Parsed market dictionary or None
        """
        try:
            # Extract market data (structure may vary based on API response)
            if isinstance(market_raw, dict):
                market_id = market_raw.get('condition_id') or market_raw.get('id')
                question = market_raw.get('question') or market_raw.get('title', 'Unknown')
                slug = market_raw.get('market_slug') or market_raw.get('slug', '')

                return {
                    'id': str(market_id),
                    'question': question,
                    'slug': slug,
                    'total_volume': float(market_raw.get('volume', 0.0)),
                    'active': market_raw.get('active', True),
                    'end_date': self._parse_datetime(market_raw.get('end_date_iso')),
                    'category': market_raw.get('category', ''),
                }
            return None

        except Exception as e:
            logger.error(f"Error parsing market data: {e}")
            return None

    async def fetch_market_trades(
        self,
        market_id: str,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent trades for a specific market using the public Data API.

        Args:
            market_id: Market condition ID
            since: Fetch trades after this timestamp
            limit: Maximum number of trades to fetch

        Returns:
            List of trade dictionaries
        """
        try:
            # Use the public Data API endpoint (no authentication required)
            url = "https://data-api.polymarket.com/trades"
            params = {
                "market": market_id,
                "limit": min(limit, 100),  # API allows up to 10,000 but we limit to 100
                "offset": 0
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as response:
                    if response.status != 200:
                        logger.warning(f"Data API returned status {response.status} for market {market_id}")
                        return []

                    trades_raw = await response.json()

            if not trades_raw:
                logger.debug(f"No trades found for market {market_id}")
                return []

            # Parse trades from Data API format
            trades = []
            for trade in trades_raw:
                try:
                    parsed_trade = self._parse_trade_from_data_api(trade, market_id)
                    if parsed_trade:
                        # Filter by timestamp if specified
                        if since and parsed_trade['timestamp'] < since:
                            continue
                        trades.append(parsed_trade)
                except Exception as e:
                    logger.error(f"Error parsing trade: {e}", extra={'trade': str(trade)[:100]})
                    continue

            logger.debug(f"Fetched {len(trades)} trades for market {market_id}")
            return trades

        except Exception as e:
            logger.error(f"Error fetching trades for market {market_id}: {e}")
            return []

    def _parse_trade_from_data_api(self, trade_raw: Any, market_id: str) -> Optional[Dict[str, Any]]:
        """
        Parse trade data from the public Data API format.

        Args:
            trade_raw: Raw trade data from Data API
            market_id: Market ID

        Returns:
            Parsed trade dictionary or None
        """
        try:
            if isinstance(trade_raw, dict):
                # Data API format: proxyWallet, side, size, price, timestamp, conditionId, etc
                timestamp = self._parse_datetime(trade_raw.get('timestamp'))

                # Calculate trade size in USD
                price = float(trade_raw.get('price', 0.0))
                size_tokens = float(trade_raw.get('size', 0.0))
                size_usd = price * size_tokens  # Approximate USD value

                return {
                    'order_id': trade_raw.get('transactionHash', '')[:16],  # Use tx hash prefix as ID
                    'market_id': trade_raw.get('conditionId', market_id),
                    'address': trade_raw.get('proxyWallet', 'unknown'),
                    'outcome': trade_raw.get('outcome', 'YES'),
                    'size': size_usd,
                    'price': price,
                    'side': trade_raw.get('side', 'BUY').upper(),
                    'timestamp': timestamp or datetime.utcnow(),
                    'fee': 0.0,  # Data API doesn't include fees
                    'asset_id': trade_raw.get('asset', ''),
                }

            return None

        except Exception as e:
            logger.error(f"Error parsing trade data from Data API: {e}")
            return None

    def _parse_trade(self, trade_raw: Any, market_id: str) -> Optional[Dict[str, Any]]:
        """
        Parse raw trade data from CLOB API into standardized format (deprecated - use Data API).

        Args:
            trade_raw: Raw trade data from API
            market_id: Market ID

        Returns:
            Parsed trade dictionary or None
        """
        try:
            if isinstance(trade_raw, dict):
                # Extract trade data
                order_id = trade_raw.get('id') or trade_raw.get('trade_id', '')
                timestamp = self._parse_datetime(trade_raw.get('timestamp'))

                # Calculate trade size in USD
                # Price is typically in the 0-1 range for prediction markets
                price = float(trade_raw.get('price', 0.0))
                size_tokens = float(trade_raw.get('size', 0.0))
                size_usd = price * size_tokens  # Approximate USD value

                return {
                    'order_id': str(order_id),
                    'market_id': market_id,
                    'address': trade_raw.get('maker_address') or trade_raw.get('taker_address', 'unknown'),
                    'outcome': trade_raw.get('outcome', 'YES'),
                    'size': size_usd,
                    'price': price,
                    'side': trade_raw.get('side', 'BUY'),
                    'timestamp': timestamp or datetime.utcnow(),
                    'fee': float(trade_raw.get('fee', 0.0)),
                    'asset_id': trade_raw.get('asset_id', ''),
                }

            return None

        except Exception as e:
            logger.error(f"Error parsing trade data: {e}")
            return None

    async def fetch_all_recent_trades(
        self,
        market_ids: List[str],
        since: Optional[datetime] = None,
        limit_per_market: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent trades for multiple markets concurrently.

        Args:
            market_ids: List of market IDs
            since: Fetch trades after this timestamp
            limit_per_market: Maximum trades per market

        Returns:
            Combined list of all trades
        """
        tasks = [
            self.fetch_market_trades(market_id, since, limit_per_market)
            for market_id in market_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results and filter out errors
        all_trades = []
        for result in results:
            if isinstance(result, list):
                all_trades.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Error in concurrent fetch: {result}")

        # Sort by timestamp descending
        all_trades.sort(key=lambda t: t['timestamp'], reverse=True)

        logger.info(f"Fetched {len(all_trades)} total trades across {len(market_ids)} markets")
        return all_trades

    async def fetch_orderbook(self, market_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch order book for a market.

        Args:
            market_id: Market condition ID

        Returns:
            Order book data or None
        """
        try:
            loop = asyncio.get_event_loop()

            orderbook = await loop.run_in_executor(
                None,
                lambda: self._get_client().get_order_book(market_id)
            )

            if not orderbook:
                logger.debug(f"No orderbook data for market {market_id}")
                return None

            return self._parse_orderbook(orderbook)

        except Exception as e:
            logger.error(f"Error fetching orderbook for market {market_id}: {e}")
            return None

    def _parse_orderbook(self, orderbook_raw: Any) -> Dict[str, Any]:
        """Parse raw orderbook data."""
        try:
            if isinstance(orderbook_raw, dict):
                return {
                    'bids': orderbook_raw.get('bids', []),
                    'asks': orderbook_raw.get('asks', []),
                    'timestamp': datetime.utcnow(),
                }
            return {'bids': [], 'asks': [], 'timestamp': datetime.utcnow()}

        except Exception as e:
            logger.error(f"Error parsing orderbook: {e}")
            return {'bids': [], 'asks': [], 'timestamp': datetime.utcnow()}

    def _parse_datetime(self, dt_value) -> Optional[datetime]:
        """
        Parse datetime from various formats (string, int, or float).

        Args:
            dt_value: Datetime value (ISO string, Unix timestamp int/float/string)

        Returns:
            Datetime object or None
        """
        if not dt_value:
            return None

        try:
            # Handle integer/float Unix timestamps directly
            if isinstance(dt_value, (int, float)):
                return datetime.utcfromtimestamp(dt_value)

            # Handle string values
            if isinstance(dt_value, str):
                # Try parsing ISO format
                if 'T' in dt_value:
                    return datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
                # Try parsing unix timestamp string
                elif dt_value.isdigit():
                    return datetime.utcfromtimestamp(int(dt_value))

            return None

        except Exception as e:
            logger.error(f"Error parsing datetime '{dt_value}': {e}")
            return None

    async def health_check(self) -> bool:
        """
        Check if Polymarket API is reachable.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            # Simple health check - try to fetch markets
            markets = await self.fetch_active_markets(limit=1)
            is_healthy = len(markets) > 0

            if is_healthy:
                logger.info("Polymarket API health check passed")
            else:
                logger.warning("Polymarket API health check failed - no markets returned")

            return is_healthy

        except Exception as e:
            logger.error(f"Polymarket API health check failed: {e}")
            return False


# Utility function for exponential backoff
async def exponential_backoff_retry(
    func,
    max_retries: int = 3,
    backoff_factor: int = 2,
    *args,
    **kwargs
):
    """
    Execute function with exponential backoff retry logic.

    Args:
        func: Async function to execute
        max_retries: Maximum retry attempts
        backoff_factor: Backoff multiplier
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                logger.warning(
                    f"Retry {attempt + 1}/{max_retries} after error: {e}. "
                    f"Waiting {wait_time}s before retry"
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"All {max_retries} retry attempts failed")

    raise last_exception
