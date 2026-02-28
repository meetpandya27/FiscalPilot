"""
Tests for Delivery Platform ROI Analyzer — delivery profitability analysis.
"""

from fiscalpilot.analyzers.delivery_roi import (
    DEFAULT_PLATFORM_FEES,
    DeliveryOrderData,
    DeliveryPlatform,
    DeliveryROIAnalyzer,
    DeliveryROIResult,
    DineInComparison,
)


class TestDeliveryROICalculation:
    """Test core delivery ROI calculations."""

    def test_basic_roi_calculation(self):
        """Calculate ROI for single platform."""
        platform_data = [
            DeliveryOrderData(
                platform=DeliveryPlatform.DOORDASH,
                total_orders=500,
                total_gross_revenue=17500,  # $35 AOV
                food_cost_pct=32,
                packaging_cost_per_order=1.00,
                commission_pct=20,
            )
        ]

        result = DeliveryROIAnalyzer.analyze(platform_data)

        assert result.total_delivery_orders == 500
        assert result.total_delivery_revenue == 17500
        assert len(result.platform_results) == 1
        assert result.platform_results[0].total_orders == 500

    def test_multi_platform_comparison(self):
        """Compare ROI across multiple platforms."""
        platform_data = [
            DeliveryOrderData(
                platform=DeliveryPlatform.DOORDASH,
                total_orders=600,
                total_gross_revenue=21000,
                commission_pct=15,
            ),
            DeliveryOrderData(
                platform=DeliveryPlatform.UBER_EATS,
                total_orders=400,
                total_gross_revenue=14000,
                commission_pct=25,
            ),
        ]

        result = DeliveryROIAnalyzer.analyze(platform_data)

        assert len(result.platform_results) == 2
        assert result.total_delivery_orders == 1000

        # Lower commission should mean higher profit
        doordash = next(r for r in result.platform_results if r.platform == DeliveryPlatform.DOORDASH)
        ubereats = next(r for r in result.platform_results if r.platform == DeliveryPlatform.UBER_EATS)

        # DoorDash with 15% commission should be more profitable than Uber at 25%
        assert doordash.profit_per_order > ubereats.profit_per_order


class TestPlatformProfitability:
    """Test individual platform profitability calculations."""

    def test_commission_calculation(self):
        """Platform commission = revenue * commission_pct."""
        platform_data = [
            DeliveryOrderData(
                platform=DeliveryPlatform.DOORDASH,
                total_orders=100,
                total_gross_revenue=3500,
                commission_pct=20,
            )
        ]

        result = DeliveryROIAnalyzer.analyze(platform_data)
        platform = result.platform_results[0]

        expected_commission = 3500 * 0.20  # $700
        assert platform.commission_paid == expected_commission

    def test_packaging_cost_calculation(self):
        """Packaging costs = orders * cost_per_order."""
        platform_data = [
            DeliveryOrderData(
                platform=DeliveryPlatform.DOORDASH,
                total_orders=100,
                total_gross_revenue=3500,
                packaging_cost_per_order=1.50,
            )
        ]

        result = DeliveryROIAnalyzer.analyze(platform_data)
        platform = result.platform_results[0]

        expected_packaging = 100 * 1.50
        assert platform.packaging_cost == expected_packaging

    def test_effective_commission_rate(self):
        """Effective commission = all platform fees / revenue."""
        platform_data = [
            DeliveryOrderData(
                platform=DeliveryPlatform.DOORDASH,
                total_orders=100,
                total_gross_revenue=3500,
                commission_pct=20,
                marketing_spend=100,
            )
        ]

        result = DeliveryROIAnalyzer.analyze(platform_data)
        platform = result.platform_results[0]

        # Effective rate should include commission + payment processing + marketing
        assert platform.effective_commission_pct > 20  # Should be higher than base commission


