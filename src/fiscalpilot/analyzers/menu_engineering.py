"""
Menu Engineering Analyzer — profitability and popularity analysis for restaurant menus.

Implements the classic Boston Consulting Group matrix adapted for restaurants:
- Stars: High profit margin, high popularity → Keep & promote
- Plowhorses: Low profit margin, high popularity → Increase price or reduce cost
- Puzzles: High profit margin, low popularity → Reposition, rename, promote
- Dogs: Low profit margin, low popularity → Remove from menu

This analysis helps restaurant owners optimize their menu for maximum profitability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("fiscalpilot.analyzers.menu_engineering")


class MenuItemCategory(str, Enum):
    """Menu item classification based on BCG matrix."""

    STAR = "star"  # High margin, high popularity
    PLOWHORSE = "plowhorse"  # Low margin, high popularity
    PUZZLE = "puzzle"  # High margin, low popularity
    DOG = "dog"  # Low margin, low popularity


@dataclass
class MenuItemData:
    """Input data for a menu item (before analysis)."""

    name: str
    menu_price: float
    food_cost: float
    quantity_sold: int
    category: str = "Main"


@dataclass
class MenuItem:
    """A single menu item with sales and cost data."""

    name: str
    category: str  # e.g., "Appetizers", "Entrees", "Desserts"
    menu_price: float
    food_cost: float
    quantity_sold: int

    # Calculated fields
    contribution_margin: float = 0.0
    food_cost_pct: float = 0.0
    total_revenue: float = 0.0
    total_cost: float = 0.0
    total_profit: float = 0.0
    popularity_index: float = 0.0
    profitability_index: float = 0.0
    classification: MenuItemCategory = MenuItemCategory.DOG
    recommendation: str = ""

    def __post_init__(self):
        """Calculate derived metrics."""
        self.contribution_margin = self.menu_price - self.food_cost
        self.food_cost_pct = (self.food_cost / self.menu_price * 100) if self.menu_price > 0 else 0
        self.total_revenue = self.menu_price * self.quantity_sold
        self.total_cost = self.food_cost * self.quantity_sold
        self.total_profit = self.contribution_margin * self.quantity_sold


@dataclass
class MenuCategory:
    """Analysis results for a menu category (e.g., Appetizers)."""

    name: str
    items: list[MenuItem] = field(default_factory=list)
    total_revenue: float = 0.0
    total_cost: float = 0.0
    total_profit: float = 0.0
    avg_contribution_margin: float = 0.0
    avg_food_cost_pct: float = 0.0
    total_quantity_sold: int = 0

    # Classification counts
    stars: int = 0
    plowhorses: int = 0
    puzzles: int = 0
    dogs: int = 0

    @property
    def item_count(self) -> int:
        """Number of items in this category."""
        return len(self.items)


@dataclass
class MenuEngineeringResult:
    """Complete menu engineering analysis results."""

    # All items with classifications
    items: list[MenuItem] = field(default_factory=list)

    # Overall metrics
    total_menu_items: int = 0
    total_revenue: float = 0.0
    total_food_cost: float = 0.0
    total_profit: float = 0.0
    total_contribution: float = 0.0  # Alias for total_profit
    overall_food_cost_pct: float = 0.0
    avg_contribution_margin: float = 0.0

    # Category breakdowns
    categories: list[MenuCategory] = field(default_factory=list)

    # Classified items (sublists for convenience)
    stars: list[MenuItem] = field(default_factory=list)
    plowhorses: list[MenuItem] = field(default_factory=list)
    puzzles: list[MenuItem] = field(default_factory=list)
    dogs: list[MenuItem] = field(default_factory=list)

    # Classification counts
    star_count: int = 0
    plowhorse_count: int = 0
    puzzle_count: int = 0
    dog_count: int = 0

    # Strategic recommendations
    recommendations: list[str] = field(default_factory=list)

    # Insights (human-readable)
    insights: list[str] = field(default_factory=list)

    # Potential savings/gains
    potential_profit_increase: float = 0.0
    explanation: str = ""

    @property
    def total_items(self) -> int:
        """Alias for total_menu_items."""
        return self.total_menu_items


class MenuEngineeringAnalyzer:
    """Analyze menu items for profitability and popularity."""

    # Thresholds for classification
    DEFAULT_POPULARITY_THRESHOLD = 0.70  # Top 70% are "popular"
    DEFAULT_PROFITABILITY_THRESHOLD = 0.70  # Top 70% are "profitable"

    @classmethod
    def analyze(
        cls,
        items: list[MenuItemData | dict[str, Any]],
        *,
        popularity_threshold: float = DEFAULT_POPULARITY_THRESHOLD,
        profitability_threshold: float = DEFAULT_PROFITABILITY_THRESHOLD,
    ) -> MenuEngineeringResult:
        """
        Analyze menu items and classify them.

        Args:
            items: List of menu items as MenuItemData or dicts with keys:
                - name: str
                - category: str (e.g., "Appetizers")
                - menu_price: float
                - food_cost: float
                - quantity_sold: int
            popularity_threshold: Percentile cutoff for "popular" (default 0.70)
            profitability_threshold: Percentile cutoff for "profitable" (default 0.70)

        Returns:
            MenuEngineeringResult with classifications and recommendations.
        """
        if not items:
            return MenuEngineeringResult(explanation="No menu items provided for analysis.")

        # Convert to MenuItem objects (handle both MenuItemData and dict)
        menu_items = []
        for item in items:
            if isinstance(item, MenuItemData):
                menu_items.append(
                    MenuItem(
                        name=item.name,
                        category=item.category,
                        menu_price=float(item.menu_price),
                        food_cost=float(item.food_cost),
                        quantity_sold=int(item.quantity_sold),
                    )
                )
            else:
                menu_items.append(
                    MenuItem(
                        name=item.get("name", "Unknown"),
                        category=item.get("category", "Uncategorized"),
                        menu_price=float(item.get("menu_price", 0)),
                        food_cost=float(item.get("food_cost", 0)),
                        quantity_sold=int(item.get("quantity_sold", 0)),
                    )
                )

        # Calculate totals for normalization
        total_quantity = sum(m.quantity_sold for m in menu_items)
        total_profit = sum(m.total_profit for m in menu_items)

        if total_quantity == 0:
            return MenuEngineeringResult(
                total_menu_items=len(menu_items), explanation="No sales data available for analysis."
            )

        # Calculate average contribution margin
        avg_cm = total_profit / total_quantity if total_quantity > 0 else 0

        # Calculate popularity and profitability indices
        for item in menu_items:
            # Popularity = item's share of total sales
            item.popularity_index = item.quantity_sold / total_quantity if total_quantity > 0 else 0
            # Profitability = CM compared to average CM
            item.profitability_index = item.contribution_margin / avg_cm if avg_cm > 0 else 0

        # Determine thresholds based on percentiles
        popularity_cutoff = cls._calculate_percentile_cutoff(
            [m.quantity_sold for m in menu_items], 1 - popularity_threshold
        )
        profitability_cutoff = avg_cm  # Items above average CM are "profitable"

        # Alternative: use contribution margin percentage threshold
        # profitability_cutoff = cls._calculate_percentile_cutoff(
        #     [m.contribution_margin for m in menu_items],
        #     1 - profitability_threshold
        # )

        # Classify each item
        stars, plowhorses, puzzles, dogs = [], [], [], []

        for item in menu_items:
            is_popular = item.quantity_sold >= popularity_cutoff
            is_profitable = item.contribution_margin >= profitability_cutoff

            if is_popular and is_profitable:
                item.classification = MenuItemCategory.STAR
                stars.append(item)
            elif is_popular and not is_profitable:
                item.classification = MenuItemCategory.PLOWHORSE
                plowhorses.append(item)
            elif not is_popular and is_profitable:
                item.classification = MenuItemCategory.PUZZLE
                puzzles.append(item)
            else:
                item.classification = MenuItemCategory.DOG
                dogs.append(item)

        # Sort by profit potential
        stars.sort(key=lambda x: x.total_profit, reverse=True)
        plowhorses.sort(key=lambda x: x.quantity_sold, reverse=True)
        puzzles.sort(key=lambda x: x.contribution_margin, reverse=True)
        dogs.sort(key=lambda x: x.total_profit)

        # Calculate category breakdowns
        categories = cls._build_category_summaries(menu_items)

        # Generate recommendations
        recommendations = cls._generate_recommendations(stars, plowhorses, puzzles, dogs)

        # Calculate potential profit increase
        potential_increase = cls._calculate_potential_increase(plowhorses, puzzles, dogs, avg_cm)

        # Calculate overall metrics
        total_revenue = sum(m.total_revenue for m in menu_items)
        total_food_cost = sum(m.total_cost for m in menu_items)
        overall_food_cost_pct = (total_food_cost / total_revenue * 100) if total_revenue > 0 else 0

        # Generate item-level recommendations
        cls._add_item_recommendations(stars, plowhorses, puzzles, dogs)

        # Generate insights
        insights = cls._generate_insights(stars, plowhorses, puzzles, dogs, menu_items)

        return MenuEngineeringResult(
            items=menu_items,
            total_menu_items=len(menu_items),
            total_revenue=total_revenue,
            total_food_cost=total_food_cost,
            total_profit=total_profit,
            total_contribution=total_profit,  # Alias
            overall_food_cost_pct=overall_food_cost_pct,
            avg_contribution_margin=avg_cm,
            categories=categories,
            stars=stars,
            plowhorses=plowhorses,
            puzzles=puzzles,
            dogs=dogs,
            star_count=len(stars),
            plowhorse_count=len(plowhorses),
            puzzle_count=len(puzzles),
            dog_count=len(dogs),
            recommendations=recommendations,
            insights=insights,
            potential_profit_increase=potential_increase,
            explanation=cls._generate_summary(stars, plowhorses, puzzles, dogs),
        )

    @staticmethod
    def _calculate_percentile_cutoff(values: list[float], percentile: float) -> float:
        """Calculate the value at a given percentile."""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        index = max(0, min(index, len(sorted_values) - 1))
        return sorted_values[index]

    @classmethod
    def _build_category_summaries(cls, items: list[MenuItem]) -> list[MenuCategory]:
        """Build summaries by menu category."""
        category_map: dict[str, MenuCategory] = {}

        for item in items:
            cat_name = item.category
            if cat_name not in category_map:
                category_map[cat_name] = MenuCategory(name=cat_name)

            cat = category_map[cat_name]
            cat.items.append(item)
            cat.total_revenue += item.total_revenue
            cat.total_cost += item.total_cost
            cat.total_profit += item.total_profit
            cat.total_quantity_sold += item.quantity_sold

            # Count classifications
            if item.classification == MenuItemCategory.STAR:
                cat.stars += 1
            elif item.classification == MenuItemCategory.PLOWHORSE:
                cat.plowhorses += 1
            elif item.classification == MenuItemCategory.PUZZLE:
                cat.puzzles += 1
            else:
                cat.dogs += 1

        # Calculate averages
        for cat in category_map.values():
            if cat.items:
                cat.avg_contribution_margin = (
                    cat.total_profit / cat.total_quantity_sold if cat.total_quantity_sold > 0 else 0
                )
                cat.avg_food_cost_pct = (cat.total_cost / cat.total_revenue * 100) if cat.total_revenue > 0 else 0

        return sorted(category_map.values(), key=lambda x: x.total_revenue, reverse=True)

    @classmethod
    def _generate_recommendations(
        cls,
        stars: list[MenuItem],
        plowhorses: list[MenuItem],
        puzzles: list[MenuItem],
        dogs: list[MenuItem],
    ) -> list[str]:
        """Generate actionable recommendations."""
        recs: list[str] = []

        # Star recommendations
        if stars:
            top_star = stars[0]
            recs.append(
                f"⭐ PROMOTE YOUR STARS: '{top_star.name}' is your top performer "
                f"(${top_star.contribution_margin:.2f} margin, {top_star.quantity_sold} sold). "
                "Feature prominently on menu, train servers to recommend."
            )

        # Plowhorse recommendations
        if plowhorses:
            sum(p.quantity_sold for p in plowhorses)
            avg_plowhorse_margin = sum(p.contribution_margin for p in plowhorses) / len(plowhorses)
            target_margin = (
                sum(s.contribution_margin for s in stars) / len(stars) if stars else avg_plowhorse_margin * 1.3
            )

            for ph in plowhorses[:3]:  # Top 3 plowhorses
                margin_gap = target_margin - ph.contribution_margin
                potential_price_increase = margin_gap
                recs.append(
                    f"🐴 PLOWHORSE '{ph.name}': Sells well ({ph.quantity_sold} orders) but low margin "
                    f"(${ph.contribution_margin:.2f}). Consider: "
                    f"(1) Raise price by ${potential_price_increase:.2f}, "
                    f"(2) Reduce portion slightly, or "
                    f"(3) Source cheaper ingredients."
                )

        # Puzzle recommendations
        if puzzles:
            for pz in puzzles[:3]:  # Top 3 puzzles
                recs.append(
                    f"🧩 PUZZLE '{pz.name}': High margin (${pz.contribution_margin:.2f}) but low sales "
                    f"({pz.quantity_sold} orders). Try: "
                    "(1) Better menu placement, "
                    "(2) Server training to recommend, "
                    "(3) Rename/reposition to highlight appeal."
                )

        # Dog recommendations
        if dogs:
            sum(d.total_profit for d in dogs if d.total_profit < 0)
            dog_names = ", ".join(d.name for d in dogs[:5])
            recs.append(
                f"🐕 CONSIDER REMOVING DOGS: {len(dogs)} items have low profit and low popularity. "
                f"Top candidates for removal: {dog_names}. "
                "Removing simplifies operations and focuses kitchen on profitable items."
            )

        return recs

    @staticmethod
    def _calculate_potential_increase(
        plowhorses: list[MenuItem],
        puzzles: list[MenuItem],
        dogs: list[MenuItem],
        avg_cm: float,
    ) -> float:
        """Estimate potential annual profit increase from optimizations."""
        potential = 0.0

        # Plowhorses: If we raise margins to average
        for ph in plowhorses:
            margin_gap = max(0, avg_cm - ph.contribution_margin)
            potential += margin_gap * ph.quantity_sold * 0.5  # Conservative: 50% of potential

        # Puzzles: If we increase sales by 50%
        for pz in puzzles:
            additional_sales = pz.quantity_sold * 0.5
            potential += pz.contribution_margin * additional_sales * 0.5  # Conservative

        # Dogs: Savings from removal (reduced waste/complexity)
        for dog in dogs:
            if dog.total_profit < 0:
                potential += abs(dog.total_profit) * 0.3  # 30% of current loss recovered

        return potential

    @staticmethod
    def _generate_summary(
        stars: list[MenuItem],
        plowhorses: list[MenuItem],
        puzzles: list[MenuItem],
        dogs: list[MenuItem],
    ) -> str:
        """Generate executive summary."""
        total = len(stars) + len(plowhorses) + len(puzzles) + len(dogs)
        if total == 0:
            return "No items to analyze."

        star_pct = len(stars) / total * 100
        dog_pct = len(dogs) / total * 100

        summary_parts = [
            f"Menu Analysis: {total} items analyzed.",
            f"⭐ Stars: {len(stars)} ({star_pct:.0f}%) — your profit drivers.",
            f"🐴 Plowhorses: {len(plowhorses)} — popular but need margin improvement.",
            f"🧩 Puzzles: {len(puzzles)} — profitable but need promotion.",
            f"🐕 Dogs: {len(dogs)} ({dog_pct:.0f}%) — candidates for removal.",
        ]

        if dog_pct > 30:
            summary_parts.append(
                "⚠️ HIGH DOG RATIO: Over 30% of your menu is underperforming. Consider significant menu simplification."
            )

        if star_pct < 15:
            summary_parts.append(
                "⚠️ LOW STAR RATIO: Less than 15% of menu items are stars. "
                "Focus on developing new high-margin, high-popularity items."
            )

        return " ".join(summary_parts)

    @classmethod
    def _add_item_recommendations(
        cls,
        stars: list[MenuItem],
        plowhorses: list[MenuItem],
        puzzles: list[MenuItem],
        dogs: list[MenuItem],
    ) -> None:
        """Add individual recommendations to each menu item."""
        for item in stars:
            item.recommendation = (
                "Feature prominently on menu. Train servers to recommend. "
                "Consider premium positioning or signature dish status. Maintain quality."
            )

        for item in plowhorses:
            margin_gap = round(item.food_cost_pct - 30, 1)  # vs 30% target
            item.recommendation = (
                f"Popular but low margin ({item.food_cost_pct:.1f}% food cost). "
                f"Options: Raise price by ${margin_gap:.2f}, reduce portion by 10%, "
                "or source cheaper ingredients without affecting quality."
            )

        for item in puzzles:
            item.recommendation = (
                "High margin but low sales. Increase visibility: "
                "better menu placement, server upsell training, "
                "rename to be more appealing, or add appealing description."
            )

        for item in dogs:
            item.recommendation = (
                "Consider removing from menu. Low profit and low popularity. "
                "If keeping: raise price, reduce cost, or reposition entirely. "
                "Removal simplifies kitchen operations."
            )

    @classmethod
    def _generate_insights(
        cls,
        stars: list[MenuItem],
        plowhorses: list[MenuItem],
        puzzles: list[MenuItem],
        dogs: list[MenuItem],
        all_items: list[MenuItem],
    ) -> list[str]:
        """Generate high-level strategic insights."""
        insights = []
        total = len(all_items)

        if total == 0:
            return ["No items to analyze."]

        # Star analysis
        if stars:
            star_revenue_pct = sum(s.total_revenue for s in stars) / sum(i.total_revenue for i in all_items) * 100
            insights.append(
                f"⭐ STARS generating {star_revenue_pct:.0f}% of revenue. "
                "These items drive your business — protect and promote them."
            )

        # Dog warning
        if len(dogs) > total * 0.25:
            dog_names = ", ".join(d.name for d in dogs[:3])
            insights.append(
                f"🚨 {len(dogs)} items ({len(dogs) / total * 100:.0f}%) are dogs. "
                f"Consider removing: {dog_names}. Menu simplification improves kitchen efficiency."
            )

        # Plowhorse opportunity
        if plowhorses:
            total_plowhorse_qty = sum(p.quantity_sold for p in plowhorses)
            avg_margin_gap = sum(30 - p.contribution_margin for p in plowhorses) / len(plowhorses)
            if avg_margin_gap > 0:
                potential = total_plowhorse_qty * avg_margin_gap * 0.5
                insights.append(
                    f"💰 PLOWHORSE OPPORTUNITY: Optimizing margins on your {len(plowhorses)} "
                    f"plowhorses could add ${potential:,.0f} to profit."
                )

        # Puzzle opportunity
        if puzzles:
            sum(p.contribution_margin * p.quantity_sold for p in puzzles)
            if len(puzzles) >= 2:
                insights.append(
                    f"🧩 {len(puzzles)} puzzles have high margins but low sales. "
                    "Marketing push or menu repositioning could significantly increase profit."
                )

        return insights


def analyze_menu(items: list[MenuItemData | dict[str, Any]], **kwargs: Any) -> MenuEngineeringResult:
    """Convenience function for menu engineering analysis.

    Args:
        items: List of menu items with name, category, menu_price, food_cost, quantity_sold.
        **kwargs: Additional options passed to analyzer.

    Returns:
        MenuEngineeringResult with classifications and recommendations.
    """
    return MenuEngineeringAnalyzer.analyze(items, **kwargs)
