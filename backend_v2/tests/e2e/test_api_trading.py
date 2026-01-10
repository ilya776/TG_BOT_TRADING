"""E2E tests for Trading API endpoints.

Tests повного flow:
1. Execute copy trade
2. Close position
3. Error handling
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Create test client
client = TestClient(app)


class TestTradingAPI:
    """E2E tests для Trading API."""

    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "2.0.0"

    def test_root_endpoint(self):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["version"] == "2.0.0"
        assert data["docs"] == "/docs"

    def test_execute_copy_trade_unauthorized(self):
        """Test execute copy trade без Authorization header."""
        # Missing Authorization header
        response = client.post(
            "/api/v1/trading/trades",
            json={
                "signal_id": 100,
                "exchange_name": "binance",
                "symbol": "BTCUSDT",
                "side": "buy",
                "trade_type": "spot",
                "size_usdt": 1000.00,
                "leverage": 1,
            },
        )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_execute_copy_trade_invalid_request(self):
        """Test execute copy trade з invalid parameters."""
        # Invalid size_usdt (negative)
        response = client.post(
            "/api/v1/trading/trades",
            headers={"Authorization": "Bearer user_id=1"},
            json={
                "signal_id": 100,
                "exchange_name": "binance",
                "symbol": "BTCUSDT",
                "side": "buy",
                "trade_type": "spot",
                "size_usdt": -1000.00,  # Invalid!
                "leverage": 1,
            },
        )

        assert response.status_code == 422  # Validation error
        data = response.json()
        assert data["error"] == "ValidationError"

    def test_execute_copy_trade_invalid_side(self):
        """Test execute copy trade з invalid side."""
        response = client.post(
            "/api/v1/trading/trades",
            headers={"Authorization": "Bearer user_id=1"},
            json={
                "signal_id": 100,
                "exchange_name": "binance",
                "symbol": "BTCUSDT",
                "side": "invalid",  # Invalid side
                "trade_type": "spot",
                "size_usdt": 1000.00,
                "leverage": 1,
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "ValidationError"

    def test_execute_copy_trade_invalid_exchange(self):
        """Test execute copy trade з unsupported exchange."""
        response = client.post(
            "/api/v1/trading/trades",
            headers={"Authorization": "Bearer user_id=1"},
            json={
                "signal_id": 100,
                "exchange_name": "unsupported_exchange",  # Invalid
                "symbol": "BTCUSDT",
                "side": "buy",
                "trade_type": "spot",
                "size_usdt": 1000.00,
                "leverage": 1,
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "ValidationError"

    @pytest.mark.skip(
        reason="Requires real exchange credentials and DB setup"
    )
    def test_execute_copy_trade_success(self):
        """Test successful copy trade execution.

        Note:
            Skipped by default - потребує:
            - Real exchange API credentials
            - Database setup
            - Valid signal_id
        """
        response = client.post(
            "/api/v1/trading/trades",
            headers={"Authorization": "Bearer user_id=1"},
            json={
                "signal_id": 100,
                "exchange_name": "binance",
                "symbol": "BTCUSDT",
                "side": "buy",
                "trade_type": "spot",
                "size_usdt": 1000.00,
                "leverage": 1,
                "stop_loss_percentage": 5.0,
                "take_profit_percentage": 10.0,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == 1
        assert data["symbol"] == "BTCUSDT"
        assert data["side"] == "buy"
        assert data["status"] in ("pending", "filled")

    def test_close_position_unauthorized(self):
        """Test close position без Authorization header."""
        response = client.post(
            "/api/v1/trading/positions/123/close",
            json={"position_id": 123, "exchange_name": "binance"},
        )

        assert response.status_code == 401

    def test_close_position_path_mismatch(self):
        """Test close position з mismatch між URL path та body."""
        response = client.post(
            "/api/v1/trading/positions/123/close",
            headers={"Authorization": "Bearer user_id=1"},
            json={
                "position_id": 456,  # Different from URL!
                "exchange_name": "binance",
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert "doesn't match" in data["detail"]["message"].lower()

    @pytest.mark.skip(reason="Requires DB setup and existing position")
    def test_close_position_success(self):
        """Test successful position close.

        Note:
            Skipped by default - потребує:
            - Database setup
            - Existing open position
            - Exchange credentials
        """
        response = client.post(
            "/api/v1/trading/positions/123/close",
            headers={"Authorization": "Bearer user_id=1"},
            json={"position_id": 123, "exchange_name": "binance"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 123
        assert data["status"] == "closed"
        assert data["realized_pnl"] is not None


class TestOpenAPISchema:
    """Test OpenAPI schema generation."""

    def test_openapi_schema(self):
        """Test що OpenAPI schema генерується правильно."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        assert schema["openapi"] == "3.1.0"
        assert schema["info"]["title"] == "Copy Trading Backend v2"
        assert schema["info"]["version"] == "2.0.0"

        # Check що routes існують
        paths = schema["paths"]
        assert "/health" in paths
        assert "/api/v1/trading/trades" in paths
        assert "/api/v1/trading/positions/{position_id}/close" in paths

    def test_docs_endpoint(self):
        """Test що Swagger UI доступний."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_endpoint(self):
        """Test що ReDoc доступний."""
        response = client.get("/redoc")
        assert response.status_code == 200
