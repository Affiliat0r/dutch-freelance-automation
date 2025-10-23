"""Exchange rate service for converting foreign currencies to EUR."""

import requests
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Optional
from decimal import Decimal
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Cache file for storing exchange rates
CACHE_FILE = Path(__file__).parent.parent / "temp" / "exchange_rates_cache.json"

class ExchangeRateService:
    """Service for fetching and caching exchange rates."""

    BASE_URL = "https://api.frankfurter.app"
    CACHE_DAYS = 90  # Cache rates for 90 days

    def __init__(self):
        """Initialize the exchange rate service."""
        self.cache = self._load_cache()

    def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str = "EUR",
        rate_date: Optional[date] = None
    ) -> Dict:
        """
        Get exchange rate from one currency to another.

        Args:
            from_currency: Source currency code (e.g., 'TRY', 'USD')
            to_currency: Target currency code (default: 'EUR')
            rate_date: Date for historical rate (default: today)

        Returns:
            Dict with 'rate', 'date', 'source', 'success' keys
        """
        # If same currency, no conversion needed
        if from_currency == to_currency:
            return {
                'success': True,
                'rate': Decimal('1.0'),
                'date': rate_date or date.today(),
                'source': 'no_conversion',
                'from_currency': from_currency,
                'to_currency': to_currency
            }

        # Use today if no date specified
        if rate_date is None:
            rate_date = date.today()

        # Check cache first
        cache_key = f"{from_currency}_{to_currency}_{rate_date}"
        if cache_key in self.cache:
            logger.info(f"Exchange rate found in cache: {cache_key}")
            return self.cache[cache_key]

        # Fetch from API
        try:
            rate_data = self._fetch_from_api(from_currency, to_currency, rate_date)

            # Cache the result
            self.cache[cache_key] = rate_data
            self._save_cache()

            return rate_data

        except Exception as e:
            logger.error(f"Failed to fetch exchange rate: {e}")

            # Try to get a recent cached rate as fallback
            fallback = self._get_fallback_rate(from_currency, to_currency)
            if fallback:
                logger.warning(f"Using fallback rate from cache")
                return fallback

            # Return error
            return {
                'success': False,
                'error': str(e),
                'from_currency': from_currency,
                'to_currency': to_currency,
                'date': rate_date
            }

    def _fetch_from_api(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: date
    ) -> Dict:
        """
        Fetch exchange rate from Frankfurter API.

        API Documentation: https://www.frankfurter.app/docs/
        """
        # Format date as YYYY-MM-DD
        date_str = rate_date.strftime('%Y-%m-%d')

        # Build URL
        # If rate_date is today, use /latest endpoint for current rates
        if rate_date == date.today():
            url = f"{self.BASE_URL}/latest"
        else:
            url = f"{self.BASE_URL}/{date_str}"

        # Add query parameters
        params = {
            'from': from_currency,
            'to': to_currency
        }

        logger.info(f"Fetching exchange rate: {from_currency} → {to_currency} on {date_str}")

        # Make request with timeout
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Extract rate from response
        # Example response: {"amount":1.0,"base":"TRY","date":"2025-01-15","rates":{"EUR":0.028}}
        rate = data['rates'][to_currency]
        actual_date = datetime.strptime(data['date'], '%Y-%m-%d').date()

        logger.info(f"Exchange rate fetched: {from_currency} → {to_currency} = {rate} on {actual_date}")

        return {
            'success': True,
            'rate': Decimal(str(rate)),
            'date': actual_date,
            'source': 'frankfurter',
            'from_currency': from_currency,
            'to_currency': to_currency,
            'raw_response': data
        }

    def _get_fallback_rate(
        self,
        from_currency: str,
        to_currency: str
    ) -> Optional[Dict]:
        """
        Get a recent cached rate as fallback.

        Looks for rates from the last 30 days.
        """
        today = date.today()

        # Check last 30 days
        for days_ago in range(1, 31):
            check_date = today - timedelta(days=days_ago)
            cache_key = f"{from_currency}_{to_currency}_{check_date}"

            if cache_key in self.cache:
                cached_data = self.cache[cache_key].copy()
                cached_data['source'] = 'cache_fallback'
                cached_data['original_date'] = cached_data['date']
                cached_data['requested_date'] = today
                return cached_data

        return None

    def _load_cache(self) -> Dict:
        """Load cached exchange rates from file."""
        if not CACHE_FILE.exists():
            return {}

        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)

            # Convert date strings back to date objects and Decimal
            converted_cache = {}
            for key, value in data.items():
                if 'date' in value and isinstance(value['date'], str):
                    value['date'] = datetime.strptime(value['date'], '%Y-%m-%d').date()
                if 'rate' in value:
                    value['rate'] = Decimal(str(value['rate']))
                converted_cache[key] = value

            logger.info(f"Loaded {len(converted_cache)} cached exchange rates")
            return converted_cache

        except Exception as e:
            logger.error(f"Failed to load exchange rate cache: {e}")
            return {}

    def _save_cache(self):
        """Save exchange rates cache to file."""
        try:
            # Ensure temp directory exists
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Convert date objects and Decimal to strings for JSON
            serializable_cache = {}
            for key, value in self.cache.items():
                serialized_value = value.copy()
                if 'date' in serialized_value and isinstance(serialized_value['date'], date):
                    serialized_value['date'] = serialized_value['date'].strftime('%Y-%m-%d')
                if 'rate' in serialized_value and isinstance(serialized_value['rate'], Decimal):
                    serialized_value['rate'] = float(serialized_value['rate'])
                # Remove non-serializable fields
                serialized_value.pop('raw_response', None)
                serializable_cache[key] = serialized_value

            with open(CACHE_FILE, 'w') as f:
                json.dump(serializable_cache, f, indent=2)

            logger.info(f"Saved {len(serializable_cache)} exchange rates to cache")

        except Exception as e:
            logger.error(f"Failed to save exchange rate cache: {e}")

    def clear_old_cache(self, days: int = None):
        """
        Clear cache entries older than specified days.

        Args:
            days: Number of days to keep (default: CACHE_DAYS)
        """
        if days is None:
            days = self.CACHE_DAYS

        cutoff_date = date.today() - timedelta(days=days)

        # Filter cache
        original_count = len(self.cache)
        self.cache = {
            key: value for key, value in self.cache.items()
            if value.get('date', date.today()) >= cutoff_date
        }

        removed_count = original_count - len(self.cache)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} old cache entries")
            self._save_cache()

    def convert_amount(
        self,
        amount: float,
        from_currency: str,
        to_currency: str = "EUR",
        rate_date: Optional[date] = None
    ) -> Dict:
        """
        Convert an amount from one currency to another.

        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code
            rate_date: Date for exchange rate

        Returns:
            Dict with conversion details
        """
        rate_data = self.get_exchange_rate(from_currency, to_currency, rate_date)

        if not rate_data['success']:
            return rate_data

        converted_amount = Decimal(str(amount)) * rate_data['rate']

        return {
            'success': True,
            'original_amount': Decimal(str(amount)),
            'original_currency': from_currency,
            'converted_amount': converted_amount,
            'converted_currency': to_currency,
            'exchange_rate': rate_data['rate'],
            'exchange_rate_date': rate_data['date'],
            'source': rate_data['source']
        }


# Singleton instance
_exchange_rate_service = None

def get_exchange_rate_service() -> ExchangeRateService:
    """Get the singleton exchange rate service instance."""
    global _exchange_rate_service
    if _exchange_rate_service is None:
        _exchange_rate_service = ExchangeRateService()
    return _exchange_rate_service
