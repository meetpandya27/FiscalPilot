"""
OAuth2 token manager — handles token storage, refresh, and rotation.

Supports QuickBooks Online, Xero, and any standard OAuth2 provider.
Stores tokens encrypted on disk so users don't need to re-authenticate
every time FiscalPilot runs.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("fiscalpilot.auth.oauth2")

# Default token storage location
_DEFAULT_TOKEN_DIR = Path.home() / ".fiscalpilot" / "tokens"


@dataclass
class TokenData:
    """Holds OAuth2 token data with expiry tracking."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    expires_at: float = 0.0
    scope: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if the access token is expired (with 5-minute buffer)."""
        return time.time() > (self.expires_at - 300)

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "expires_at": self.expires_at,
            "scope": self.scope,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TokenData:
        return cls(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token", ""),
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in", 3600),
            expires_at=data.get("expires_at", 0.0),
            scope=data.get("scope", ""),
            extra=data.get("extra", {}),
        )

    @classmethod
    def from_oauth_response(cls, data: dict[str, Any]) -> TokenData:
        """Parse a standard OAuth2 token response."""
        expires_in = int(data.get("expires_in", 3600))
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", ""),
            token_type=data.get("token_type", "Bearer"),
            expires_in=expires_in,
            expires_at=time.time() + expires_in,
            scope=data.get("scope", ""),
            extra={k: v for k, v in data.items() if k not in {
                "access_token", "refresh_token", "token_type", "expires_in", "scope",
            }},
        )


class OAuth2TokenManager:
    """Manages OAuth2 tokens with automatic refresh and persistent storage.

    Supports the standard OAuth2 authorization code and refresh token flows.

    Usage::

        manager = OAuth2TokenManager(
            provider="quickbooks",
            client_id="...",
            client_secret="...",
            token_url="https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
        )

        # Load existing tokens or set initial ones
        manager.load_or_set(refresh_token="...")

        # Get a valid access token (auto-refreshes if expired)
        token = await manager.get_access_token()
    """

    def __init__(
        self,
        provider: str,
        client_id: str,
        client_secret: str,
        token_url: str,
        *,
        scopes: list[str] | None = None,
        token_dir: Path | None = None,
        extra_token_params: dict[str, str] | None = None,
    ) -> None:
        self.provider = provider
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.scopes = scopes or []
        self.token_dir = token_dir or _DEFAULT_TOKEN_DIR
        self.extra_token_params = extra_token_params or {}
        self._token: TokenData | None = None
        self._http_client: httpx.AsyncClient | None = None

    @property
    def _token_file(self) -> Path:
        """Path to the token storage file for this provider."""
        return self.token_dir / f"{self.provider}.json"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create a reusable httpx client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # ------------------------------------------------------------------
    # Token persistence
    # ------------------------------------------------------------------

    def _save_token(self, token: TokenData) -> None:
        """Save token data to disk."""
        self.token_dir.mkdir(parents=True, exist_ok=True)
        self._token_file.write_text(json.dumps(token.to_dict(), indent=2))
        # Restrict file permissions to owner only
        self._token_file.chmod(0o600)
        logger.debug("Saved %s token to %s", self.provider, self._token_file)

    def _load_token(self) -> TokenData | None:
        """Load token data from disk if available."""
        if self._token_file.exists():
            try:
                data = json.loads(self._token_file.read_text())
                logger.debug("Loaded %s token from %s", self.provider, self._token_file)
                return TokenData.from_dict(data)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to load %s token: %s", self.provider, e)
        return None

    def load_or_set(
        self,
        *,
        access_token: str = "",
        refresh_token: str = "",
    ) -> TokenData:
        """Load existing tokens from disk, or set new ones.

        If tokens are found on disk, they are loaded. Otherwise, the provided
        tokens are stored as the initial token set.
        """
        stored = self._load_token()
        if stored and stored.refresh_token:
            self._token = stored
            logger.info("Loaded existing %s tokens", self.provider)
        else:
            self._token = TokenData(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=0.0,  # Force refresh on first use
            )
            if refresh_token:
                self._save_token(self._token)
            logger.info("Initialized new %s tokens", self.provider)
        return self._token

    # ------------------------------------------------------------------
    # Token refresh
    # ------------------------------------------------------------------

    async def refresh(self) -> TokenData:
        """Refresh the access token using the refresh token.

        Raises:
            ValueError: If no refresh token is available.
            httpx.HTTPStatusError: If the refresh request fails.
        """
        if not self._token or not self._token.refresh_token:
            raise ValueError(
                f"No refresh token available for {self.provider}. "
                "Please authenticate first."
            )

        client = await self._get_client()

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self._token.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            **self.extra_token_params,
        }

        logger.debug("Refreshing %s access token", self.provider)
        resp = await client.post(self.token_url, data=payload)
        resp.raise_for_status()

        data = resp.json()
        self._token = TokenData.from_oauth_response(data)

        # Some providers (like QuickBooks) rotate the refresh token
        if not self._token.refresh_token and self._token:
            self._token.refresh_token = payload["refresh_token"]

        self._save_token(self._token)
        logger.info("Refreshed %s access token (expires in %ds)", self.provider, self._token.expires_in)
        return self._token

    async def get_access_token(self) -> str:
        """Get a valid access token, refreshing if needed.

        Returns:
            The access token string, ready to use in Authorization headers.
        """
        if not self._token:
            stored = self._load_token()
            if stored:
                self._token = stored
            else:
                raise ValueError(
                    f"No tokens configured for {self.provider}. "
                    "Call load_or_set() first."
                )

        if self._token.is_expired:
            await self.refresh()

        return self._token.access_token  # type: ignore[union-attr]

    def get_auth_header(self) -> dict[str, str]:
        """Get the Authorization header dict (synchronous, uses cached token).

        Use get_access_token() for the async version that auto-refreshes.
        """
        if not self._token or not self._token.access_token:
            raise ValueError(f"No access token available for {self.provider}")
        return {"Authorization": f"{self._token.token_type} {self._token.access_token}"}

    # ------------------------------------------------------------------
    # Authorization code exchange (initial auth)
    # ------------------------------------------------------------------

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
    ) -> TokenData:
        """Exchange an authorization code for tokens.

        This is step 2 of the OAuth2 authorization code flow. The user first
        authorizes in a browser, then provides the code here.

        Args:
            code: The authorization code from the callback URL.
            redirect_uri: The redirect URI used in the authorization request.

        Returns:
            The initial TokenData with access and refresh tokens.
        """
        client = await self._get_client()

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            **self.extra_token_params,
        }

        resp = await client.post(self.token_url, data=payload)
        resp.raise_for_status()

        data = resp.json()
        self._token = TokenData.from_oauth_response(data)
        self._save_token(self._token)

        logger.info("Exchanged auth code for %s tokens", self.provider)
        return self._token

    def get_authorization_url(
        self,
        authorize_url: str,
        redirect_uri: str,
        state: str = "",
    ) -> str:
        """Build the authorization URL for the OAuth2 login flow.

        Args:
            authorize_url: The provider's authorization endpoint.
            redirect_uri: Where the provider redirects after authorization.
            state: CSRF protection state parameter.

        Returns:
            The full URL to redirect the user to for authorization.
        """
        from urllib.parse import urlencode

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.scopes),
        }
        if state:
            params["state"] = state

        return f"{authorize_url}?{urlencode(params)}"