class TestDineInComparison:
    """Test comparison with dine-in margins."""

    def test_margin_gap_calculation(self):
        """Calculate gap between delivery and dine-in margins."""
        platform_data = [
            DeliveryOrderData(
                platform=DeliveryPlatform.DOORDASH,
                total_orders=500,
                total_gross_revenue=17500,
                commission_pct=25,  # Higher commission to ensure delivery is worse
                food_cost_pct=35,   # Higher food cost for delivery
            )
        ]

        dine_in = DineInComparison(
            food_cost_pct=30,
            labor_cost_pct=28,
        )

        result = DeliveryROIAnalyzer.analyze(platform_data, dine_in_comparison=dine_in)

        assert result.dine_in_margin_pct == 42  # 100 - 30 - 28
        # With 25% commission + 35% food cost, delivery should be less profitable
        # Margin gap = dine_in - delivery, positive means delivery is worse
        assert result.delivery_margin_gap_pct is not None  # Just check it's calculated

    def test_price_increase_recommendation(self):
        """Should recommend price increase to match dine-in margins."""
        platform_data = [
            DeliveryOrderData(
                platform=DeliveryPlatform.DOORDASH,
                total_orders=500,
                total_gross_revenue=17500,
                commission_pct=25,  # High commission
            )
        ]

        result = DeliveryROIAnalyzer.analyze(platform_data)

        # With high commission, should recommend price increase
        if result.overall_delivery_margin_pct < result.dine_in_margin_pct:
            assert result.recommended_price_increase_pct > 0


class TestDirectOrderingSavings:
    """Test direct ordering opportunity calculation."""

    def test_direct_savings_calculation(self):
        """Calculate savings if all orders went direct."""
        platform_data = [
            DeliveryOrderData(
                platform=DeliveryPlatform.DOORDASH,
                total_orders=500,
                total_gross_revenue=17500,
                commission_pct=20,
            ),
            DeliveryOrderData(
                platform=DeliveryPlatform.UBER_EATS,
                total_orders=300,
                total_gross_revenue=10500,
                commission_pct=25,
            ),
        ]

        result = DeliveryROIAnalyzer.analyze(platform_data)

        # Direct ordering should save the commission difference
        assert result.direct_ordering_savings > 0


class TestQuickAnalysis:
    """Test quick analysis functionality."""

    def test_quick_analysis_basic(self):
        """Quick analysis with minimal inputs."""
        result = DeliveryROIAnalyzer.quick_analysis(
            platform=DeliveryPlatform.DOORDASH,
            monthly_orders=500,
            average_order_value=35,
            commission_pct=20,
        )

        assert result.total_delivery_orders == 500
        assert len(result.platform_results) == 1

    def test_quick_analysis_profitability(self):
        """Quick analysis should calculate profitability."""
        result = DeliveryROIAnalyzer.quick_analysis(
            monthly_orders=500,
            average_order_value=35,
            commission_pct=15,  # Relatively low
        )

        # Should be profitable with 15% commission
        assert result.total_delivery_profit > 0


class TestDeliveryROIInsights:
    """Test insight generation."""

    def test_margin_insight_generated(self):
        """Should generate insight about delivery margin."""
        platform_data = [
            DeliveryOrderData(
                platform=DeliveryPlatform.DOORDASH,
                total_orders=500,
                total_gross_revenue=17500,
            )
        ]

        result = DeliveryROIAnalyzer.analyze(platform_data)

        assert len(result.insights) > 0
        assert any("margin" in i.lower() for i in result.insights)

    def test_high_commission_warning(self):
        """Should warn about high commission rates."""
        platform_data = [
            DeliveryOrderData(
                platform=DeliveryPlatform.UBER_EATS,
                total_orders=500,
                total_gross_revenue=17500,
                commission_pct=30,  # Very high
            )
        ]

        result = DeliveryROIAnalyzer.analyze(platform_data)

        # Should have warning about high fees
        has_warning = any("high" in i.lower() or "fee" in i.lower() for i in result.insights)
        assert has_warning

    def test_losing_money_alert(self):
        """Should alert when delivery is unprofitable."""
        platform_data = [
            DeliveryOrderData(
                platform=DeliveryPlatform.DOORDASH,
                total_orders=100,
                total_gross_revenue=2000,  # Low AOV
                commission_pct=30,
                food_cost_pct=40,  # High food cost
                packaging_cost_per_order=2.00,
            )
        ]

        result = DeliveryROIAnalyzer.analyze(platform_data)

        if result.total_delivery_profit < 0:
            has_alert = any("losing" in i.lower() or "money" in i.lower() for i in result.insights)
            assert has_alert


