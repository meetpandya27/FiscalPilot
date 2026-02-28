"""
FiscalPilot Intelligence Analyzers — pure computation modules.

These are statistical and rule-based engines that run WITHOUT LLM calls,
producing structured results that agents can incorporate into their prompts.
"""

from fiscalpilot.analyzers.anomaly import AnomalyDetector
from fiscalpilot.analyzers.benchmarks import BenchmarkAnalyzer
from fiscalpilot.analyzers.benfords import BenfordsAnalyzer
from fiscalpilot.analyzers.breakeven import BreakevenCalculator, calculate_breakeven
from fiscalpilot.analyzers.cashflow import CashFlowForecaster
from fiscalpilot.analyzers.delivery_roi import DeliveryROIAnalyzer, analyze_delivery_roi

# Restaurant vertical analyzers
from fiscalpilot.analyzers.menu_engineering import MenuEngineeringAnalyzer
from fiscalpilot.analyzers.restaurant import RestaurantAnalyzer, analyze_restaurant
from fiscalpilot.analyzers.tax_optimizer import TaxOptimizer
from fiscalpilot.analyzers.tip_credit import TipCreditCalculator, calculate_tip_credit

# New competitor-inspired analyzers
from fiscalpilot.analyzers.chat import FinancialChatAssistant, ChatResponse, ask
from fiscalpilot.analyzers.invoice_processor import (
    InvoiceProcessor,
    ExtractedInvoice,
    process_invoice,
    process_invoice_folder,
)
from fiscalpilot.analyzers.auto_categorizer import (
    AutoCategorizer,
    CategoryRule,
    CategorizationResult,
    categorize,
    batch_categorize,
)
from fiscalpilot.analyzers.duplicate_detector import (
    DuplicateDetector,
    DuplicateMatch,
    DuplicateReport,
    find_duplicates,
    find_invoice_duplicates,
)
from fiscalpilot.analyzers.reconciliation import (
    BankReconciler,
    BankEntry,
    ReconciliationReport,
    reconcile_bank_statement,
)
from fiscalpilot.analyzers.policy_engine import (
    SpendPolicyEngine,
    SpendPolicy,
    PolicyCondition,
    PolicyEvaluationResult,
    evaluate_transaction,
    create_default_policy_engine,
)
from fiscalpilot.analyzers.budget import (
    BudgetManager,
    Budget,
    BudgetProgress,
    BudgetReport,
    BudgetPeriod,
    create_monthly_budget,
    check_budgets,
)
from fiscalpilot.analyzers.currency import (
    CurrencyConverter,
    Currency,
    ExchangeRate,
    ConversionResult,
    convert_amount,
    format_currency,
)

__all__ = [
    # Core analyzers
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
    # AI Chat Interface (Digits-inspired)
    "FinancialChatAssistant",
    "ChatResponse",
    "ask",
    # Invoice Processing (Vic.ai, Stampli-inspired)
    "InvoiceProcessor",
    "ExtractedInvoice",
    "process_invoice",
    "process_invoice_folder",
    # Auto-Categorization (Digits, Maybe Finance-inspired)
    "AutoCategorizer",
    "CategoryRule",
    "CategorizationResult",
    "categorize",
    "batch_categorize",
    # Duplicate Detection (Vic.ai-inspired)
    "DuplicateDetector",
    "DuplicateMatch",
    "DuplicateReport",
    "find_duplicates",
    "find_invoice_duplicates",
    # Bank Reconciliation (Akaunting-inspired)
    "BankReconciler",
    "BankEntry",
    "ReconciliationReport",
    "reconcile_bank_statement",
    # Spend Policy Engine (Ramp-inspired)
    "SpendPolicyEngine",
    "SpendPolicy",
    "PolicyCondition",
    "PolicyEvaluationResult",
    "evaluate_transaction",
    "create_default_policy_engine",
    # Budget Management (xtraCHEF, Firefly III-inspired)
    "BudgetManager",
    "Budget",
    "BudgetProgress",
    "BudgetReport",
    "BudgetPeriod",
    "create_monthly_budget",
    "check_budgets",
    # Multi-Currency Support (Akaunting-inspired)
    "CurrencyConverter",
    "Currency",
    "ExchangeRate",
    "ConversionResult",
    "convert_amount",
    "format_currency",
]
