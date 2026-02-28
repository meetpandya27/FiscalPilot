"""
Scenario Planning — what-if analysis for financial decisions.

Provides:
- Revenue scenario modeling
- Cost scenario modeling
- Pricing impact analysis
- Growth/contraction scenarios
- Sensitivity analysis
- Monte Carlo simulations
- Break-even scenario analysis
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Callable
import random


class ScenarioType(str, Enum):
    """Types of scenarios."""
    
    REVENUE = "revenue"
    COST = "cost"
    PRICING = "pricing"
    VOLUME = "volume"
    MIXED = "mixed"
    CUSTOM = "custom"


@dataclass
class ScenarioVariable:
    """A variable that can change in scenarios."""
    
    name: str
    base_value: Decimal
    description: str | None = None
    unit: str | None = None
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    
    # For sensitivity analysis
    low_case: Decimal | None = None  # e.g., -20%
    high_case: Decimal | None = None  # e.g., +20%


@dataclass
class Assumption:
    """An assumption in a scenario."""
    
    name: str
    value: Decimal | float | str
    description: str | None = None
    is_percentage: bool = False


@dataclass
class ScenarioResult:
    """Result of running a scenario."""
    
    name: str
    scenario_type: ScenarioType
    
    # Inputs
    assumptions: list[Assumption] = field(default_factory=list)
    variables_changed: dict[str, Decimal] = field(default_factory=dict)
    
    # Outputs
    revenue: Decimal = Decimal("0")
    costs: Decimal = Decimal("0")
    gross_profit: Decimal = Decimal("0")
    net_income: Decimal = Decimal("0")
    
    # Changes from baseline
    revenue_change: Decimal = Decimal("0")
    cost_change: Decimal = Decimal("0")
    profit_change: Decimal = Decimal("0")
    
    # Ratios
    gross_margin_pct: float = 0.0
    net_margin_pct: float = 0.0
    
    # Additional metrics
    custom_metrics: dict[str, Any] = field(default_factory=dict)
    
    @property
    def profit_change_pct(self) -> float:
        """Profit change as percentage."""
        if self.net_income - self.profit_change == 0:
            return 0.0
        baseline_profit = self.net_income - self.profit_change
        return float(self.profit_change / baseline_profit * 100) if baseline_profit != 0 else 0.0


@dataclass
class SensitivityResult:
    """Result of sensitivity analysis."""
    
    variable_name: str
    base_value: Decimal
    
    # Results at different values
    results: list[dict[str, Any]] = field(default_factory=list)
    
    # Key findings
    break_even_value: Decimal | None = None
    most_sensitive_metric: str | None = None
    sensitivity_coefficient: float = 0.0  # % change in output per % change in input


@dataclass
class MonteCarloResult:
    """Result of Monte Carlo simulation."""
    
    iterations: int
    
    # Distribution statistics
    mean_profit: Decimal
    median_profit: Decimal
    std_dev: Decimal
    min_profit: Decimal
    max_profit: Decimal
    
    # Percentiles
    percentile_5: Decimal
    percentile_25: Decimal
    percentile_75: Decimal
    percentile_95: Decimal
    
    # Probability metrics
    probability_positive: float  # Probability of positive profit
    probability_loss: float  # Probability of loss
    
    # Raw results for histogram
    all_results: list[Decimal] = field(default_factory=list)


class ScenarioPlanner:
    """Scenario planning and what-if analysis.

    Usage::

        planner = ScenarioPlanner()
        
        # Set baseline
        planner.set_baseline(
            revenue=Decimal("1000000"),
            costs=Decimal("800000"),
        )
        
        # Define variables
        planner.add_variable(ScenarioVariable(
            name="price_per_unit",
            base_value=Decimal("50"),
            low_case=Decimal("45"),
            high_case=Decimal("55"),
        ))
        
        # Run scenarios
        result = planner.run_scenario(
            name="Price Increase 10%",
            changes={"price_per_unit": Decimal("55")},
        )
        
        # Sensitivity analysis
        sensitivity = planner.sensitivity_analysis("price_per_unit")
    """

    def __init__(self) -> None:
        # Baseline financials
        self.baseline_revenue = Decimal("0")
        self.baseline_costs = Decimal("0")
        self.baseline_fixed_costs = Decimal("0")
        self.baseline_variable_costs = Decimal("0")
        
        # Variables
        self.variables: dict[str, ScenarioVariable] = {}
        
        # Custom calculation functions
        self._revenue_fn: Callable | None = None
        self._cost_fn: Callable | None = None
        
        # Results history
        self.scenarios: list[ScenarioResult] = []

    def set_baseline(
        self,
        revenue: Decimal,
        costs: Decimal,
        fixed_costs: Decimal | None = None,
        variable_costs: Decimal | None = None,
    ) -> None:
        """Set baseline financial figures."""
        self.baseline_revenue = revenue
        self.baseline_costs = costs
        self.baseline_fixed_costs = fixed_costs or Decimal("0")
        self.baseline_variable_costs = variable_costs or costs - (fixed_costs or Decimal("0"))

    def add_variable(self, variable: ScenarioVariable) -> None:
        """Add a scenario variable."""
        self.variables[variable.name] = variable

    def set_revenue_function(self, fn: Callable[[dict[str, Decimal]], Decimal]) -> None:
        """Set custom revenue calculation function.
        
        Function receives dict of variable name -> value, returns revenue.
        """
        self._revenue_fn = fn

    def set_cost_function(self, fn: Callable[[dict[str, Decimal]], Decimal]) -> None:
        """Set custom cost calculation function."""
        self._cost_fn = fn

    def _calculate_financials(
        self,
        variable_values: dict[str, Decimal],
    ) -> tuple[Decimal, Decimal]:
        """Calculate revenue and costs given variable values."""
        # Use custom functions if provided
        if self._revenue_fn:
            revenue = self._revenue_fn(variable_values)
        else:
            revenue = self.baseline_revenue
            # Apply simple scaling based on volume/price changes
            if "volume" in variable_values and "volume" in self.variables:
                base_vol = self.variables["volume"].base_value
                if base_vol > 0:
                    volume_factor = variable_values["volume"] / base_vol
                    revenue = revenue * volume_factor
            if "price" in variable_values and "price" in self.variables:
                base_price = self.variables["price"].base_value
                if base_price > 0:
                    price_factor = variable_values["price"] / base_price
                    revenue = revenue * price_factor
        
        if self._cost_fn:
            costs = self._cost_fn(variable_values)
        else:
            costs = self.baseline_costs
            # Scale variable costs with volume
            if "volume" in variable_values and "volume" in self.variables:
                base_vol = self.variables["volume"].base_value
                if base_vol > 0:
                    volume_factor = variable_values["volume"] / base_vol
                    costs = self.baseline_fixed_costs + (self.baseline_variable_costs * volume_factor)
        
        return revenue, costs

    def run_scenario(
        self,
        name: str,
        changes: dict[str, Decimal],
        scenario_type: ScenarioType = ScenarioType.MIXED,
        assumptions: list[Assumption] | None = None,
    ) -> ScenarioResult:
        """Run a scenario with specified changes.
        
        Args:
            name: Scenario name.
            changes: Dict of variable name -> new value.
            scenario_type: Type of scenario.
            assumptions: List of assumptions.
        
        Returns:
            ScenarioResult with full analysis.
        """
        # Build variable values (base + changes)
        var_values = {
            v.name: v.base_value
            for v in self.variables.values()
        }
        var_values.update(changes)
        
        # Calculate financials
        revenue, costs = self._calculate_financials(var_values)
        gross_profit = revenue - costs
        net_income = gross_profit  # Simplified; could add taxes etc.
        
        # Calculate changes from baseline
        baseline_profit = self.baseline_revenue - self.baseline_costs
        
        result = ScenarioResult(
            name=name,
            scenario_type=scenario_type,
            assumptions=assumptions or [],
            variables_changed=changes,
            revenue=revenue,
            costs=costs,
            gross_profit=gross_profit,
            net_income=net_income,
            revenue_change=revenue - self.baseline_revenue,
            cost_change=costs - self.baseline_costs,
            profit_change=net_income - baseline_profit,
            gross_margin_pct=float(gross_profit / revenue * 100) if revenue > 0 else 0,
            net_margin_pct=float(net_income / revenue * 100) if revenue > 0 else 0,
        )
        
        self.scenarios.append(result)
        return result

    def run_percentage_change(
        self,
        name: str,
        variable: str,
        percent_change: float,
    ) -> ScenarioResult:
        """Run scenario with percentage change to a variable."""
        var = self.variables.get(variable)
        if not var:
            raise ValueError(f"Variable {variable} not found")
        
        new_value = var.base_value * Decimal(str(1 + percent_change / 100))
        return self.run_scenario(
            name=name,
            changes={variable: new_value},
            assumptions=[
                Assumption(
                    name=f"{variable} change",
                    value=percent_change,
                    is_percentage=True,
                )
            ],
        )

    def compare_scenarios(
        self,
        scenario_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """Compare multiple scenarios."""
        if scenario_names:
            scenarios = [s for s in self.scenarios if s.name in scenario_names]
        else:
            scenarios = self.scenarios
        
        if not scenarios:
            return {"error": "No scenarios to compare"}
        
        baseline_profit = self.baseline_revenue - self.baseline_costs
        
        return {
            "baseline": {
                "revenue": float(self.baseline_revenue),
                "costs": float(self.baseline_costs),
                "profit": float(baseline_profit),
            },
            "scenarios": [
                {
                    "name": s.name,
                    "revenue": float(s.revenue),
                    "costs": float(s.costs),
                    "profit": float(s.net_income),
                    "profit_change": float(s.profit_change),
                    "profit_change_pct": s.profit_change_pct,
                    "margin_pct": s.net_margin_pct,
                }
                for s in sorted(scenarios, key=lambda x: x.net_income, reverse=True)
            ],
            "best_scenario": max(scenarios, key=lambda x: x.net_income).name,
            "worst_scenario": min(scenarios, key=lambda x: x.net_income).name,
        }

    def sensitivity_analysis(
        self,
        variable: str,
        steps: int = 10,
        range_pct: float = 50.0,
    ) -> SensitivityResult:
        """Perform sensitivity analysis on a variable.
        
        Args:
            variable: Variable name to analyze.
            steps: Number of steps in each direction.
            range_pct: Range as percentage of base value.
        
        Returns:
            SensitivityResult with analysis at each step.
        """
        var = self.variables.get(variable)
        if not var:
            raise ValueError(f"Variable {variable} not found")
        
        base = var.base_value
        min_val = base * Decimal(str(1 - range_pct / 100))
        max_val = base * Decimal(str(1 + range_pct / 100))
        
        if var.min_value is not None:
            min_val = max(min_val, var.min_value)
        if var.max_value is not None:
            max_val = min(max_val, var.max_value)
        
        step_size = (max_val - min_val) / (steps * 2)
        
        results = []
        baseline_profit = self.baseline_revenue - self.baseline_costs
        break_even_value = None
        
        current = min_val
        prev_profit = None
        
        while current <= max_val:
            # Run scenario
            revenue, costs = self._calculate_financials({variable: current})
            profit = revenue - costs
            
            pct_change = float((current - base) / base * 100) if base != 0 else 0
            profit_pct_change = float((profit - baseline_profit) / baseline_profit * 100) if baseline_profit != 0 else 0
            
            results.append({
                "value": float(current),
                "pct_from_base": pct_change,
                "revenue": float(revenue),
                "costs": float(costs),
                "profit": float(profit),
                "profit_pct_change": profit_pct_change,
            })
            
            # Check for break-even crossing
            if prev_profit is not None:
                if (prev_profit < 0 and profit >= 0) or (prev_profit >= 0 and profit < 0):
                    # Interpolate break-even
                    break_even_value = current - step_size / 2
            
            prev_profit = profit
            current += step_size
        
        # Calculate sensitivity coefficient
        if len(results) >= 2:
            first = results[0]
            last = results[-1]
            var_pct_change = last["pct_from_base"] - first["pct_from_base"]
            profit_pct_change = last["profit_pct_change"] - first["profit_pct_change"]
            sensitivity = profit_pct_change / var_pct_change if var_pct_change != 0 else 0
        else:
            sensitivity = 0
        
        return SensitivityResult(
            variable_name=variable,
            base_value=base,
            results=results,
            break_even_value=break_even_value,
            most_sensitive_metric="profit",
            sensitivity_coefficient=sensitivity,
        )

    def monte_carlo(
        self,
        iterations: int = 1000,
        variable_distributions: dict[str, tuple[float, float]] | None = None,
    ) -> MonteCarloResult:
        """Run Monte Carlo simulation.
        
        Args:
            iterations: Number of simulation runs.
            variable_distributions: Dict of variable -> (mean, std_dev) for normal distribution.
                                   If not provided, uses uniform between low_case and high_case.
        
        Returns:
            MonteCarloResult with distribution statistics.
        """
        results: list[Decimal] = []
        
        for _ in range(iterations):
            # Generate random values for each variable
            var_values = {}
            for name, var in self.variables.items():
                if variable_distributions and name in variable_distributions:
                    mean, std = variable_distributions[name]
                    value = Decimal(str(random.gauss(mean, std)))
                elif var.low_case is not None and var.high_case is not None:
                    low = float(var.low_case)
                    high = float(var.high_case)
                    value = Decimal(str(random.uniform(low, high)))
                else:
                    value = var.base_value
                
                # Clamp to bounds
                if var.min_value is not None:
                    value = max(value, var.min_value)
                if var.max_value is not None:
                    value = min(value, var.max_value)
                
                var_values[name] = value
            
            # Calculate profit
            revenue, costs = self._calculate_financials(var_values)
            profit = revenue - costs
            results.append(profit)
        
        # Calculate statistics
        results.sort()
        n = len(results)
        
        mean_profit = sum(results) / n
        median_profit = results[n // 2]
        
        # Standard deviation
        variance = sum((r - mean_profit) ** 2 for r in results) / n
        std_dev = Decimal(str(float(variance) ** 0.5))
        
        # Percentiles
        def percentile(p: float) -> Decimal:
            idx = int(n * p / 100)
            return results[min(idx, n - 1)]
        
        return MonteCarloResult(
            iterations=iterations,
            mean_profit=mean_profit,
            median_profit=median_profit,
            std_dev=std_dev,
            min_profit=results[0],
            max_profit=results[-1],
            percentile_5=percentile(5),
            percentile_25=percentile(25),
            percentile_75=percentile(75),
            percentile_95=percentile(95),
            probability_positive=len([r for r in results if r > 0]) / n * 100,
            probability_loss=len([r for r in results if r < 0]) / n * 100,
            all_results=results,
        )

    def best_worst_case(self) -> dict[str, ScenarioResult]:
        """Generate best and worst case scenarios using variable bounds."""
        # Best case: maximize profit
        best_changes = {}
        worst_changes = {}
        
        for name, var in self.variables.items():
            # Determine which direction helps profit
            # This is simplified; real implementation would test both
            if var.high_case is not None:
                best_changes[name] = var.high_case
            if var.low_case is not None:
                worst_changes[name] = var.low_case
        
        best = self.run_scenario(
            name="Best Case",
            changes=best_changes,
            scenario_type=ScenarioType.MIXED,
        )
        
        worst = self.run_scenario(
            name="Worst Case",
            changes=worst_changes,
            scenario_type=ScenarioType.MIXED,
        )
        
        return {
            "best_case": best,
            "worst_case": worst,
        }

    def pricing_impact(
        self,
        price_changes: list[float],
        elasticity: float = -1.0,
        current_price: Decimal | None = None,
        current_volume: Decimal | None = None,
    ) -> list[ScenarioResult]:
        """Analyze impact of price changes with demand elasticity.
        
        Args:
            price_changes: List of percentage price changes to test.
            elasticity: Price elasticity of demand (negative value).
            current_price: Current price (or use variable).
            current_volume: Current volume (or use variable).
        
        Returns:
            List of scenario results.
        """
        price = current_price or self.variables.get("price", ScenarioVariable("price", Decimal("100"))).base_value
        volume = current_volume or self.variables.get("volume", ScenarioVariable("volume", Decimal("1000"))).base_value
        
        results = []
        
        for pct_change in price_changes:
            new_price = price * Decimal(str(1 + pct_change / 100))
            
            # Calculate demand change using elasticity
            volume_pct_change = pct_change * elasticity
            new_volume = volume * Decimal(str(1 + volume_pct_change / 100))
            
            result = self.run_scenario(
                name=f"Price {'+' if pct_change >= 0 else ''}{pct_change}%",
                changes={
                    "price": new_price,
                    "volume": new_volume,
                },
                scenario_type=ScenarioType.PRICING,
                assumptions=[
                    Assumption(name="Price change", value=pct_change, is_percentage=True),
                    Assumption(name="Elasticity", value=elasticity),
                    Assumption(name="Volume change", value=volume_pct_change, is_percentage=True),
                ],
            )
            results.append(result)
        
        return results
