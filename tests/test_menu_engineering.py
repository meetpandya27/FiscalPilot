"""
Tests for Menu Engineering Analyzer — BCG matrix menu classification.
"""

from fiscalpilot.analyzers.menu_engineering import (
    MenuEngineeringAnalyzer,
    MenuItemCategory,
    MenuItemData,
)


class TestMenuItemClassification:
    """Test menu item classification logic."""

    def test_star_classification(self):
        """Stars: high popularity + high profitability."""
        items = [
            MenuItemData(name="Star Burger", menu_price=16, food_cost=4, quantity_sold=500),
            MenuItemData(name="Low Seller", menu_price=12, food_cost=6, quantity_sold=50),
        ]
        result = MenuEngineeringAnalyzer.analyze(items)

        star_item = next(i for i in result.items if i.name == "Star Burger")
        assert star_item.classification == MenuItemCategory.STAR

    def test_plowhorse_classification(self):
        """Plowhorses: high popularity + low profitability."""
        items = [
            MenuItemData(name="Budget Meal", menu_price=10, food_cost=5, quantity_sold=800),
            MenuItemData(name="Premium", menu_price=30, food_cost=8, quantity_sold=100),
        ]
        result = MenuEngineeringAnalyzer.analyze(items)

        plowhorse = next(i for i in result.items if i.name == "Budget Meal")
        assert plowhorse.classification == MenuItemCategory.PLOWHORSE

    def test_puzzle_classification(self):
        """Puzzles: low popularity + high profitability."""
        items = [
            # Puzzle: expensive with high margin, but rarely ordered
            MenuItemData(name="Lobster Special", menu_price=65, food_cost=20, quantity_sold=5),
            # High volume items to establish higher cutoffs
            MenuItemData(name="House Burger", menu_price=14, food_cost=6, quantity_sold=500),
            MenuItemData(name="Fries", menu_price=6, food_cost=1.50, quantity_sold=600),
            MenuItemData(name="Soda", menu_price=3, food_cost=0.50, quantity_sold=800),
        ]
        result = MenuEngineeringAnalyzer.analyze(items)

        puzzle = next(i for i in result.items if i.name == "Lobster Special")
        # Lobster: high CM ($45) vs avg, but very low sales (5) vs others (500+)
        assert puzzle.classification == MenuItemCategory.PUZZLE

    def test_dog_classification(self):
        """Dogs: low popularity + low profitability."""
        items = [
            # Dog: low margin AND unpopular
            MenuItemData(name="Sad Salad", menu_price=8, food_cost=6, quantity_sold=3),
            # Star for comparison: high margin, high popularity
            MenuItemData(name="Popular Burger", menu_price=16, food_cost=4, quantity_sold=500),
            MenuItemData(name="Wings", menu_price=14, food_cost=5, quantity_sold=400),
            MenuItemData(name="Tacos", menu_price=12, food_cost=4, quantity_sold=450),
        ]
        result = MenuEngineeringAnalyzer.analyze(items)

        dog = next(i for i in result.items if i.name == "Sad Salad")
        # Sad Salad: $2 CM (low) vs avg ~$10, only 3 orders (very low)
        assert dog.classification == MenuItemCategory.DOG


class TestMenuEngineeringCalculations:
    """Test menu engineering calculations."""

    def test_contribution_margin_calculation(self):
        """Contribution margin = price - food cost."""
        items = [MenuItemData(name="Test", menu_price=20, food_cost=6, quantity_sold=100)]
        result = MenuEngineeringAnalyzer.analyze(items)

        assert result.items[0].contribution_margin == 14.0

    def test_food_cost_percentage(self):
        """Food cost % = food_cost / menu_price * 100."""
        items = [MenuItemData(name="Test", menu_price=20, food_cost=6, quantity_sold=100)]
        result = MenuEngineeringAnalyzer.analyze(items)

        assert result.items[0].food_cost_pct == 30.0

    def test_total_revenue_calculation(self):
        """Total revenue = sum(price * quantity) for all items."""
        items = [
            MenuItemData(name="A", menu_price=10, food_cost=3, quantity_sold=100),
            MenuItemData(name="B", menu_price=20, food_cost=6, quantity_sold=50),
        ]
        result = MenuEngineeringAnalyzer.analyze(items)

        expected_revenue = (10 * 100) + (20 * 50)  # 1000 + 1000 = 2000
        assert result.total_revenue == expected_revenue

    def test_total_contribution(self):
        """Total contribution = sum(CM * quantity)."""
        items = [
            MenuItemData(name="A", menu_price=10, food_cost=3, quantity_sold=100),
            MenuItemData(name="B", menu_price=20, food_cost=6, quantity_sold=50),
        ]
        result = MenuEngineeringAnalyzer.analyze(items)

        expected_contribution = (7 * 100) + (14 * 50)  # 700 + 700 = 1400
        assert result.total_contribution == expected_contribution