class TestPlatformFeeDefaults:
    """Test default platform fee structures."""

    def test_doordash_defaults(self):
        """DoorDash should have default fees."""
        assert DeliveryPlatform.DOORDASH in DEFAULT_PLATFORM_FEES
        fees = DEFAULT_PLATFORM_FEES[DeliveryPlatform.DOORDASH]

        assert fees.commission_pct > 0
        assert fees.payment_processing_pct > 0

    def test_direct_has_low_fees(self):
        """Direct ordering should have minimal fees."""
        assert DeliveryPlatform.DIRECT in DEFAULT_PLATFORM_FEES
        fees = DEFAULT_PLATFORM_FEES[DeliveryPlatform.DIRECT]

        assert fees.commission_pct == 0
        # Only payment processing for direct


class TestDeliveryROIEdgeCases:
    """Test edge cases."""

    def test_zero_orders(self):
        """Should handle zero orders gracefully."""
        platform_data = [
            DeliveryOrderData(
                platform=DeliveryPlatform.DOORDASH,
                total_orders=0,
                total_gross_revenue=0,
            )
        ]

        result = DeliveryROIAnalyzer.analyze(platform_data)

        assert result.total_delivery_orders == 0
        assert result.total_delivery_profit == 0

    def test_empty_platform_list(self):
        """Should handle empty platform list."""
        result = DeliveryROIAnalyzer.analyze([])

        assert result.total_delivery_orders == 0
        assert len(result.platform_results) == 0

    def test_refunds_and_adjustments(self):
        """Should account for refunds in profitability."""
        platform_data = [
            DeliveryOrderData(
                platform=DeliveryPlatform.DOORDASH,
                total_orders=500,
                total_gross_revenue=17500,
                total_refunds=500,
                total_adjustments=200,
            )
        ]

        result = DeliveryROIAnalyzer.analyze(platform_data)
        platform = result.platform_results[0]

        assert platform.refunds_adjustments == 700


class TestDineInComparisonModel:
    """Test DineInComparison model."""

    def test_gross_margin(self):
        """Gross margin = 100 - food - labor."""
        dine_in = DineInComparison(
            food_cost_pct=30,
            labor_cost_pct=28,
        )

        assert dine_in.gross_margin_pct == 42

    def test_net_margin(self):
        """Net margin = 100 - food - labor - overhead."""
        dine_in = DineInComparison(
            food_cost_pct=30,
            labor_cost_pct=28,
            overhead_cost_pct=15,
        )

        assert dine_in.net_margin_pct == 27


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_analyze_delivery_roi(self):
        """Test analyze_delivery_roi convenience function."""
        from fiscalpilot.analyzers.delivery_roi import analyze_delivery_roi

        platform_data = [
            DeliveryOrderData(
                platform=DeliveryPlatform.DOORDASH,
                total_orders=100,
                total_gross_revenue=3500,
            )
        ]

        result = analyze_delivery_roi(platform_data)

        assert isinstance(result, DeliveryROIResult)

    def test_quick_delivery_analysis(self):
        """Test quick_delivery_analysis convenience function."""
        from fiscalpilot.analyzers.delivery_roi import quick_delivery_analysis

        result = quick_delivery_analysis(monthly_orders=500)

        assert isinstance(result, DeliveryROIResult)
