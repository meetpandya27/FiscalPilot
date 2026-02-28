"""
Auto-Categorization Engine — intelligently categorize transactions.

Inspired by Digits' AI categorization and Maybe Finance's rule-based
categorization. Uses multiple strategies:
1. Rule-based matching (keywords, vendors, patterns)
2. ML-based prediction (when trained model available)
3. Historical pattern matching (learn from user corrections)
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from fiscalpilot.models.financial import ExpenseCategory, Transaction

logger = logging.getLogger("fiscalpilot.analyzers.auto_categorizer")


class CategorizationStrategy(str, Enum):
    """Strategy used for categorization."""
    
    RULE_BASED = "rule_based"
    VENDOR_MATCH = "vendor_match"
    ML_PREDICTION = "ml_prediction"
    HISTORICAL = "historical"
    MANUAL = "manual"
    UNKNOWN = "unknown"


@dataclass
class CategoryRule:
    """A rule for categorizing transactions."""
    
    name: str
    category: str
    patterns: list[str] = field(default_factory=list)
    vendors: list[str] = field(default_factory=list)
    amount_range: tuple[float | None, float | None] = (None, None)
    priority: int = 0
    
    def matches(self, transaction: Transaction) -> bool:
        """Check if this rule matches a transaction."""
        # Check vendor match
        vendor = transaction.vendor or ""
        if self.vendors:
            vendor_match = any(
                v.lower() in vendor.lower() 
                for v in self.vendors
            )
            if vendor_match:
                return True
        
        # Check description patterns
        description = transaction.description or ""
        if self.patterns:
            pattern_match = any(
                re.search(p, description, re.IGNORECASE)
                for p in self.patterns
            )
            if pattern_match:
                return True
        
        # Check amount range
        if self.amount_range[0] is not None and transaction.amount < self.amount_range[0]:
            return False
        if self.amount_range[1] is not None and transaction.amount > self.amount_range[1]:
            return False
        
        return False


@dataclass
class CategorizationResult:
    """Result of auto-categorization."""
    
    category: str
    confidence: float
    strategy: CategorizationStrategy
    rule_name: str | None = None
    alternatives: list[tuple[str, float]] = field(default_factory=list)


class AutoCategorizer:
    """
    Automatically categorize financial transactions.
    
    Features like Digits and Maybe Finance:
    - Multi-strategy categorization (rules, ML, historical)
    - Learns from user corrections over time
    - High confidence for known vendors
    - Suggests alternatives for low-confidence matches
    
    Example usage:
        categorizer = AutoCategorizer()
        result = categorizer.categorize(transaction)
        print(f"Category: {result.category} (confidence: {result.confidence:.0%})")
    """
    
    # Default categorization rules
    DEFAULT_RULES = [
        # Payroll & HR
        CategoryRule(
            name="payroll_services",
            category="payroll",
            vendors=["ADP", "Gusto", "Paychex", "Paylocity", "Rippling", "Zenefits"],
            patterns=[r"payroll", r"salary", r"wages"],
        ),
        
        # Software & SaaS
        CategoryRule(
            name="software_cloud",
            category="software",
            vendors=[
                "AWS", "Amazon Web Services", "Microsoft Azure", "Google Cloud", 
                "Salesforce", "HubSpot", "Slack", "Zoom", "Dropbox", "GitHub",
                "Atlassian", "Jira", "Confluence", "Adobe", "Canva", "Notion"
            ],
            patterns=[r"subscription", r"saas", r"software", r"cloud", r"\.io\b", r"\.com\b"],
        ),
        
        # Office & Supplies
        CategoryRule(
            name="office_supplies",
            category="office_supplies",
            vendors=["Staples", "Office Depot", "OfficeMax", "Amazon", "Uline"],
            patterns=[r"office", r"supplies", r"paper", r"printer", r"ink", r"toner"],
        ),
        
        # Marketing & Advertising
        CategoryRule(
            name="marketing_ads",
            category="marketing",
            vendors=[
                "Google Ads", "Facebook", "Meta", "LinkedIn", "Twitter", "X Corp",
                "Mailchimp", "Constant Contact", "SEMrush", "Ahrefs"
            ],
            patterns=[r"advertis", r"marketing", r"campaign", r"promo", r"sponsor"],
        ),
        
        # Travel & Transportation
        CategoryRule(
            name="travel_expenses",
            category="travel",
            vendors=[
                "Delta", "United", "American Airlines", "Southwest", "JetBlue",
                "Uber", "Lyft", "Hertz", "Avis", "Enterprise", "Marriott", 
                "Hilton", "Hyatt", "Airbnb", "Expedia", "Hotels.com"
            ],
            patterns=[r"flight", r"hotel", r"rental car", r"uber", r"lyft", r"airline", r"travel"],
        ),
        
        # Food & Meals (business)
        CategoryRule(
            name="business_meals",
            category="meals",
            vendors=[
                "DoorDash", "Grubhub", "UberEats", "Postmates", "Caviar",
                "Starbucks", "Dunkin", "McDonald's", "Chipotle", "Subway"
            ],
            patterns=[r"restaurant", r"cafe", r"coffee", r"lunch", r"dinner", r"breakfast", r"meal"],
        ),
        
        # Utilities
        CategoryRule(
            name="utilities",
            category="utilities",
            vendors=["PG&E", "ConEd", "Duke Energy", "Comcast", "Verizon", "AT&T", "T-Mobile", "Sprint"],
            patterns=[r"electric", r"gas", r"water", r"internet", r"phone", r"utility"],
        ),
        
        # Professional Services
        CategoryRule(
            name="professional_services",
            category="professional_services",
            patterns=[r"consulting", r"legal", r"attorney", r"accountant", r"cpa", r"lawyer"],
        ),
        
        # Insurance
        CategoryRule(
            name="insurance",
            category="insurance",
            vendors=["State Farm", "Geico", "Progressive", "Allstate", "Liberty Mutual"],
            patterns=[r"insurance", r"premium", r"coverage"],
        ),
        
        # Banking & Fees
        CategoryRule(
            name="bank_fees",
            category="bank_fees",
            patterns=[r"bank fee", r"service charge", r"overdraft", r"wire fee", r"ach fee"],
        ),
        
        # Rent & Lease
        CategoryRule(
            name="rent",
            category="rent",
            patterns=[r"\brent\b", r"lease", r"office space", r"property"],
        ),
        
        # Equipment
        CategoryRule(
            name="equipment",
            category="equipment",
            vendors=["Apple", "Dell", "HP", "Lenovo", "Best Buy", "B&H Photo"],
            patterns=[r"computer", r"laptop", r"monitor", r"equipment", r"hardware"],
        ),
        
        # Restaurant-specific
        CategoryRule(
            name="food_inventory",
            category="inventory",
            vendors=[
                "Sysco", "US Foods", "Restaurant Depot", "Gordon Food Service",
                "Performance Food", "McLane"
            ],
            patterns=[r"food\s*(?:cost|inventory|supply)", r"produce", r"meat", r"dairy"],
        ),
        
        CategoryRule(
            name="beverage_inventory",
            category="inventory",
            vendors=["Southern Glazers", "Republic National", "Breakthru Beverage"],
            patterns=[r"beverage", r"liquor", r"beer", r"wine", r"alcohol"],
        ),
    ]
    
    def __init__(self, rules: list[CategoryRule] | None = None):
        """Initialize categorizer with custom or default rules."""
        self.rules = rules or self.DEFAULT_RULES.copy()
        self.vendor_history: dict[str, Counter] = {}  # vendor -> category counts
        self.user_corrections: list[dict] = []
        
    def categorize(self, transaction: Transaction) -> CategorizationResult:
        """
        Categorize a single transaction.
        
        Args:
            transaction: Transaction to categorize.
            
        Returns:
            CategorizationResult with category and confidence.
        """
        # If already categorized manually, return as-is
        if transaction.category:
            return CategorizationResult(
                category=transaction.category.value,
                confidence=1.0,
                strategy=CategorizationStrategy.MANUAL,
            )
        
        # Try rule-based matching first
        rule_result = self._match_rules(transaction)
        if rule_result and rule_result.confidence > 0.7:
            return rule_result
        
        # Try historical vendor matching
        vendor_result = self._match_vendor_history(transaction)
        if vendor_result and vendor_result.confidence > 0.8:
            return vendor_result
        
        # Return best result or unknown
        if rule_result:
            return rule_result
        if vendor_result:
            return vendor_result
        
        return CategorizationResult(
            category="uncategorized",
            confidence=0.0,
            strategy=CategorizationStrategy.UNKNOWN,
        )
    
    def _match_rules(self, transaction: Transaction) -> CategorizationResult | None:
        """Match transaction against rules."""
        matches: list[tuple[CategoryRule, float]] = []
        
        for rule in sorted(self.rules, key=lambda r: r.priority, reverse=True):
            if rule.matches(transaction):
                # Calculate confidence based on match type
                confidence = 0.8
                
                # Higher confidence for vendor matches
                vendor = transaction.vendor or ""
                if rule.vendors and any(v.lower() in vendor.lower() for v in rule.vendors):
                    confidence = 0.95
                
                matches.append((rule, confidence))
        
        if not matches:
            return None
        
        # Return best match
        best_rule, best_confidence = max(matches, key=lambda x: x[1])
        
        alternatives = [
            (r.category, c) 
            for r, c in matches 
            if r.category != best_rule.category
        ][:3]
        
        return CategorizationResult(
            category=best_rule.category,
            confidence=best_confidence,
            strategy=CategorizationStrategy.RULE_BASED,
            rule_name=best_rule.name,
            alternatives=alternatives,
        )
    
    def _match_vendor_history(self, transaction: Transaction) -> CategorizationResult | None:
        """Match based on historical vendor categorization."""
        vendor = transaction.vendor
        if not vendor or vendor not in self.vendor_history:
            return None
        
        category_counts = self.vendor_history[vendor]
        if not category_counts:
            return None
        
        # Get most common category for this vendor
        most_common = category_counts.most_common(1)[0]
        category, count = most_common
        total = sum(category_counts.values())
        confidence = count / total
        
        alternatives = [
            (cat, cnt / total) 
            for cat, cnt in category_counts.most_common(4)[1:]
        ]
        
        return CategorizationResult(
            category=category,
            confidence=confidence,
            strategy=CategorizationStrategy.HISTORICAL,
            alternatives=alternatives,
        )
    
    def learn_from_correction(
        self,
        transaction: Transaction,
        correct_category: str,
        original_category: str | None = None,
    ):
        """
        Learn from a user correction to improve future categorization.
        
        Args:
            transaction: The transaction that was corrected.
            correct_category: The correct category.
            original_category: What the system originally predicted.
        """
        vendor = transaction.vendor
        if vendor:
            if vendor not in self.vendor_history:
                self.vendor_history[vendor] = Counter()
            self.vendor_history[vendor][correct_category] += 1
        
        self.user_corrections.append({
            "description": transaction.description,
            "vendor": vendor,
            "amount": transaction.amount,
            "original": original_category,
            "correct": correct_category,
        })
        
        logger.info(f"Learned: {vendor or 'Unknown'} -> {correct_category}")
    
    def batch_categorize(
        self,
        transactions: list[Transaction],
        auto_apply: bool = False,
    ) -> list[tuple[Transaction, CategorizationResult]]:
        """
        Categorize multiple transactions.
        
        Args:
            transactions: List of transactions to categorize.
            auto_apply: If True, automatically apply categories to transactions.
            
        Returns:
            List of (transaction, result) tuples.
        """
        results = []
        for txn in transactions:
            result = self.categorize(txn)
            if auto_apply and result.confidence > 0.8:
                self._apply_category(txn, result.category)
            results.append((txn, result))
        
        return results
    
    def _apply_category(self, transaction: Transaction, category: str):
        """Apply a category to a transaction (import ExpenseCategory at runtime)."""
        try:
            from fiscalpilot.models.financial import ExpenseCategory
            try:
                transaction.category = ExpenseCategory(category)
            except ValueError:
                # Category not in enum, leave as-is
                pass
        except ImportError:
            pass
    
    def add_rule(self, rule: CategoryRule):
        """Add a new categorization rule."""
        self.rules.append(rule)
    
    def remove_rule(self, rule_name: str) -> bool:
        """Remove a rule by name."""
        before_count = len(self.rules)
        self.rules = [r for r in self.rules if r.name != rule_name]
        return len(self.rules) < before_count
    
    def get_uncategorized(
        self,
        transactions: list[Transaction],
    ) -> list[Transaction]:
        """Get transactions that couldn't be categorized."""
        uncategorized = []
        for txn in transactions:
            if not txn.category:
                result = self.categorize(txn)
                if result.confidence < 0.7:
                    uncategorized.append(txn)
        return uncategorized
    
    def get_category_stats(
        self,
        transactions: list[Transaction],
    ) -> dict[str, dict[str, Any]]:
        """Get categorization statistics."""
        stats = {
            "total": len(transactions),
            "by_strategy": Counter(),
            "by_category": Counter(),
            "confidence_avg": 0.0,
            "uncategorized": 0,
        }
        
        confidences = []
        for txn in transactions:
            result = self.categorize(txn)
            stats["by_strategy"][result.strategy.value] += 1
            stats["by_category"][result.category] += 1
            confidences.append(result.confidence)
            if result.category == "uncategorized":
                stats["uncategorized"] += 1
        
        if confidences:
            stats["confidence_avg"] = sum(confidences) / len(confidences)
        
        return stats


# Convenience functions
def categorize(transaction: Transaction) -> CategorizationResult:
    """Quick categorization for a single transaction."""
    categorizer = AutoCategorizer()
    return categorizer.categorize(transaction)


def batch_categorize(
    transactions: list[Transaction],
    auto_apply: bool = False,
) -> list[tuple[Transaction, CategorizationResult]]:
    """Quick batch categorization."""
    categorizer = AutoCategorizer()
    return categorizer.batch_categorize(transactions, auto_apply)