class TestMenuEngineeringRecommendations:
    """Test recommendation generation."""

    def test_stars_get_feature_recommendation(self):
        """Stars should be featured/maintained."""
        items = [
            MenuItemData(name="Star", menu_price=20, food_cost=5, quantity_sold=500),
            MenuItemData(name="Other", menu_price=15, food_cost=8, quantity_sold=50),
        ]
        result = MenuEngineeringAnalyzer.analyze(items)

        star = next(i for i in result.items if i.name == "Star")
        assert star.recommendation
        assert any(word in star.recommendation.lower() for word in ["feature", "maintain", "premium", "promote"])

    def test_dogs_get_remove_recommendation(self):
        """Dogs should be considered for removal."""
        items = [
            MenuItemData(name="Dog", menu_price=8, food_cost=6, quantity_sold=3),
            MenuItemData(name="Star", menu_price=20, food_cost=5, quantity_sold=500),
            MenuItemData(name="Star2", menu_price=18, food_cost=4, quantity_sold=400),
            MenuItemData(name="Star3", menu_price=16, food_cost=4, quantity_sold=450),
        ]
        result = MenuEngineeringAnalyzer.analyze(items)

        dog = next((i for i in result.items if i.name == "Dog"), None)
        assert dog is not None, f"Dog not found. Classifications: {[(i.name, i.classification) for i in result.items]}"
        assert dog.classification == MenuItemCategory.DOG, f"Dog classified as {dog.classification}"
        assert dog.recommendation
        # Dogs get removal/rework recommendations
        rec_lower = dog.recommendation.lower()
        assert any(word in rec_lower for word in ["remov", "drop", "eliminat", "consider", "rework", "rebrand"])

    def test_puzzles_get_marketing_recommendation(self):
        """Puzzles need marketing/repositioning."""
        items = [
            MenuItemData(name="Puzzle", menu_price=45, food_cost=10, quantity_sold=5),
            MenuItemData(name="Popular", menu_price=15, food_cost=5, quantity_sold=500),
            MenuItemData(name="Popular2", menu_price=14, food_cost=5, quantity_sold=400),
            MenuItemData(name="Popular3", menu_price=16, food_cost=6, quantity_sold=450),
        ]
        result = MenuEngineeringAnalyzer.analyze(items)

        puzzle = next((i for i in result.items if i.name == "Puzzle"), None)
        assert puzzle is not None, f"Puzzle not found. Classifications: {[(i.name, i.classification) for i in result.items]}"
        assert puzzle.classification == MenuItemCategory.PUZZLE, f"Puzzle classified as {puzzle.classification}"
        assert puzzle.recommendation
        # Puzzles get promotion/marketing recommendations
        rec_lower = puzzle.recommendation.lower()
        assert any(word in rec_lower for word in ["promot", "market", "visib", "placement", "increase", "boost", "featue", "sell"])


class TestMenuEngineeringResult:
    """Test result object structure."""

    def test_result_has_all_categories(self):
        """Result should track items in all categories."""
        items = [
            MenuItemData(name="Star", menu_price=20, food_cost=4, quantity_sold=500),
            MenuItemData(name="Plowhorse", menu_price=10, food_cost=5, quantity_sold=600),
            MenuItemData(name="Puzzle", menu_price=50, food_cost=12, quantity_sold=20),
            MenuItemData(name="Dog", menu_price=8, food_cost=5, quantity_sold=15),
        ]
        result = MenuEngineeringAnalyzer.analyze(items)

        assert result.star_count >= 0
        assert result.plowhorse_count >= 0
        assert result.puzzle_count >= 0
        assert result.dog_count >= 0
        assert result.star_count + result.plowhorse_count + result.puzzle_count + result.dog_count == 4

    def test_insights_generated(self):
        """Should generate actionable insights."""
        items = [
            MenuItemData(name="A", menu_price=20, food_cost=5, quantity_sold=300),
            MenuItemData(name="B", menu_price=15, food_cost=8, quantity_sold=100),
        ]
        result = MenuEngineeringAnalyzer.analyze(items)

        assert len(result.insights) > 0

    def test_empty_items_handled(self):
        """Should handle empty item list gracefully."""
        result = MenuEngineeringAnalyzer.analyze([])

        assert result.total_items == 0
        assert result.total_revenue == 0


class TestMenuCategories:
    """Test category-level analysis."""

    def test_category_grouping(self):
        """Items with same category should be grouped."""
        items = [
            MenuItemData(name="Burger", menu_price=16, food_cost=4, quantity_sold=300, category="Mains"),
            MenuItemData(name="Pasta", menu_price=18, food_cost=5, quantity_sold=200, category="Mains"),
            MenuItemData(name="Soda", menu_price=3, food_cost=0.5, quantity_sold=500, category="Beverages"),
        ]
        result = MenuEngineeringAnalyzer.analyze(items)

        assert len(result.categories) >= 2

        mains = next((c for c in result.categories if c.name == "Mains"), None)
        assert mains is not None
        assert mains.item_count == 2
