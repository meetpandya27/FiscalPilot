"""Tests for the OAuth2 token manager."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fiscalpilot.auth.oauth2 import OAuth2TokenManager, TokenData


# ---------------------------------------------------------------------------
# TokenData tests
# ---------------------------------------------------------------------------


class TestTokenData:
    def test_from_oauth_response(self) -> None:
        data = {
            "access_token": "abc123",
            "refresh_token": "ref456",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "read write",
            "x_refresh_token_expires_in": 8726400,
        }
        token = TokenData.from_oauth_response(data)
        assert token.access_token == "abc123"
        assert token.refresh_token == "ref456"
        assert token.expires_in == 3600
        assert token.scope == "read write"
        assert token.extra["x_refresh_token_expires_in"] == 8726400
        assert not token.is_expired

    def test_is_expired_true(self) -> None:
        token = TokenData(
            access_token="abc",
            refresh_token="ref",
            expires_at=time.time() - 100,
        )
        assert token.is_expired

    def test_is_expired_within_buffer(self) -> None:
        # Token expires in 4 minutes (< 5 min buffer)
        token = TokenData(
            access_token="abc",
            refresh_token="ref",
            expires_at=time.time() + 240,
        )
        assert token.is_expired

    def test_is_expired_false(self) -> None:
        token = TokenData(
            access_token="abc",
            refresh_token="ref",
            expires_at=time.time() + 3600,
        )
        assert not token.is_expired

    def test_round_trip(self) -> None:
        original = TokenData(
            access_token="abc",
            refresh_token="ref",
            token_type="Bearer",
            expires_in=3600,
            expires_at=time.time() + 3600,
            scope="accounting",
            extra={"realm_id": "123"},
        )
        restored = TokenData.from_dict(original.to_dict())
        assert restored.access_token == original.access_token
        assert restored.refresh_token == original.refresh_token
        assert restored.scope == original.scope
        assert restored.extra == original.extra


# ---------------------------------------------------------------------------
# OAuth2TokenManager tests
# ---------------------------------------------------------------------------


class TestOAuth2TokenManager:
    def _make_manager(self, token_dir: Path) -> OAuth2TokenManager:
        return OAuth2TokenManager(
            provider="test_provider",
            client_id="test_client",
            client_secret="test_secret",
            token_url="https://example.com/oauth/token",
            token_dir=token_dir,
        )

    def test_load_or_set_new(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)
        token = mgr.load_or_set(refresh_token="new_refresh")
        assert token.refresh_token == "new_refresh"
        # Should be saved to disk
        token_file = tmp_path / "test_provider.json"
        assert token_file.exists()
        data = json.loads(token_file.read_text())
        assert data["refresh_token"] == "new_refresh"

    def test_load_or_set_existing(self, tmp_path: Path) -> None:
        # Pre-seed a token file
        token_file = tmp_path / "test_provider.json"
        token_file.write_text(json.dumps({
            "access_token": "old_access",
            "refresh_token": "old_refresh",
            "expires_at": time.time() + 3600,
        }))

        mgr = self._make_manager(tmp_path)
        token = mgr.load_or_set(refresh_token="should_be_ignored")
        assert token.refresh_token == "old_refresh"

    def test_get_auth_header(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)
        mgr.load_or_set(access_token="my_token", refresh_token="my_refresh")
        # Force set a non-expired token
        mgr._token = TokenData(
            access_token="my_token",
            refresh_token="my_refresh",
            expires_at=time.time() + 3600,
        )
        header = mgr.get_auth_header()
        assert header == {"Authorization": "Bearer my_token"}

    def test_get_authorization_url(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)
        url = mgr.get_authorization_url(
            authorize_url="https://example.com/authorize",
            redirect_uri="https://myapp.com/callback",
            state="abc123",
        )
        assert "https://example.com/authorize?" in url
        assert "client_id=test_client" in url
        assert "redirect_uri=" in url
        assert "state=abc123" in url
        assert "response_type=code" in url

    @pytest.mark.asyncio
    async def test_refresh(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)
        mgr.load_or_set(refresh_token="old_refresh")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False

        mgr._http_client = mock_client

        token = await mgr.refresh()
        assert token.access_token == "new_access"
        assert token.refresh_token == "new_refresh"

        # Verify the POST was called correctly
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "https://example.com/oauth/token"
        post_data = call_kwargs[1]["data"]
        assert post_data["grant_type"] == "refresh_token"
        assert post_data["refresh_token"] == "old_refresh"

    @pytest.mark.asyncio
    async def test_get_access_token_valid(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)
        mgr._token = TokenData(
            access_token="valid_token",
            refresh_token="ref",
            expires_at=time.time() + 3600,
        )
        token = await mgr.get_access_token()
        assert token == "valid_token"

    @pytest.mark.asyncio
    async def test_get_access_token_expired_triggers_refresh(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)
        mgr._token = TokenData(
            access_token="expired_token",
            refresh_token="ref",
            expires_at=time.time() - 100,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "refreshed_token",
            "refresh_token": "new_ref",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False
        mgr._http_client = mock_client

        token = await mgr.get_access_token()
        assert token == "refreshed_token"

    @pytest.mark.asyncio
    async def test_exchange_code(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "code_access",
            "refresh_token": "code_refresh",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False
        mgr._http_client = mock_client

        token = await mgr.exchange_code("auth_code_123", "https://myapp.com/callback")
        assert token.access_token == "code_access"
        assert token.refresh_token == "code_refresh"

        # Verify saved to disk
        token_file = tmp_path / "test_provider.json"
        assert token_file.exists()

    @pytest.mark.asyncio
    async def test_no_tokens_raises(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)
        with pytest.raises(ValueError, match="No tokens configured"):
            await mgr.get_access_token()
