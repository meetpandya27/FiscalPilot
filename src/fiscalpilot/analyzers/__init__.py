"""
FiscalPilot Intelligence Analyzers — pure computation modules.

These are statistical and rule-based engines that run WITHOUT LLM calls,
producing structured results that agents can incorporate into their prompts.
"""

from fiscalpilot.analyzers.benfords import BenfordsAnalyzer
from fiscalpilot.analyzers.anomaly import AnomalyDetector
from fiscalpilot.analyzers.benchmarks import BenchmarkAnalyzer
from fiscalpilot.analyzers.cashflow import CashFlowForecaster
from fiscalpilot.analyzers.tax_optimizer import TaxOptimizer
from fiscalpilot.analyzers.restaurant import RestaurantAnalyzer, analyze_restaurant

__all__ = [
    "BenfordsAnalyzer",
    "AnomalyDetector",
    "BenchmarkAnalyzer",
    "CashFlowForecaster",
    "TaxOptimizer",
    "RestaurantAnalyzer",
    "analyze_restaurant",
]

