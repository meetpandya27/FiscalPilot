"""Tests for the Multi-Currency Support module."""

import pytest
from datetime import date
from fiscalpilot.analyzers.currency import (
    CurrencyConverter,
    Currency,
    ExchangeRate,
    ConversionResult,
    CURRENCY_INFO,
    convert_amount,
    format_currency,
)
from fiscalpilot.models.financial import Transaction, TransactionType


class TestCurrencyInfo:
    """Test currency info constants."""
    
    def test_usd_info(self):
        """Test USD currency info."""
        assert "USD" in CURRENCY_INFO
        assert CURRENCY_INFO["USD"]["symbol"] == "$"
        assert CURRENCY_INFO["USD"]["decimals"] == 2
    
    def test_eur_info(self):
        """Test EUR currency info."""
        assert "EUR" in CURRENCY_INFO
        assert CURRENCY_INFO["EUR"]["symbol"] == "€"
    
    def test_jpy_zero_decimals(self):
        """Test JPY has 0 decimals."""
        assert CURRENCY_INFO["JPY"]["decimals"] == 0


class TestExchangeRate:
    """Test ExchangeRate class."""
    
    def test_creation(self):
        """Test basic rate creation."""
        rate = ExchangeRate(
            from_currency="EUR",
            to_currency="USD",
            rate=1.08,
            date=date(2025, 1, 15),
        )
        assert rate.from_currency == "EUR"
        assert rate.to_currency == "USD"
        assert rate.rate == 1.08
    
    def test_inverse_rate(self):
        """Test inverse rate calculation."""
        rate = ExchangeRate(
            from_currency="EUR",
            to_currency="USD",
            rate=1.08,
            date=date(2025, 1, 15),
        )
        
        inverse = rate.inverse
        assert inverse.from_currency == "USD"
        assert inverse.to_currency == "EUR"
        assert abs(inverse.rate - (1 / 1.08)) < 0.0001


class TestConversionResult:
    """Test ConversionResult class."""
    
    def test_creation(self):
        """Test result creation."""
        result = ConversionResult(
            original_amount=100.0,
            original_currency="EUR",
            converted_amount=108.0,
            target_currency="USD",
            exchange_rate=1.08,
            rate_date=date(2025, 1, 15),
        )
        assert result.original_amount == 100.0
        assert result.converted_amount == 108.0
    
    def test_string_representation(self):
        """Test string formatting."""
        result = ConversionResult(
            original_amount=100.0,
            original_currency="EUR",
            converted_amount=108.0,
            target_currency="USD",
            exchange_rate=1.08,
            rate_date=date(2025, 1, 15),
        )
        
        str_result = str(result)
        assert "€100.00" in str_result
        assert "$108.00" in str_result


