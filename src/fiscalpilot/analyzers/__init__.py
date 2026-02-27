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

# Restaurant vertical analyzers
from fiscalpilot.analyzers.menu_engineering import MenuEngineeringAnalyzer
from fiscalpilot.analyzers.breakeven import BreakevenCalculator, calculate_breakeven
from fiscalpilot.analyzers.tip_credit import TipCreditCalculator, calculate_tip_credit
from fiscalpilot.analyzers.delivery_roi import DeliveryROIAnalyzer, analyze_delivery_roi

__all__ = [
    "BenfordsAnalyzer",
    "AnomalyDetector",
    "BenchmarkAnalyzer",
    "CashFlowForecaster",
    "TaxOptimizer",
    "RestaurantAnalyzer",
    "analyze_restaurant",
    # Restaurant vertical
    "MenuEngineeringAnalyzer",
    "BreakevenCalculator",
    "calculate_breakeven",
    "TipCreditCalculator",
    "calculate_tip_credit",
    "DeliveryROIAnalyzer",
    "analyze_delivery_roi",
]

