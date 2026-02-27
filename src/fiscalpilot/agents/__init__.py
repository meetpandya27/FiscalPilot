"""Agents package — LLM-powered financial reasoning agents."""
from fiscalpilot.agents.base import BaseAgent
from fiscalpilot.agents.coordinator import CoordinatorAgent
from fiscalpilot.agents.cost_cutter import CostCutterAgent
from fiscalpilot.agents.cost_optimizer import CostOptimizerAgent
from fiscalpilot.agents.margin_optimizer import MarginOptimizerAgent
from fiscalpilot.agents.restaurant import RestaurantAgent, create_restaurant_agent
from fiscalpilot.agents.revenue_analyzer import RevenueAnalyzerAgent
from fiscalpilot.agents.risk_detector import RiskDetectorAgent
from fiscalpilot.agents.vendor_auditor import VendorAuditorAgent

__all__ = [
    "BaseAgent",
    "CoordinatorAgent",
    "CostCutterAgent",
    "CostOptimizerAgent",
    "MarginOptimizerAgent",
    "RestaurantAgent",
    "RevenueAnalyzerAgent",
    "RiskDetectorAgent",
    "VendorAuditorAgent",
    "create_restaurant_agent",
]