class TestCurrencyConverter:
    """Test CurrencyConverter class."""
    
    def test_init_default_base(self):
        """Test default base currency is USD."""
        converter = CurrencyConverter()
        assert converter.base_currency == "USD"
    
    def test_init_custom_base(self):
        """Test custom base currency."""
        converter = CurrencyConverter(base_currency="EUR")
        assert converter.base_currency == "EUR"
    
    def test_same_currency_conversion(self):
        """Test conversion of same currency."""
        converter = CurrencyConverter()
        result = converter.convert(100.0, "USD", "USD")
        
        assert result.converted_amount == 100.0
        assert result.exchange_rate == 1.0
    
    def test_eur_to_usd(self):
        """Test EUR to USD conversion."""
        converter = CurrencyConverter()
        converter.add_rate("EUR", "USD", 1.08, date(2025, 1, 15))
        
        result = converter.convert(100.0, "EUR", "USD")
        
        assert result.converted_amount == 108.0
        assert result.exchange_rate == 1.08
    
    def test_usd_to_eur(self):
        """Test USD to EUR conversion (inverse)."""
        converter = CurrencyConverter()
        converter.add_rate("USD", "EUR", 0.926, date(2025, 1, 15))  # ~1/1.08
        
        result = converter.convert(100.0, "USD", "EUR")
        
        assert abs(result.converted_amount - 92.6) < 0.1
    
    def test_triangulation(self):
        """Test rate triangulation via USD."""
        converter = CurrencyConverter()
        
        # Only have EUR-USD and GBP-USD rates
        converter.add_rate("EUR", "USD", 1.08, date(2025, 1, 15))
        converter.add_rate("GBP", "USD", 1.25, date(2025, 1, 15))
        converter.add_rate("USD", "EUR", 1/1.08, date(2025, 1, 15))
        converter.add_rate("USD", "GBP", 1/1.25, date(2025, 1, 15))
        
        # Should calculate GBP to EUR via USD
        result = converter.convert(100.0, "GBP", "EUR")
        
        # GBP -> USD -> EUR: 100 * 1.25 * (1/1.08) = ~115.74
        assert result.converted_amount > 0
    
    def test_add_rate(self):
        """Test adding exchange rates."""
        converter = CurrencyConverter()
        converter.add_rate("EUR", "USD", 1.10, date(2025, 1, 20))
        
        rate = converter.get_rate("EUR", "USD", date(2025, 1, 20))
        assert rate is not None
        assert rate.rate == 1.10
    
    def test_historical_rate(self):
        """Test getting historical rate."""
        converter = CurrencyConverter()
        
        # Add rates for different dates
        converter.add_rate("EUR", "USD", 1.05, date(2025, 1, 1))
        converter.add_rate("EUR", "USD", 1.08, date(2025, 1, 15))
        converter.add_rate("EUR", "USD", 1.10, date(2025, 1, 30))
        
        # Get rate closest to Jan 10
        rate = converter.get_rate("EUR", "USD", date(2025, 1, 10))
        assert rate is not None
        # Should be closest to Jan 1 rate
    
    def test_format_amount(self):
        """Test amount formatting."""
        converter = CurrencyConverter()
        
        # USD formatting
        formatted = converter.format_amount(1234.56, "USD")
        assert "$1,234.56" in formatted
        
        # EUR formatting
        formatted = converter.format_amount(1234.56, "EUR")
        assert "€1,234.56" in formatted
        
        # JPY (no decimals)
        formatted = converter.format_amount(1234.0, "JPY")
        assert "¥1,234" in formatted
    
    def test_format_with_code(self):
        """Test formatting with currency code."""
        converter = CurrencyConverter()
        
        formatted = converter.format_amount(100.0, "USD", include_code=True)
        assert "USD" in formatted
    
    def test_get_totals_by_currency(self):
        """Test totaling transactions by currency."""
        converter = CurrencyConverter()
        
        transactions = [
            Transaction(
                date=date(2025, 1, 15),
                amount=-100.0,
                description="USD payment",
                type=TransactionType.EXPENSE,
            ),
            Transaction(
                date=date(2025, 1, 16),
                amount=-200.0,
                description="Another USD",
                type=TransactionType.EXPENSE,
            ),
        ]
        
        # Without currency attribute, should default to base
        totals = converter.get_totals_by_currency(transactions)
        assert totals.get("USD") == -300.0
    
    def test_get_summary(self):
        """Test currency summary generation."""
        converter = CurrencyConverter()
        
        transactions = [
            Transaction(
                date=date(2025, 1, 15),
                amount=-100.0,
                description="Payment",
                type=TransactionType.EXPENSE,
            ),
        ]
        
        summary = converter.get_summary(transactions)
        
        assert summary.base_currency == "USD"
        assert len(summary.totals_by_currency) > 0


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_convert_amount(self):
        """Test convert_amount function."""
        # Same currency should return same amount
        result = convert_amount(100.0, "USD", "USD")
        assert result == 100.0
    
    def test_format_currency(self):
        """Test format_currency function."""
        formatted = format_currency(1234.56, "USD")
        assert "$1,234.56" == formatted
        
        formatted = format_currency(1234.56, "EUR")
        assert "€1,234.56" == formatted
