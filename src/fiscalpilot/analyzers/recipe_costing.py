"""
Recipe Costing Analyzer — calculate food costs and menu pricing.

Restaurant-specific module for:
- Recipe ingredient costing
- Menu item cost analysis
- Food cost percentage tracking
- Portion cost optimization
- Menu pricing recommendations
- Plate cost breakdowns
- Yield calculations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any


class UnitType(str, Enum):
    """Units of measurement."""
    
    # Weight
    OUNCE = "oz"
    POUND = "lb"
    GRAM = "g"
    KILOGRAM = "kg"
    
    # Volume
    TEASPOON = "tsp"
    TABLESPOON = "tbsp"
    FLUID_OUNCE = "fl_oz"
    CUP = "cup"
    PINT = "pt"
    QUART = "qt"
    GALLON = "gal"
    MILLILITER = "ml"
    LITER = "L"
    
    # Count
    EACH = "each"
    DOZEN = "dozen"
    CASE = "case"
    
    # Other
    PORTION = "portion"
    SERVING = "serving"


# Conversion factors to base units (oz for weight, fl_oz for volume)
UNIT_CONVERSIONS = {
    # Weight -> ounces
    UnitType.OUNCE: Decimal("1"),
    UnitType.POUND: Decimal("16"),
    UnitType.GRAM: Decimal("0.035274"),
    UnitType.KILOGRAM: Decimal("35.274"),
    
    # Volume -> fluid ounces
    UnitType.TEASPOON: Decimal("0.1667"),
    UnitType.TABLESPOON: Decimal("0.5"),
    UnitType.FLUID_OUNCE: Decimal("1"),
    UnitType.CUP: Decimal("8"),
    UnitType.PINT: Decimal("16"),
    UnitType.QUART: Decimal("32"),
    UnitType.GALLON: Decimal("128"),
    UnitType.MILLILITER: Decimal("0.033814"),
    UnitType.LITER: Decimal("33.814"),
    
    # Count
    UnitType.EACH: Decimal("1"),
    UnitType.DOZEN: Decimal("12"),
    UnitType.CASE: Decimal("1"),  # Variable, should be specified
    UnitType.PORTION: Decimal("1"),
    UnitType.SERVING: Decimal("1"),
}


@dataclass
class Ingredient:
    """An ingredient used in recipes."""
    
    id: str
    name: str
    purchase_unit: UnitType
    purchase_quantity: Decimal
    purchase_price: Decimal
    recipe_unit: UnitType
    yield_percentage: float = 100.0  # Usable percentage after prep
    
    @property
    def cost_per_purchase_unit(self) -> Decimal:
        """Cost per purchase unit."""
        if self.purchase_quantity <= 0:
            return Decimal("0")
        return self.purchase_price / self.purchase_quantity
    
    @property
    def cost_per_recipe_unit(self) -> Decimal:
        """Cost per recipe unit, adjusted for yield."""
        # Convert purchase unit to recipe unit
        purchase_in_base = UNIT_CONVERSIONS.get(self.purchase_unit, Decimal("1"))
        recipe_in_base = UNIT_CONVERSIONS.get(self.recipe_unit, Decimal("1"))
        
        if recipe_in_base == 0:
            return Decimal("0")
        
        # Units of recipe per purchase
        units_per_purchase = (self.purchase_quantity * purchase_in_base) / recipe_in_base
        
        # Adjust for yield
        usable_units = units_per_purchase * Decimal(str(self.yield_percentage / 100))
        
        if usable_units <= 0:
            return Decimal("0")
        
        return self.purchase_price / usable_units


@dataclass
class RecipeItem:
    """An ingredient line in a recipe."""
    
    ingredient: Ingredient
    quantity: Decimal
    unit: UnitType | None = None  # Defaults to ingredient's recipe_unit
    prep_note: str | None = None
    
    @property
    def cost(self) -> Decimal:
        """Cost for this line item."""
        unit = self.unit or self.ingredient.recipe_unit
        
        # If using same unit as recipe unit, simple calculation
        if unit == self.ingredient.recipe_unit:
            return self.quantity * self.ingredient.cost_per_recipe_unit
        
        # Convert units
        item_in_base = UNIT_CONVERSIONS.get(unit, Decimal("1"))
        recipe_in_base = UNIT_CONVERSIONS.get(self.ingredient.recipe_unit, Decimal("1"))
        
        quantity_in_recipe_units = self.quantity * item_in_base / recipe_in_base
        return quantity_in_recipe_units * self.ingredient.cost_per_recipe_unit


@dataclass
class Recipe:
    """A recipe with ingredients and costing."""
    
    id: str
    name: str
    category: str
    items: list[RecipeItem] = field(default_factory=list)
    yield_quantity: Decimal = Decimal("1")  # Number of portions/servings
    yield_unit: str = "portion"
    prep_time_minutes: int = 0
    cook_time_minutes: int = 0
    labor_cost_per_hour: Decimal = Decimal("15")  # For labor cost calculations
    notes: str | None = None
    
    # Pricing
    target_food_cost_pct: float = 30.0  # Target food cost percentage
    menu_price: Decimal | None = None  # Actual menu price
    
    @property
    def total_ingredient_cost(self) -> Decimal:
        """Total cost of all ingredients."""
        return sum(item.cost for item in self.items)
    
    @property
    def cost_per_portion(self) -> Decimal:
        """Cost per portion/serving."""
        if self.yield_quantity <= 0:
            return Decimal("0")
        return self.total_ingredient_cost / self.yield_quantity
    
    @property
    def labor_cost(self) -> Decimal:
        """Estimated labor cost for prep and cooking."""
        total_minutes = self.prep_time_minutes + self.cook_time_minutes
        hours = Decimal(str(total_minutes / 60))
        return hours * self.labor_cost_per_hour / self.yield_quantity
    
    @property
    def total_cost_per_portion(self) -> Decimal:
        """Total cost per portion including labor."""
        return self.cost_per_portion + self.labor_cost
    
    @property
    def suggested_price(self) -> Decimal:
        """Suggested menu price based on target food cost %."""
        if self.target_food_cost_pct <= 0:
            return Decimal("0")
        return (self.cost_per_portion / Decimal(str(self.target_food_cost_pct / 100))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    
    @property
    def actual_food_cost_pct(self) -> float | None:
        """Actual food cost percentage if menu price is set."""
        if not self.menu_price or self.menu_price <= 0:
            return None
        return float(self.cost_per_portion / self.menu_price * 100)
    
    @property
    def gross_profit(self) -> Decimal | None:
        """Gross profit per portion."""
        if not self.menu_price:
            return None
        return self.menu_price - self.cost_per_portion
    
    @property
    def margin_pct(self) -> float | None:
        """Gross margin percentage."""
        if not self.menu_price or self.menu_price <= 0:
            return None
        return float((self.menu_price - self.cost_per_portion) / self.menu_price * 100)


@dataclass
class RecipeCostAnalysis:
    """Detailed cost analysis for a recipe."""
    
    recipe_id: str
    recipe_name: str
    category: str
    total_ingredient_cost: Decimal
    cost_per_portion: Decimal
    yield_quantity: Decimal
    labor_cost_per_portion: Decimal
    total_cost_per_portion: Decimal
    suggested_price: Decimal
    menu_price: Decimal | None
    actual_food_cost_pct: float | None
    gross_profit: Decimal | None
    margin_pct: float | None
    ingredient_breakdown: list[dict[str, Any]]
    
    @property
    def is_profitable(self) -> bool:
        """Recipe is profitable if margin > 0."""
        return self.gross_profit is not None and self.gross_profit > 0
    
    @property
    def food_cost_on_target(self) -> bool:
        """Food cost is within 5% of typical 30% target."""
        if self.actual_food_cost_pct is None:
            return False
        return 25 <= self.actual_food_cost_pct <= 35


class RecipeCostingAnalyzer:
    """Analyze recipe costs and menu pricing.

    Usage::

        analyzer = RecipeCostingAnalyzer()
        
        # Add ingredients
        tomato = Ingredient(
            id="tomato",
            name="Roma Tomatoes",
            purchase_unit=UnitType.POUND,
            purchase_quantity=Decimal("1"),
            purchase_price=Decimal("2.99"),
            recipe_unit=UnitType.EACH,
        )
        analyzer.add_ingredient(tomato)
        
        # Create recipe
        salsa = Recipe(
            id="salsa",
            name="House Salsa",
            category="Appetizers",
        )
        salsa.items.append(RecipeItem(ingredient=tomato, quantity=Decimal("6")))
        analyzer.add_recipe(salsa)
        
        # Analyze
        analysis = analyzer.analyze_recipe("salsa")
    """

    def __init__(
        self,
        default_food_cost_target: float = 30.0,
        default_labor_rate: Decimal = Decimal("15"),
    ) -> None:
        self.default_food_cost_target = default_food_cost_target
        self.default_labor_rate = default_labor_rate
        self.ingredients: dict[str, Ingredient] = {}
        self.recipes: dict[str, Recipe] = {}

    def add_ingredient(self, ingredient: Ingredient) -> None:
        """Add or update an ingredient."""
        self.ingredients[ingredient.id] = ingredient

    def get_ingredient(self, ingredient_id: str) -> Ingredient | None:
        """Get an ingredient by ID."""
        return self.ingredients.get(ingredient_id)

    def add_recipe(self, recipe: Recipe) -> None:
        """Add or update a recipe."""
        if recipe.labor_cost_per_hour == Decimal("15"):
            recipe.labor_cost_per_hour = self.default_labor_rate
        if recipe.target_food_cost_pct == 30.0:
            recipe.target_food_cost_pct = self.default_food_cost_target
        self.recipes[recipe.id] = recipe

    def get_recipe(self, recipe_id: str) -> Recipe | None:
        """Get a recipe by ID."""
        return self.recipes.get(recipe_id)

    def analyze_recipe(self, recipe_id: str) -> RecipeCostAnalysis | None:
        """Generate detailed cost analysis for a recipe."""
        recipe = self.recipes.get(recipe_id)
        if not recipe:
            return None
        
        # Build ingredient breakdown
        breakdown = []
        for item in recipe.items:
            breakdown.append({
                "ingredient": item.ingredient.name,
                "quantity": float(item.quantity),
                "unit": (item.unit or item.ingredient.recipe_unit).value,
                "cost": float(item.cost),
                "cost_pct": float(item.cost / max(recipe.total_ingredient_cost, Decimal("0.01")) * 100),
            })
        
        return RecipeCostAnalysis(
            recipe_id=recipe.id,
            recipe_name=recipe.name,
            category=recipe.category,
            total_ingredient_cost=recipe.total_ingredient_cost,
            cost_per_portion=recipe.cost_per_portion,
            yield_quantity=recipe.yield_quantity,
            labor_cost_per_portion=recipe.labor_cost,
            total_cost_per_portion=recipe.total_cost_per_portion,
            suggested_price=recipe.suggested_price,
            menu_price=recipe.menu_price,
            actual_food_cost_pct=recipe.actual_food_cost_pct,
            gross_profit=recipe.gross_profit,
            margin_pct=recipe.margin_pct,
            ingredient_breakdown=sorted(breakdown, key=lambda x: x["cost"], reverse=True),
        )

    def analyze_all_recipes(self) -> list[RecipeCostAnalysis]:
        """Analyze all recipes."""
        analyses = []
        for recipe_id in self.recipes:
            analysis = self.analyze_recipe(recipe_id)
            if analysis:
                analyses.append(analysis)
        return sorted(analyses, key=lambda x: x.cost_per_portion, reverse=True)

    def get_high_cost_recipes(
        self,
        threshold_pct: float = 35.0,
    ) -> list[RecipeCostAnalysis]:
        """Get recipes with food cost above threshold."""
        return [
            a for a in self.analyze_all_recipes()
            if a.actual_food_cost_pct and a.actual_food_cost_pct > threshold_pct
        ]

    def get_low_margin_recipes(
        self,
        threshold_pct: float = 60.0,
    ) -> list[RecipeCostAnalysis]:
        """Get recipes with margin below threshold."""
        return [
            a for a in self.analyze_all_recipes()
            if a.margin_pct and a.margin_pct < threshold_pct
        ]

    def get_menu_analysis(self) -> dict[str, Any]:
        """Get overall menu cost analysis."""
        analyses = self.analyze_all_recipes()
        
        if not analyses:
            return {
                "recipe_count": 0,
                "avg_food_cost_pct": 0,
                "avg_margin_pct": 0,
                "total_menu_value": 0,
            }
        
        priced_recipes = [a for a in analyses if a.menu_price]
        
        return {
            "recipe_count": len(analyses),
            "priced_recipes": len(priced_recipes),
            "avg_food_cost_pct": (
                sum(a.actual_food_cost_pct for a in priced_recipes if a.actual_food_cost_pct) / len(priced_recipes)
                if priced_recipes else 0
            ),
            "avg_margin_pct": (
                sum(a.margin_pct for a in priced_recipes if a.margin_pct) / len(priced_recipes)
                if priced_recipes else 0
            ),
            "avg_cost_per_portion": float(
                sum(a.cost_per_portion for a in analyses) / len(analyses)
            ),
            "highest_cost_recipe": max(analyses, key=lambda x: x.cost_per_portion).recipe_name,
            "lowest_cost_recipe": min(analyses, key=lambda x: x.cost_per_portion).recipe_name,
            "high_cost_count": len(self.get_high_cost_recipes()),
            "low_margin_count": len(self.get_low_margin_recipes()),
            "by_category": self._analyze_by_category(analyses),
        }

    def _analyze_by_category(
        self,
        analyses: list[RecipeCostAnalysis],
    ) -> dict[str, dict[str, Any]]:
        """Analyze recipes grouped by category."""
        categories: dict[str, list[RecipeCostAnalysis]] = {}
        
        for analysis in analyses:
            cat = analysis.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(analysis)
        
        return {
            cat: {
                "recipe_count": len(items),
                "avg_cost": float(sum(i.cost_per_portion for i in items) / len(items)),
                "avg_food_cost_pct": (
                    sum(i.actual_food_cost_pct for i in items if i.actual_food_cost_pct) / 
                    len([i for i in items if i.actual_food_cost_pct])
                    if any(i.actual_food_cost_pct for i in items) else 0
                ),
            }
            for cat, items in categories.items()
        }

    def suggest_price_adjustments(
        self,
        target_food_cost_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        """Suggest price adjustments to hit target food cost %.
        
        Returns list of recipes needing adjustment with suggested new prices.
        """
        target = target_food_cost_pct or self.default_food_cost_target
        adjustments = []
        
        for recipe in self.recipes.values():
            if not recipe.menu_price:
                continue
            
            actual_pct = recipe.actual_food_cost_pct
            if actual_pct is None:
                continue
            
            # If actual is more than 3% off target
            if abs(actual_pct - target) > 3:
                suggested_price = recipe.cost_per_portion / Decimal(str(target / 100))
                
                adjustments.append({
                    "recipe_id": recipe.id,
                    "recipe_name": recipe.name,
                    "current_price": float(recipe.menu_price),
                    "suggested_price": float(suggested_price.quantize(Decimal("0.01"))),
                    "price_change": float(suggested_price - recipe.menu_price),
                    "current_food_cost_pct": actual_pct,
                    "target_food_cost_pct": target,
                })
        
        return sorted(adjustments, key=lambda x: abs(x["price_change"]), reverse=True)

    def find_substitutions(
        self,
        recipe_id: str,
        max_cost_reduction_pct: float = 20.0,
    ) -> list[dict[str, Any]]:
        """Find potential ingredient substitutions to reduce cost.
        
        This is a simplified version - in practice would need
        ingredient alternatives database.
        """
        recipe = self.recipes.get(recipe_id)
        if not recipe:
            return []
        
        # Find high-cost ingredients
        suggestions = []
        
        analysis = self.analyze_recipe(recipe_id)
        if not analysis:
            return []
        
        for item_data in analysis.ingredient_breakdown:
            if item_data["cost_pct"] > 25:  # If ingredient is >25% of cost
                suggestions.append({
                    "ingredient": item_data["ingredient"],
                    "current_cost_pct": item_data["cost_pct"],
                    "suggestion": f"Consider alternatives for {item_data['ingredient']} - high cost impact",
                    "potential_savings": item_data["cost"] * 0.2,  # Assume 20% savings possible
                })
        
        return suggestions

    def batch_update_ingredient_costs(
        self,
        cost_updates: dict[str, Decimal],
    ) -> dict[str, dict[str, Any]]:
        """Update ingredient costs and show impact on recipes.
        
        Args:
            cost_updates: Dict of ingredient_id -> new purchase_price.
        
        Returns:
            Dict of recipe_id -> cost change impact.
        """
        # Store old costs
        old_costs = {}
        for ing_id, new_price in cost_updates.items():
            if ing_id in self.ingredients:
                old_costs[ing_id] = self.ingredients[ing_id].purchase_price
                self.ingredients[ing_id].purchase_price = new_price
        
        # Calculate impact on each recipe
        impact = {}
        for recipe in self.recipes.values():
            # Check if recipe uses any updated ingredients
            affected_ingredients = [
                item for item in recipe.items
                if item.ingredient.id in cost_updates
            ]
            
            if affected_ingredients:
                # Calculate new cost
                new_cost = recipe.cost_per_portion
                
                # Calculate old cost (temporarily restore prices)
                for item in affected_ingredients:
                    item.ingredient.purchase_price = old_costs[item.ingredient.id]
                old_cost = recipe.cost_per_portion
                
                # Restore new prices
                for item in affected_ingredients:
                    item.ingredient.purchase_price = cost_updates[item.ingredient.id]
                
                impact[recipe.id] = {
                    "recipe_name": recipe.name,
                    "old_cost": float(old_cost),
                    "new_cost": float(new_cost),
                    "change": float(new_cost - old_cost),
                    "change_pct": float((new_cost - old_cost) / old_cost * 100) if old_cost > 0 else 0,
                    "affected_ingredients": [i.ingredient.name for i in affected_ingredients],
                }
        
        return impact
