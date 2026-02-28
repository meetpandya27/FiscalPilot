"""
OAuth2 token manager — handles token storage, refresh, and rotation.

Supports QuickBooks Online, Xero, and any standard OAuth2 provider.
Stores tokens encrypted on disk so users don't need to re-authenticate
every time FiscalPilot runs.

Features:
- PKCE (Proof Key for Code Exchange) for enhanced security
- Local callback server for browser-based OAuth flows
- Automatic token refresh with configurable buffer
- Encrypted token storage (AES-GCM via cryptography)
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import secrets
import socket
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("fiscalpilot.auth.oauth2")


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

def _get_encryption_key() -> bytes:
    """Derive an encryption key from machine-specific data.
    
    Uses a combination of hostname and a stored salt to derive a key.
    This provides basic protection - tokens are only readable on the
    same machine where they were stored.
    """
    key_file = Path.home() / ".fiscalpilot" / ".key_salt"
    
    if key_file.exists():
        salt = key_file.read_bytes()
    else:
        salt = os.urandom(16)
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(salt)
        key_file.chmod(0o600)
    
    # Use hostname as part of the key derivation (machine-binding)
    password = socket.gethostname().encode() + b"fiscalpilot-v1"
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key


def _encrypt_data(data: str) -> str:
    """Encrypt a string using Fernet (AES-128-CBC)."""
    f = Fernet(_get_encryption_key())
    return f.encrypt(data.encode()).decode()


def _decrypt_data(encrypted: str) -> str:
    """Decrypt a Fernet-encrypted string."""
    f = Fernet(_get_encryption_key())
    return f.decrypt(encrypted.encode()).decode()


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

def generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge pair.
    
    Returns:
        Tuple of (code_verifier, code_challenge) for OAuth2 PKCE flow.
    """
    # Generate a random 43-128 character code verifier
    code_verifier = secrets.token_urlsafe(64)[:128]
    
    # Create SHA256 hash and base64url encode (without padding)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    
    return code_verifier, code_challenge


# ---------------------------------------------------------------------------
# Local callback server
# ---------------------------------------------------------------------------

