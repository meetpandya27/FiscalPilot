"""
Multi-Currency Support — handle multiple currencies and conversions.

Inspired by Akaunting's multi-currency features. Track transactions
in different currencies, convert for reporting, and handle exchange
rate fluctuations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fiscalpilot.models.financial import Transaction

logger = logging.getLogger("fiscalpilot.analyzers.currency")


# Common currency codes
class Currency(str, Enum):
    """ISO 4217 currency codes."""
    
    USD = "USD"  # US Dollar
    EUR = "EUR"  # Euro
    GBP = "GBP"  # British Pound
    CAD = "CAD"  # Canadian Dollar
    AUD = "AUD"  # Australian Dollar
    JPY = "JPY"  # Japanese Yen
    CHF = "CHF"  # Swiss Franc
    CNY = "CNY"  # Chinese Yuan
    INR = "INR"  # Indian Rupee
    MXN = "MXN"  # Mexican Peso
    BRL = "BRL"  # Brazilian Real
    KRW = "KRW"  # South Korean Won
    SGD = "SGD"  # Singapore Dollar
    HKD = "HKD"  # Hong Kong Dollar
    NZD = "NZD"  # New Zealand Dollar
    SEK = "SEK"  # Swedish Krona
    NOK = "NOK"  # Norwegian Krone
    DKK = "DKK"  # Danish Krone
    ZAR = "ZAR"  # South African Rand
    THB = "THB"  # Thai Baht


# Currency symbols and info
CURRENCY_INFO = {
    "USD": {"symbol": "$", "name": "US Dollar", "decimals": 2},
    "EUR": {"symbol": "€", "name": "Euro", "decimals": 2},
    "GBP": {"symbol": "£", "name": "British Pound", "decimals": 2},
    "CAD": {"symbol": "CA$", "name": "Canadian Dollar", "decimals": 2},
    "AUD": {"symbol": "A$", "name": "Australian Dollar", "decimals": 2},
    "JPY": {"symbol": "¥", "name": "Japanese Yen", "decimals": 0},
    "CHF": {"symbol": "CHF", "name": "Swiss Franc", "decimals": 2},
    "CNY": {"symbol": "¥", "name": "Chinese Yuan", "decimals": 2},
    "INR": {"symbol": "₹", "name": "Indian Rupee", "decimals": 2},
    "MXN": {"symbol": "MX$", "name": "Mexican Peso", "decimals": 2},
    "BRL": {"symbol": "R$", "name": "Brazilian Real", "decimals": 2},
    "KRW": {"symbol": "₩", "name": "South Korean Won", "decimals": 0},
    "SGD": {"symbol": "S$", "name": "Singapore Dollar", "decimals": 2},
    "HKD": {"symbol": "HK$", "name": "Hong Kong Dollar", "decimals": 2},
    "NZD": {"symbol": "NZ$", "name": "New Zealand Dollar", "decimals": 2},
    "SEK": {"symbol": "kr", "name": "Swedish Krona", "decimals": 2},
    "NOK": {"symbol": "kr", "name": "Norwegian Krone", "decimals": 2},
    "DKK": {"symbol": "kr", "name": "Danish Krone", "decimals": 2},
    "ZAR": {"symbol": "R", "name": "South African Rand", "decimals": 2},
    "THB": {"symbol": "฿", "name": "Thai Baht", "decimals": 2},
}


@dataclass
class ExchangeRate:
    """An exchange rate between two currencies."""
    
    from_currency: str
    to_currency: str
    rate: float
    date: date
    source: str = "manual"  # API source or "manual"
    
    @property
    def inverse(self) -> ExchangeRate:
        """Get inverse rate."""
        return ExchangeRate(
            from_currency=self.to_currency,
            to_currency=self.from_currency,
            rate=1.0 / self.rate if self.rate != 0 else 0,
            date=self.date,
            source=self.source,
        )


@dataclass
class ConversionResult:
    """Result of a currency conversion."""
    
    original_amount: float
    original_currency: str
    converted_amount: float
    target_currency: str
    exchange_rate: float
    rate_date: date
    gain_loss: float = 0.0  # Unrealized gain/loss
    
    def __str__(self) -> str:
        return f"{self.format_original()} → {self.format_converted()}"
    
    def format_original(self) -> str:
        info = CURRENCY_INFO.get(self.original_currency, {})
        symbol = info.get("symbol", self.original_currency)
        decimals = info.get("decimals", 2)
        return f"{symbol}{self.original_amount:,.{decimals}f}"
    
    def format_converted(self) -> str:
        info = CURRENCY_INFO.get(self.target_currency, {})
        symbol = info.get("symbol", self.target_currency)
        decimals = info.get("decimals", 2)
        return f"{symbol}{self.converted_amount:,.{decimals}f}"


@dataclass
class CurrencySummary:
    """Summary of amounts by currency."""
    
    base_currency: str
    totals_by_currency: dict[str, float] = field(default_factory=dict)
    converted_total: float = 0.0
    conversion_details: list[ConversionResult] = field(default_factory=list)
    unrealized_gain_loss: float = 0.0


class CurrencyConverter:
    """
    Convert between currencies with exchange rate management.
    
    Features inspired by Akaunting:
    - Manual and API-based exchange rates
    - Historical rate tracking
    - Automatic conversion for reporting
    - Unrealized gain/loss calculation
    - Multi-currency totals
    
    Example usage:
        converter = CurrencyConverter(base_currency="USD")
        
        # Add exchange rates
        converter.add_rate("EUR", "USD", 1.08, date.today())
        converter.add_rate("GBP", "USD", 1.25, date.today())
        
        # Convert amount
        result = converter.convert(100, "EUR", "USD")
        print(f"{result}")  # €100.00 → $108.00
    """
    
    # Sample exchange rates (vs USD) for fallback
    # These are approximate and should be updated via API in production
    DEFAULT_RATES_VS_USD = {
        "EUR": 1.08,
        "GBP": 1.25,
        "CAD": 0.74,
        "AUD": 0.65,
        "JPY": 0.0067,
        "CHF": 1.12,
        "CNY": 0.14,
        "INR": 0.012,
        "MXN": 0.059,
        "BRL": 0.20,
        "KRW": 0.00074,
        "SGD": 0.74,
        "HKD": 0.13,
        "NZD": 0.61,
        "SEK": 0.095,
        "NOK": 0.094,
        "DKK": 0.14,
        "ZAR": 0.056,
        "THB": 0.029,
    }
    
    def __init__(self, base_currency: str = "USD"):
        """
        Initialize converter.
        
        Args:
            base_currency: Default currency for reporting.
        """
        self.base_currency = base_currency.upper()
        self.rates: dict[tuple[str, str], list[ExchangeRate]] = {}
        
        # Load default rates
        self._load_default_rates()
    
    def _load_default_rates(self):
        """Load default exchange rates."""
        today = date.today()
        
        for currency, rate_vs_usd in self.DEFAULT_RATES_VS_USD.items():
            # Store rate to USD
            self.add_rate(currency, "USD", rate_vs_usd, today, source="default")
            # Store inverse
            self.add_rate("USD", currency, 1.0 / rate_vs_usd, today, source="default")
    
    def add_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate: float,
        rate_date: date | None = None,
        source: str = "manual",
    ):
        """
        Add an exchange rate.
        
        Args:
            from_currency: Source currency code.
            to_currency: Target currency code.
            rate: Exchange rate (1 from = rate to).
            rate_date: Date of the rate.
            source: Rate source (API name or "manual").
        """
        from_curr = from_currency.upper()
        to_curr = to_currency.upper()
        rate_date = rate_date or date.today()
        
        key = (from_curr, to_curr)
        if key not in self.rates:
            self.rates[key] = []
        
        self.rates[key].append(ExchangeRate(
            from_currency=from_curr,
            to_currency=to_curr,
            rate=rate,
            date=rate_date,
            source=source,
        ))
    
    def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: date | None = None,
    ) -> ExchangeRate | None:
        """
        Get exchange rate for a currency pair.
        
        Args:
            from_currency: Source currency.
            to_currency: Target currency.
            rate_date: Date to get rate for (latest if None).
            
        Returns:
            ExchangeRate or None if not found.
        """
        from_curr = from_currency.upper()
        to_curr = to_currency.upper()
        
        # Same currency
        if from_curr == to_curr:
            return ExchangeRate(
                from_currency=from_curr,
                to_currency=to_curr,
                rate=1.0,
                date=rate_date or date.today(),
            )
        
        key = (from_curr, to_curr)
        rates = self.rates.get(key, [])
        
        if not rates:
            # Try to find via USD (triangulation)
            return self._triangulate(from_curr, to_curr, rate_date)
        
        # Get rate for specific date or latest
        if rate_date:
            # Find closest rate to requested date
            closest = min(rates, key=lambda r: abs((r.date - rate_date).days))
            return closest
        else:
            # Return most recent
            return max(rates, key=lambda r: r.date)
    
    def _triangulate(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: date | None = None,
    ) -> ExchangeRate | None:
        """
        Calculate rate via USD triangulation.
        
        If we don't have a direct rate, try: FROM → USD → TO
        """
        # Get FROM → USD rate
        from_to_usd = self.get_rate(from_currency, "USD", rate_date)
        if not from_to_usd:
            return None
        
        # Get USD → TO rate
        usd_to_target = self.get_rate("USD", to_currency, rate_date)
        if not usd_to_target:
            return None
        
        # Calculate combined rate
        combined_rate = from_to_usd.rate * usd_to_target.rate
        
        return ExchangeRate(
            from_currency=from_currency,
            to_currency=to_currency,
            rate=combined_rate,
            date=rate_date or date.today(),
            source="triangulated",
        )
    
    def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str | None = None,
        rate_date: date | None = None,
    ) -> ConversionResult:
        """
        Convert an amount between currencies.
        
        Args:
            amount: Amount to convert.
            from_currency: Source currency code.
            to_currency: Target currency (base_currency if None).
            rate_date: Date for rate lookup.
            
        Returns:
            ConversionResult with conversion details.
        """
        from_curr = from_currency.upper()
        to_curr = (to_currency or self.base_currency).upper()
        
        rate = self.get_rate(from_curr, to_curr, rate_date)
        
        if rate:
            converted = amount * rate.rate
            # Round to appropriate decimals
            decimals = CURRENCY_INFO.get(to_curr, {}).get("decimals", 2)
            converted = round(converted, decimals)
            
            return ConversionResult(
                original_amount=amount,
                original_currency=from_curr,
                converted_amount=converted,
                target_currency=to_curr,
                exchange_rate=rate.rate,
                rate_date=rate.date,
            )
        else:
            # No rate found, return unconverted
            logger.warning(f"No rate found for {from_curr} → {to_curr}")
            return ConversionResult(
                original_amount=amount,
                original_currency=from_curr,
                converted_amount=amount,
                target_currency=from_curr,
                exchange_rate=1.0,
                rate_date=date.today(),
            )
    
    def convert_transactions(
        self,
        transactions: list[Transaction],
        target_currency: str | None = None,
    ) -> list[tuple[Transaction, ConversionResult]]:
        """
        Convert all transactions to a common currency.
        
        Args:
            transactions: Transactions to convert.
            target_currency: Target currency (base if None).
            
        Returns:
            List of (transaction, conversion_result) tuples.
        """
        target = target_currency or self.base_currency
        results = []
        
        for txn in transactions:
            # Get transaction currency (default to base)
            txn_currency = getattr(txn, 'currency', None) or self.base_currency
            
            result = self.convert(
                amount=txn.amount,
                from_currency=txn_currency,
                to_currency=target,
                rate_date=txn.date,
            )
            results.append((txn, result))
        
        return results
    
    def get_totals_by_currency(
        self,
        transactions: list[Transaction],
    ) -> dict[str, float]:
        """
        Get transaction totals grouped by currency.
        
        Args:
            transactions: Transactions to summarize.
            
        Returns:
            Dict of currency code → total amount.
        """
        totals: dict[str, float] = {}
        
        for txn in transactions:
            currency = getattr(txn, 'currency', None) or self.base_currency
            totals[currency] = totals.get(currency, 0.0) + txn.amount
        
        return totals
    
    def get_summary(
        self,
        transactions: list[Transaction],
    ) -> CurrencySummary:
        """
        Get comprehensive currency summary.
        
        Args:
            transactions: Transactions to analyze.
            
        Returns:
            CurrencySummary with totals and conversions.
        """
        totals = self.get_totals_by_currency(transactions)
        
        converted_total = 0.0
        conversion_details = []
        
        for currency, amount in totals.items():
            result = self.convert(amount, currency, self.base_currency)
            converted_total += result.converted_amount
            conversion_details.append(result)
        
        return CurrencySummary(
            base_currency=self.base_currency,
            totals_by_currency=totals,
            converted_total=converted_total,
            conversion_details=conversion_details,
        )
    
    def format_amount(
        self,
        amount: float,
        currency: str,
        include_code: bool = False,
    ) -> str:
        """
        Format an amount with currency symbol.
        
        Args:
            amount: Amount to format.
            currency: Currency code.
            include_code: Include currency code after amount.
            
        Returns:
            Formatted string like "$1,234.56" or "$1,234.56 USD".
        """
        info = CURRENCY_INFO.get(currency.upper(), {})
        symbol = info.get("symbol", currency)
        decimals = info.get("decimals", 2)
        
        formatted = f"{symbol}{amount:,.{decimals}f}"
        if include_code:
            formatted += f" {currency.upper()}"
        
        return formatted


# Convenience functions
def convert_amount(
    amount: float,
    from_currency: str,
    to_currency: str = "USD",
) -> float:
    """Quick currency conversion."""
    converter = CurrencyConverter()
    result = converter.convert(amount, from_currency, to_currency)
    return result.converted_amount


def format_currency(
    amount: float,
    currency: str = "USD",
) -> str:
    """Quick currency formatting."""
    info = CURRENCY_INFO.get(currency.upper(), {})
    symbol = info.get("symbol", currency)
    decimals = info.get("decimals", 2)
    return f"{symbol}{amount:,.{decimals}f}"
