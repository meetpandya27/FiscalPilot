"""Integration tests for production-ready connectors.

These tests require real sandbox API credentials set as environment variables.
They are skipped by default in CI unless credentials are provided.

To run locally with sandbox credentials:
    export QUICKBOOKS_CLIENT_ID=xxx
    export QUICKBOOKS_CLIENT_SECRET=xxx
    export QUICKBOOKS_REALM_ID=xxx
    export QUICKBOOKS_REFRESH_TOKEN=xxx

    export XERO_CLIENT_ID=xxx
    export XERO_CLIENT_SECRET=xxx
    export XERO_TENANT_ID=xxx
    export XERO_REFRESH_TOKEN=xxx

    export PLAID_CLIENT_ID=xxx
    export PLAID_SECRET=xxx
    export PLAID_ACCESS_TOKEN=xxx

    export SQUARE_ACCESS_TOKEN=xxx
    export SQUARE_LOCATION_ID=xxx

    pytest tests/test_integration.py -v --integration
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

from fiscalpilot.models.company import CompanyProfile, Industry


# Custom marker for integration tests
def pytest_configure(config):
    config.addinivalue_line("markers", "integration: marks tests as integration tests (require credentials)")


# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------


@pytest.fixture
def company_profile() -> CompanyProfile:
    """Standard test company profile."""
    return CompanyProfile(
        name="Integration Test Co",
        industry=Industry.RESTAURANT,
    )


@pytest.fixture
def date_range() -> tuple[datetime, datetime]:
    """Default date range for transaction pulls (last 90 days)."""
    end = datetime.now()
    start = end - timedelta(days=90)
    return start, end


# -------------------------------------------------------------------------
# Skip helpers
# -------------------------------------------------------------------------


def skip_unless_env(*env_vars: str) -> pytest.MarkDecorator:
    """Skip test if any environment variable is missing."""
    missing = [v for v in env_vars if not os.getenv(v)]
    return pytest.mark.skipif(
        len(missing) > 0,
        reason=f"Missing environment variables: {', '.join(missing)}",
    )


# Skip decorators for each provider
requires_quickbooks = skip_unless_env(
    "QUICKBOOKS_CLIENT_ID",
    "QUICKBOOKS_CLIENT_SECRET",
    "QUICKBOOKS_REALM_ID",
    "QUICKBOOKS_REFRESH_TOKEN",
)

requires_xero = skip_unless_env(
    "XERO_CLIENT_ID",
    "XERO_CLIENT_SECRET",
    "XERO_TENANT_ID",
    "XERO_REFRESH_TOKEN",
)

requires_plaid = skip_unless_env(
    "PLAID_CLIENT_ID",
    "PLAID_SECRET",
    "PLAID_ACCESS_TOKEN",
)

requires_square = skip_unless_env(
    "SQUARE_ACCESS_TOKEN",
)


# -------------------------------------------------------------------------
# QuickBooks Integration Tests
# -------------------------------------------------------------------------


@pytest.mark.integration
class TestQuickBooksIntegration:
    """Integration tests for QuickBooks connector."""

    @requires_quickbooks
    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        """Test QuickBooks sandbox health check."""
        from fiscalpilot.connectors.quickbooks_connector import QuickBooksConnector

        connector = QuickBooksConnector(
            credentials={
                "client_id": os.environ["QUICKBOOKS_CLIENT_ID"],
                "client_secret": os.environ["QUICKBOOKS_CLIENT_SECRET"],
                "realm_id": os.environ["QUICKBOOKS_REALM_ID"],
                "refresh_token": os.environ["QUICKBOOKS_REFRESH_TOKEN"],
            },
            sandbox=True,
        )

        result = await connector.health_check()
        await connector.close()

        assert result["healthy"] is True
        assert "company_name" in result

    @requires_quickbooks
    @pytest.mark.asyncio
    async def test_pull_transactions(
        self, company_profile: CompanyProfile, date_range: tuple[datetime, datetime]
    ) -> None:
        """Test pulling transactions from QuickBooks sandbox."""
        from fiscalpilot.connectors.quickbooks_connector import QuickBooksConnector

        connector = QuickBooksConnector(
            credentials={
                "client_id": os.environ["QUICKBOOKS_CLIENT_ID"],
                "client_secret": os.environ["QUICKBOOKS_CLIENT_SECRET"],
                "realm_id": os.environ["QUICKBOOKS_REALM_ID"],
                "refresh_token": os.environ["QUICKBOOKS_REFRESH_TOKEN"],
            },
            sandbox=True,
        )

        start, end = date_range
        dataset = await connector.pull(company_profile, start_date=start, end_date=end)
        await connector.close()

        # Should return a valid dataset
        assert dataset is not None
        assert dataset.company_name == company_profile.name
        # Sandbox may have 0 transactions, but should not error
        assert isinstance(dataset.transactions, list)

    @requires_quickbooks
    @pytest.mark.asyncio
    async def test_accounts_list(self) -> None:
        """Test listing accounts from QuickBooks sandbox."""
        from fiscalpilot.connectors.quickbooks_connector import QuickBooksConnector

        connector = QuickBooksConnector(
            credentials={
                "client_id": os.environ["QUICKBOOKS_CLIENT_ID"],
                "client_secret": os.environ["QUICKBOOKS_CLIENT_SECRET"],
                "realm_id": os.environ["QUICKBOOKS_REALM_ID"],
                "refresh_token": os.environ["QUICKBOOKS_REFRESH_TOKEN"],
            },
            sandbox=True,
        )

        accounts = await connector.get_accounts()
        await connector.close()

        # Sandbox should have at least some accounts
        assert isinstance(accounts, list)


# -------------------------------------------------------------------------
# Xero Integration Tests
# -------------------------------------------------------------------------


@pytest.mark.integration
class TestXeroIntegration:
    """Integration tests for Xero connector."""

    @requires_xero
    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        """Test Xero demo company health check."""
        from fiscalpilot.connectors.xero_connector import XeroConnector

        connector = XeroConnector(
            credentials={
                "client_id": os.environ["XERO_CLIENT_ID"],
                "client_secret": os.environ["XERO_CLIENT_SECRET"],
                "tenant_id": os.environ["XERO_TENANT_ID"],
                "refresh_token": os.environ["XERO_REFRESH_TOKEN"],
            },
        )

        result = await connector.health_check()
        await connector.close()

        assert result["healthy"] is True
        assert "org_name" in result

    @requires_xero
    @pytest.mark.asyncio
    async def test_pull_transactions(
        self, company_profile: CompanyProfile, date_range: tuple[datetime, datetime]
    ) -> None:
        """Test pulling transactions from Xero demo company."""
        from fiscalpilot.connectors.xero_connector import XeroConnector

        connector = XeroConnector(
            credentials={
                "client_id": os.environ["XERO_CLIENT_ID"],
                "client_secret": os.environ["XERO_CLIENT_SECRET"],
                "tenant_id": os.environ["XERO_TENANT_ID"],
                "refresh_token": os.environ["XERO_REFRESH_TOKEN"],
            },
        )

        start, end = date_range
        dataset = await connector.pull(company_profile, start_date=start, end_date=end)
        await connector.close()

        assert dataset is not None
        assert dataset.company_name == company_profile.name
        assert isinstance(dataset.transactions, list)

    @requires_xero
    @pytest.mark.asyncio
    async def test_get_organizations(self) -> None:
        """Test listing Xero organizations."""
        from fiscalpilot.connectors.xero_connector import XeroConnector

        connector = XeroConnector(
            credentials={
                "client_id": os.environ["XERO_CLIENT_ID"],
                "client_secret": os.environ["XERO_CLIENT_SECRET"],
                "tenant_id": os.environ["XERO_TENANT_ID"],
                "refresh_token": os.environ["XERO_REFRESH_TOKEN"],
            },
        )

        orgs = await connector.get_organizations()
        await connector.close()

        # Should have at least the connected org
        assert isinstance(orgs, list)
        assert len(orgs) >= 1


# -------------------------------------------------------------------------
# Plaid Integration Tests
# -------------------------------------------------------------------------


@pytest.mark.integration
class TestPlaidIntegration:
    """Integration tests for Plaid connector."""

    @requires_plaid
    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        """Test Plaid sandbox health check."""
        from fiscalpilot.connectors.plaid_connector import PlaidConnector

        connector = PlaidConnector(
            credentials={
                "client_id": os.environ["PLAID_CLIENT_ID"],
                "secret": os.environ["PLAID_SECRET"],
                "access_tokens": [os.environ["PLAID_ACCESS_TOKEN"]],
            },
            environment="sandbox",
        )

        result = await connector.health_check()
        await connector.close()

        assert result["healthy"] is True

    @requires_plaid
    @pytest.mark.asyncio
    async def test_pull_transactions(
        self, company_profile: CompanyProfile, date_range: tuple[datetime, datetime]
    ) -> None:
        """Test pulling transactions from Plaid sandbox."""
        from fiscalpilot.connectors.plaid_connector import PlaidConnector

        connector = PlaidConnector(
            credentials={
                "client_id": os.environ["PLAID_CLIENT_ID"],
                "secret": os.environ["PLAID_SECRET"],
                "access_tokens": [os.environ["PLAID_ACCESS_TOKEN"]],
            },
            environment="sandbox",
        )

        start, end = date_range
        dataset = await connector.pull(company_profile, start_date=start, end_date=end)
        await connector.close()

        assert dataset is not None
        assert isinstance(dataset.transactions, list)

    @requires_plaid
    @pytest.mark.asyncio
    async def test_create_link_token(self) -> None:
        """Test creating a Plaid Link token."""
        from fiscalpilot.connectors.plaid_connector import PlaidConnector

        connector = PlaidConnector(
            credentials={
                "client_id": os.environ["PLAID_CLIENT_ID"],
                "secret": os.environ["PLAID_SECRET"],
            },
            environment="sandbox",
        )

        link_token = await connector.create_link_token(user_id="test_user")
        await connector.close()

        assert isinstance(link_token, str)
        assert link_token.startswith("link-")

    @requires_plaid
    @pytest.mark.asyncio
    async def test_get_institutions(self) -> None:
        """Test getting connected institutions."""
        from fiscalpilot.connectors.plaid_connector import PlaidConnector

        connector = PlaidConnector(
            credentials={
                "client_id": os.environ["PLAID_CLIENT_ID"],
                "secret": os.environ["PLAID_SECRET"],
                "access_tokens": [os.environ["PLAID_ACCESS_TOKEN"]],
            },
            environment="sandbox",
        )

        institutions = await connector.get_institutions()
        await connector.close()

        assert isinstance(institutions, list)


# -------------------------------------------------------------------------
# Square Integration Tests
# -------------------------------------------------------------------------


@pytest.mark.integration
class TestSquareIntegration:
    """Integration tests for Square connector."""

    @requires_square
    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        """Test Square sandbox health check."""
        from fiscalpilot.connectors.square_connector import SquareConnector

        connector = SquareConnector(
            credentials={
                "access_token": os.environ["SQUARE_ACCESS_TOKEN"],
                "location_id": os.environ.get("SQUARE_LOCATION_ID"),
            },
            sandbox=True,
        )

        result = await connector.health_check()
        await connector.close()

        assert result["healthy"] is True

    @requires_square
    @pytest.mark.asyncio
    async def test_pull_transactions(
        self, company_profile: CompanyProfile, date_range: tuple[datetime, datetime]
    ) -> None:
        """Test pulling transactions from Square sandbox."""
        from fiscalpilot.connectors.square_connector import SquareConnector

        connector = SquareConnector(
            credentials={
                "access_token": os.environ["SQUARE_ACCESS_TOKEN"],
                "location_id": os.environ.get("SQUARE_LOCATION_ID"),
            },
            sandbox=True,
        )

        start, end = date_range
        dataset = await connector.pull(company_profile, start_date=start, end_date=end)
        await connector.close()

        assert dataset is not None
        assert isinstance(dataset.transactions, list)

    @requires_square
    @pytest.mark.asyncio
    async def test_get_locations(self) -> None:
        """Test listing Square locations."""
        from fiscalpilot.connectors.square_connector import SquareConnector

        connector = SquareConnector(
            credentials={
                "access_token": os.environ["SQUARE_ACCESS_TOKEN"],
            },
            sandbox=True,
        )

        locations = await connector.get_locations()
        await connector.close()

        assert isinstance(locations, list)


# -------------------------------------------------------------------------
# CLI Integration Tests
# -------------------------------------------------------------------------


@pytest.mark.integration
class TestCLICommands:
    """Test CLI commands work correctly."""

    def test_connections_command(self) -> None:
        """Test 'fp connections' command runs without error."""
        from typer.testing import CliRunner

        from fiscalpilot.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["connections"])

        assert result.exit_code == 0
        assert "Connected Integrations" in result.stdout

    def test_connectors_command(self) -> None:
        """Test 'fp connectors' command runs without error."""
        from typer.testing import CliRunner

        from fiscalpilot.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["connectors"])

        assert result.exit_code == 0

    def test_audit_help(self) -> None:
        """Test 'fp audit --help' shows options."""
        from typer.testing import CliRunner

        from fiscalpilot.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["audit", "--help"])

        assert result.exit_code == 0
        assert "--config" in result.stdout or "CONFIG" in result.stdout

    def test_scan_help(self) -> None:
        """Test 'fp scan --help' shows options."""
        from typer.testing import CliRunner

        from fiscalpilot.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["scan", "--help"])

        assert result.exit_code == 0


# -------------------------------------------------------------------------
# OAuth2 Flow Tests
# -------------------------------------------------------------------------


@pytest.mark.integration
class TestOAuth2Flows:
    """Test OAuth2 infrastructure."""

    def test_pkce_generation(self) -> None:
        """Test PKCE code verifier/challenge generation."""
        from fiscalpilot.auth.oauth2 import generate_pkce_pair

        verifier, challenge = generate_pkce_pair()

        # Verifier should be 43-128 chars, base64url
        assert 43 <= len(verifier) <= 128
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in verifier)

        # Challenge should be 43 chars (SHA-256 base64url)
        assert len(challenge) == 43

    def test_token_encryption(self) -> None:
        """Test token encryption/decryption roundtrip."""
        import tempfile
        from pathlib import Path

        from fiscalpilot.auth.oauth2 import OAuth2TokenManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = OAuth2TokenManager(
                provider="test",
                client_id="test-client",
                client_secret="test-secret",
                token_url="https://example.com/token",
                token_dir=Path(tmpdir),
            )

            # Create a mock token to save
            from fiscalpilot.auth.oauth2 import TokenData

            test_token = TokenData(
                access_token="test-access-token",
                token_type="Bearer",
                refresh_token="test-refresh-token",
                expires_in=3600,
            )

            # Save and load through the secure storage
            manager._save_token(test_token)
            loaded = manager._load_token()

            assert loaded is not None
            assert loaded.access_token == test_token.access_token
            assert loaded.refresh_token == test_token.refresh_token

    def test_oauth2_authorization_url(self) -> None:
        """Test OAuth2 authorization URL generation."""
        import tempfile
        from pathlib import Path

        from fiscalpilot.auth.oauth2 import OAuth2TokenManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = OAuth2TokenManager(
                provider="test",
                client_id="test-client-id",
                client_secret="test-secret",
                token_url="https://example.com/token",
                scopes=["read", "write"],
                token_dir=Path(tmpdir),
            )

            url = manager.get_authorization_url(
                authorize_url="https://example.com/authorize",
                redirect_uri="http://localhost:8080/callback",
                state="test-state",
            )

            assert "https://example.com/authorize" in url
            assert "client_id=test-client-id" in url
            assert "response_type=code" in url
            assert "redirect_uri" in url
            assert "state=test-state" in url