class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth2 callback."""
    
    auth_code: str | None = None
    auth_state: str | None = None
    error: str | None = None
    realm_id: str | None = None  # QuickBooks-specific
    
    def do_GET(self) -> None:
        """Handle the OAuth callback GET request."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        # Extract auth code or error
        if "code" in params:
            _OAuthCallbackHandler.auth_code = params["code"][0]
            _OAuthCallbackHandler.auth_state = params.get("state", [None])[0]
            _OAuthCallbackHandler.realm_id = params.get("realmId", [None])[0]
            self._send_success_page()
        elif "error" in params:
            _OAuthCallbackHandler.error = params.get("error_description", params["error"])[0]
            self._send_error_page(_OAuthCallbackHandler.error)
        else:
            self._send_error_page("No authorization code received")
    
    def _send_success_page(self) -> None:
        """Send a success HTML page."""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>FiscalPilot - Connected!</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; 
                       display: flex; justify-content: center; align-items: center;
                       height: 100vh; margin: 0; background: #f0fdf4; }
                .card { background: white; padding: 40px; border-radius: 12px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; }
                h1 { color: #16a34a; margin-bottom: 10px; }
                p { color: #666; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>✅ Connected!</h1>
                <p>You can close this window and return to FiscalPilot.</p>
            </div>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())
    
    def _send_error_page(self, error: str) -> None:
        """Send an error HTML page."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>FiscalPilot - Error</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; 
                       display: flex; justify-content: center; align-items: center;
                       height: 100vh; margin: 0; background: #fef2f2; }}
                .card {{ background: white; padding: 40px; border-radius: 12px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; }}
                h1 {{ color: #dc2626; margin-bottom: 10px; }}
                p {{ color: #666; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>❌ Connection Failed</h1>
                <p>{error}</p>
                <p>Please try again or contact support.</p>
            </div>
        </body>
        </html>
        """
        self.send_response(400)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())
    
    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging."""
        pass


class OAuthCallbackServer:
    """Local HTTP server to capture OAuth2 callback.
    
    Usage::
    
        server = OAuthCallbackServer(port=8080)
        redirect_uri = server.get_redirect_uri()
        # ... redirect user to auth URL with redirect_uri ...
        result = await server.wait_for_callback(timeout=300)
        # result = {"code": "...", "state": "...", "realm_id": "..."}
    """
    
    def __init__(self, port: int = 8080) -> None:
        self.port = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
    
    def get_redirect_uri(self) -> str:
        """Get the redirect URI for this callback server."""
        return f"http://localhost:{self.port}/callback"
    
    def start(self) -> None:
        """Start the callback server in a background thread."""
        # Reset state
        _OAuthCallbackHandler.auth_code = None
        _OAuthCallbackHandler.auth_state = None
        _OAuthCallbackHandler.error = None
        _OAuthCallbackHandler.realm_id = None
        
        self._server = HTTPServer(("localhost", self.port), _OAuthCallbackHandler)
        self._thread = threading.Thread(target=self._server.handle_request, daemon=True)
        self._thread.start()
        logger.debug("OAuth callback server started on port %d", self.port)
    
    def stop(self) -> None:
        """Stop the callback server."""
        if self._server:
            self._server.server_close()
            self._server = None
        logger.debug("OAuth callback server stopped")
    
    async def wait_for_callback(self, timeout: float = 300) -> dict[str, str | None]:
        """Wait for the OAuth callback with timeout.
        
        Args:
            timeout: Maximum seconds to wait for callback.
            
        Returns:
            Dict with 'code', 'state', 'realm_id' (if QuickBooks), or 'error'.
            
        Raises:
            TimeoutError: If callback not received within timeout.
        """
        start = time.time()
        
        while time.time() - start < timeout:
            if _OAuthCallbackHandler.auth_code:
                return {
                    "code": _OAuthCallbackHandler.auth_code,
                    "state": _OAuthCallbackHandler.auth_state,
                    "realm_id": _OAuthCallbackHandler.realm_id,
                }
            if _OAuthCallbackHandler.error:
                return {"error": _OAuthCallbackHandler.error}
            
            await asyncio.sleep(0.5)
        
        raise TimeoutError(f"OAuth callback not received within {timeout}s")

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
    # Token persistence (encrypted)
    # ------------------------------------------------------------------

    def _save_token(self, token: TokenData, *, encrypt: bool = True) -> None:
        """Save token data to disk with optional encryption."""
        self.token_dir.mkdir(parents=True, exist_ok=True)
        
        data_json = json.dumps(token.to_dict(), indent=2)
        
        if encrypt:
            try:
                encrypted = _encrypt_data(data_json)
                self._token_file.write_text(encrypted)
            except Exception as e:
                logger.warning("Encryption failed, saving unencrypted: %s", e)
                self._token_file.write_text(data_json)
        else:
            self._token_file.write_text(data_json)
        
        # Restrict file permissions to owner only
        self._token_file.chmod(0o600)
        logger.debug("Saved %s token to %s", self.provider, self._token_file)

    def _load_token(self) -> TokenData | None:
        """Load token data from disk (handles both encrypted and plain)."""
        if not self._token_file.exists():
            return None
        
        content = self._token_file.read_text()
        
        # Try to decrypt first (it might be encrypted)
        try:
            decrypted = _decrypt_data(content)
            data = json.loads(decrypted)
            logger.debug("Loaded encrypted %s token from %s", self.provider, self._token_file)
            return TokenData.from_dict(data)
        except Exception:
            pass
        
        # Fall back to plain JSON (backward compatibility)
        try:
            data = json.loads(content)
            logger.debug("Loaded plain %s token from %s", self.provider, self._token_file)
            # Re-save with encryption for next time
            token = TokenData.from_dict(data)
            self._save_token(token)
            return token
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to load %s token: %s", self.provider, e)
        
        return None
    
    def delete_token(self) -> bool:
        """Delete stored token for this provider.
        
        Returns:
            True if token was deleted, False if no token existed.
        """
        if self._token_file.exists():
            self._token_file.unlink()
            self._token = None
            logger.info("Deleted %s token", self.provider)
            return True
        return False
    
    def has_token(self) -> bool:
        """Check if a token is stored for this provider."""
        return self._token_file.exists()

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
        *,
        code_verifier: str | None = None,
    ) -> TokenData:
        """Exchange an authorization code for tokens.

        This is step 2 of the OAuth2 authorization code flow. The user first
        authorizes in a browser, then provides the code here.

        Args:
            code: The authorization code from the callback URL.
            redirect_uri: The redirect URI used in the authorization request.
            code_verifier: PKCE code verifier (if PKCE was used).

        Returns:
            The initial TokenData with access and refresh tokens.
        """
        client = await self._get_client()

        payload: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            **self.extra_token_params,
        }
        
        if code_verifier:
            payload["code_verifier"] = code_verifier

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
        *,
        code_challenge: str | None = None,
        extra_params: dict[str, str] | None = None,
    ) -> str:
        """Build the authorization URL for the OAuth2 login flow.

        Args:
            authorize_url: The provider's authorization endpoint.
            redirect_uri: Where the provider redirects after authorization.
            state: CSRF protection state parameter.
            code_challenge: PKCE code challenge (SHA256 hash of code_verifier).
            extra_params: Additional provider-specific parameters.

        Returns:
            The full URL to redirect the user to for authorization.
        """
        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.scopes),
        }
        
        if state:
            params["state"] = state
        
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        
        if extra_params:
            params.update(extra_params)

        return f"{authorize_url}?{urlencode(params)}"
    
    # ------------------------------------------------------------------
    # Interactive browser flow
    # ------------------------------------------------------------------
    
    async def authorize_interactive(
        self,
        authorize_url: str,
        *,
        port: int = 8080,
        timeout: float = 300,
        use_pkce: bool = True,
        extra_params: dict[str, str] | None = None,
        open_browser: bool = True,
    ) -> dict[str, Any]:
        """Complete interactive OAuth2 flow via browser.
        
        Opens user's browser to authorize, then captures callback.
        
        Args:
            authorize_url: The provider's authorization endpoint.
            port: Local port for callback server (default 8080).
            timeout: Seconds to wait for user to complete auth.
            use_pkce: Enable PKCE for enhanced security.
            extra_params: Additional provider-specific URL parameters.
            open_browser: Automatically open browser (set False for testing).
        
        Returns:
            Dict with 'token' (TokenData) and optionally 'realm_id' for QuickBooks.
            
        Raises:
            TimeoutError: If user doesn't complete auth in time.
            ValueError: If authorization fails.
        """
        # Generate PKCE if enabled
        code_verifier: str | None = None
        code_challenge: str | None = None
        if use_pkce:
            code_verifier, code_challenge = generate_pkce_pair()
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Start callback server
        server = OAuthCallbackServer(port=port)
        redirect_uri = server.get_redirect_uri()
        server.start()
        
        try:
            # Build and open authorization URL
            auth_url = self.get_authorization_url(
                authorize_url=authorize_url,
                redirect_uri=redirect_uri,
                state=state,
                code_challenge=code_challenge,
                extra_params=extra_params,
            )
            
            logger.info("Opening browser for %s authorization", self.provider)
            
            if open_browser:
                webbrowser.open(auth_url)
            
            # Wait for callback
            result = await server.wait_for_callback(timeout=timeout)
            
            if "error" in result:
                raise ValueError(f"Authorization failed: {result['error']}")
            
            # Verify state
            if result.get("state") != state:
                raise ValueError("State mismatch - possible CSRF attack")
            
            # Exchange code for tokens
            token = await self.exchange_code(
                code=result["code"],  # type: ignore
                redirect_uri=redirect_uri,
                code_verifier=code_verifier,
            )
            
            return {
                "token": token,
                "realm_id": result.get("realm_id"),  # QuickBooks-specific
            }
            
        finally:
            server.stop()
