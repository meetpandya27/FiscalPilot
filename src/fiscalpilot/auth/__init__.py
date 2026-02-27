"""
FiscalPilot authentication and token management.

Provides OAuth2 flows, token storage, and automatic refresh for
accounting platform integrations (QuickBooks, Xero, etc.).
"""

from fiscalpilot.auth.oauth2 import OAuth2TokenManager, TokenData

__all__ = ["OAuth2TokenManager", "TokenData"]
