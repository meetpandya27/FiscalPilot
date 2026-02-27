"""
Company profile model — describes the business being audited.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CompanySize(str, Enum):
    """Company size classification."""

    MICRO = "micro"  # < $500K revenue (food truck, freelancer)
    SMALL = "small"  # $500K – $5M (restaurant, small shop)
    MEDIUM = "medium"  # $5M – $100M
    LARGE = "large"  # $100M – $1B
    ENTERPRISE = "enterprise"  # $1B+


class Industry(str, Enum):
    """Industry classification."""

    RESTAURANT = "restaurant"
    RETAIL = "retail"
    ECOMMERCE = "ecommerce"
    SAAS = "saas"
    MANUFACTURING = "manufacturing"
    HEALTHCARE = "healthcare"
    CONSTRUCTION = "construction"
    PROFESSIONAL_SERVICES = "professional_services"
    NONPROFIT = "nonprofit"
    REAL_ESTATE = "real_estate"
    LOGISTICS = "logistics"
    EDUCATION = "education"
    FINANCIAL_SERVICES = "financial_services"
    OTHER = "other"


class CompanyProfile(BaseModel):
    """Profile of the company being audited.

    This tells FiscalPilot what kind of business it's working with,
    so it can apply industry-specific heuristics and benchmarks.
    """

    name: str = Field(description="Company or business name")
    industry: Industry = Field(default=Industry.OTHER)
    size: CompanySize = Field(default=CompanySize.SMALL)
    annual_revenue: float | None = Field(default=None, description="Annual revenue in base currency")
    employee_count: int | None = Field(default=None)
    country: str = Field(default="US")
    currency: str = Field(default="USD")
    fiscal_year_start_month: int = Field(default=1, ge=1, le=12)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def size_label(self) -> str:
        """Human-readable size label."""
        labels = {
            CompanySize.MICRO: "Micro Business",
            CompanySize.SMALL: "Small Business",
            CompanySize.MEDIUM: "Mid-Market",
            CompanySize.LARGE: "Large Enterprise",
            CompanySize.ENTERPRISE: "Fortune 500 / Global Enterprise",
        }
        return labels.get(self.size, "Business")
