"""Contract tests для Exchange adapters.

Перевіряємо що всі adapters (Binance, Bybit, Bitget) дотримуються ExchangePort interface.
Contract tests - це автоматична валідація що всі реалізації мають однаковий API.
"""

import inspect
from decimal import Decimal

import pytest

from app.domain.exchanges.ports import ExchangePort
from app.domain.exchanges.value_objects import Balance, OrderResult
from app.infrastructure.exchanges.adapters import BinanceAdapter, BitgetAdapter, BybitAdapter


# All exchange adapters to test
EXCHANGE_ADAPTERS = [
    BinanceAdapter,
    BybitAdapter,
    BitgetAdapter,
]


class TestExchangePortContract:
    """Test що всі adapters implement ExchangePort correctly."""

    @pytest.mark.parametrize("adapter_class", EXCHANGE_ADAPTERS)
    def test_adapter_implements_exchange_port(self, adapter_class):
        """Test: Adapter є subclass від ExchangePort."""
        assert issubclass(adapter_class, ExchangePort), (
            f"{adapter_class.__name__} must be subclass of ExchangePort"
        )

    @pytest.mark.parametrize("adapter_class", EXCHANGE_ADAPTERS)
    def test_adapter_has_all_required_methods(self, adapter_class):
        """Test: Adapter має всі методи з ExchangePort interface."""
        port_methods = {
            name
            for name, method in inspect.getmembers(ExchangePort, predicate=inspect.isfunction)
            if not name.startswith("_")
        }

        adapter_methods = {
            name
            for name, method in inspect.getmembers(adapter_class, predicate=inspect.isfunction)
            if not name.startswith("_")
        }

        missing_methods = port_methods - adapter_methods

        assert not missing_methods, (
            f"{adapter_class.__name__} missing methods: {missing_methods}"
        )

    @pytest.mark.parametrize("adapter_class", EXCHANGE_ADAPTERS)
    def test_initialize_method_signature(self, adapter_class):
        """Test: initialize() method має правильну signature."""
        method = getattr(adapter_class, "initialize")
        sig = inspect.signature(method)

        # Check return annotation
        assert sig.return_annotation == None or "None" in str(sig.return_annotation), (
            f"{adapter_class.__name__}.initialize() must return None"
        )

    @pytest.mark.parametrize("adapter_class", EXCHANGE_ADAPTERS)
    def test_execute_spot_buy_signature(self, adapter_class):
        """Test: execute_spot_buy() має правильну signature."""
        method = getattr(adapter_class, "execute_spot_buy")
        sig = inspect.signature(method)

        # Check parameters
        params = list(sig.parameters.keys())
        assert "symbol" in params, f"{adapter_class.__name__}.execute_spot_buy() missing 'symbol'"
        assert "quantity" in params, f"{adapter_class.__name__}.execute_spot_buy() missing 'quantity'"

        # Check parameter types
        assert sig.parameters["symbol"].annotation == str
        assert sig.parameters["quantity"].annotation == Decimal

        # Check return type
        assert "OrderResult" in str(sig.return_annotation), (
            f"{adapter_class.__name__}.execute_spot_buy() must return OrderResult"
        )

    @pytest.mark.parametrize("adapter_class", EXCHANGE_ADAPTERS)
    def test_execute_spot_sell_signature(self, adapter_class):
        """Test: execute_spot_sell() має правильну signature."""
        method = getattr(adapter_class, "execute_spot_sell")
        sig = inspect.signature(method)

        params = list(sig.parameters.keys())
        assert "symbol" in params
        assert "quantity" in params

        assert sig.parameters["symbol"].annotation == str
        assert sig.parameters["quantity"].annotation == Decimal
        assert "OrderResult" in str(sig.return_annotation)

    @pytest.mark.parametrize("adapter_class", EXCHANGE_ADAPTERS)
    def test_execute_futures_long_signature(self, adapter_class):
        """Test: execute_futures_long() має правильну signature."""
        method = getattr(adapter_class, "execute_futures_long")
        sig = inspect.signature(method)

        params = list(sig.parameters.keys())
        assert "symbol" in params
        assert "quantity" in params
        assert "leverage" in params

        assert sig.parameters["symbol"].annotation == str
        assert sig.parameters["quantity"].annotation == Decimal
        assert sig.parameters["leverage"].annotation == int
        assert "OrderResult" in str(sig.return_annotation)

    @pytest.mark.parametrize("adapter_class", EXCHANGE_ADAPTERS)
    def test_execute_futures_short_signature(self, adapter_class):
        """Test: execute_futures_short() має правильну signature."""
        method = getattr(adapter_class, "execute_futures_short")
        sig = inspect.signature(method)

        params = list(sig.parameters.keys())
        assert "symbol" in params
        assert "quantity" in params
        assert "leverage" in params

        assert sig.parameters["symbol"].annotation == str
        assert sig.parameters["quantity"].annotation == Decimal
        assert sig.parameters["leverage"].annotation == int
        assert "OrderResult" in str(sig.return_annotation)

    @pytest.mark.parametrize("adapter_class", EXCHANGE_ADAPTERS)
    def test_close_futures_position_signature(self, adapter_class):
        """Test: close_futures_position() має правильну signature."""
        method = getattr(adapter_class, "close_futures_position")
        sig = inspect.signature(method)

        params = list(sig.parameters.keys())
        assert "symbol" in params
        assert "position_side" in params

        assert sig.parameters["symbol"].annotation == str
        assert sig.parameters["position_side"].annotation == str
        assert "OrderResult" in str(sig.return_annotation)

    @pytest.mark.parametrize("adapter_class", EXCHANGE_ADAPTERS)
    def test_get_balances_signature(self, adapter_class):
        """Test: get_balances() має правильну signature."""
        method = getattr(adapter_class, "get_balances")
        sig = inspect.signature(method)

        # Should return list[Balance]
        assert "list" in str(sig.return_annotation) and "Balance" in str(sig.return_annotation), (
            f"{adapter_class.__name__}.get_balances() must return list[Balance]"
        )

    @pytest.mark.parametrize("adapter_class", EXCHANGE_ADAPTERS)
    def test_get_balance_signature(self, adapter_class):
        """Test: get_balance() має правильну signature."""
        method = getattr(adapter_class, "get_balance")
        sig = inspect.signature(method)

        params = list(sig.parameters.keys())
        assert "asset" in params

        assert sig.parameters["asset"].annotation == str
        assert "Balance" in str(sig.return_annotation)

    @pytest.mark.parametrize("adapter_class", EXCHANGE_ADAPTERS)
    def test_get_symbol_info_signature(self, adapter_class):
        """Test: get_symbol_info() має правильну signature."""
        method = getattr(adapter_class, "get_symbol_info")
        sig = inspect.signature(method)

        params = list(sig.parameters.keys())
        assert "symbol" in params

        assert sig.parameters["symbol"].annotation == str
        # Should return dict
        assert "dict" in str(sig.return_annotation)


class TestExchangeFactory:
    """Test ExchangeFactory."""

    def test_create_binance_adapter(self):
        """Test: Factory створює Binance adapter."""
        from app.infrastructure.exchanges.factories import ExchangeFactory

        factory = ExchangeFactory()
        adapter = factory.create_exchange(
            exchange_name="binance",
            api_key="test_key",
            api_secret="test_secret",
            testnet=True,
        )

        assert isinstance(adapter, BinanceAdapter)
        assert isinstance(adapter, ExchangePort)

    def test_create_bybit_adapter(self):
        """Test: Factory створює Bybit adapter."""
        from app.infrastructure.exchanges.factories import ExchangeFactory

        factory = ExchangeFactory()
        adapter = factory.create_exchange(
            exchange_name="bybit",
            api_key="test_key",
            api_secret="test_secret",
            testnet=True,
        )

        assert isinstance(adapter, BybitAdapter)
        assert isinstance(adapter, ExchangePort)

    def test_create_bitget_adapter(self):
        """Test: Factory створює Bitget adapter."""
        from app.infrastructure.exchanges.factories import ExchangeFactory

        factory = ExchangeFactory()
        adapter = factory.create_exchange(
            exchange_name="bitget",
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_pass",
            testnet=True,
        )

        assert isinstance(adapter, BitgetAdapter)
        assert isinstance(adapter, ExchangePort)

    def test_factory_rejects_unsupported_exchange(self):
        """Test: Factory raise error для unsupported exchange."""
        from app.infrastructure.exchanges.factories import ExchangeFactory

        factory = ExchangeFactory()

        with pytest.raises(ValueError, match="Unsupported exchange"):
            factory.create_exchange(
                exchange_name="unknown_exchange",
                api_key="key",
                api_secret="secret",
            )

    def test_factory_is_supported(self):
        """Test: Factory.is_supported() працює правильно."""
        from app.infrastructure.exchanges.factories import ExchangeFactory

        factory = ExchangeFactory()

        assert factory.is_supported("binance") is True
        assert factory.is_supported("bybit") is True
        assert factory.is_supported("bitget") is True
        assert factory.is_supported("BINANCE") is True  # Case insensitive
        assert factory.is_supported("unknown") is False

    def test_factory_get_supported_exchanges(self):
        """Test: Factory.get_supported_exchanges() повертає всі supported."""
        from app.infrastructure.exchanges.factories import ExchangeFactory

        factory = ExchangeFactory()
        supported = factory.get_supported_exchanges()

        assert "binance" in supported
        assert "bybit" in supported
        assert "bitget" in supported
        assert len(supported) == 3


class TestRetryLogic:
    """Test retry logic."""

    @pytest.mark.asyncio
    async def test_retry_decorator_retries_on_retryable_error(self):
        """Test: retry_with_backoff retries на RetryableError."""
        from app.infrastructure.exchanges.retry import RetryableError, retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        async def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("Temporary error")
            return "success"

        result = await failing_function()

        assert result == "success"
        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_retry_decorator_gives_up_after_max_retries(self):
        """Test: retry_with_backoff gives up після max_retries."""
        from app.infrastructure.exchanges.retry import RetryableError, retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        async def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise RetryableError("Always fails")

        with pytest.raises(RetryableError):
            await always_failing_function()

        assert call_count == 3  # Initial + 2 retries


class TestCircuitBreaker:
    """Test circuit breaker."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        """Test: Circuit breaker opens після threshold failures."""
        from app.infrastructure.exchanges.circuit_breakers import (
            CircuitBreaker,
            CircuitBreakerOpenError,
            CircuitState,
        )

        circuit = CircuitBreaker(failure_threshold=3, timeout_seconds=1)

        async def failing_function():
            raise Exception("API error")

        # First 3 calls should fail with Exception
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit.call(failing_function)

        # Circuit should now be OPEN
        assert circuit.state == CircuitState.OPEN

        # Next call should fail with CircuitBreakerOpenError (fast fail)
        with pytest.raises(CircuitBreakerOpenError):
            await circuit.call(failing_function)

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovers_after_success(self):
        """Test: Circuit breaker closes після успішних calls в HALF_OPEN."""
        from app.infrastructure.exchanges.circuit_breakers import CircuitBreaker, CircuitState

        circuit = CircuitBreaker(
            failure_threshold=2,
            timeout_seconds=0.1,  # Short timeout для тесту
            success_threshold=1,
        )

        call_count = 0

        async def sometimes_failing_function():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Fails first 2 times")
            return "success"

        # Fail 2 times → circuit OPEN
        for _ in range(2):
            with pytest.raises(Exception):
                await circuit.call(sometimes_failing_function)

        assert circuit.state == CircuitState.OPEN

        # Wait for timeout
        import asyncio

        await asyncio.sleep(0.15)

        # Next call should succeed → circuit HALF_OPEN → CLOSED
        result = await circuit.call(sometimes_failing_function)
        assert result == "success"
        assert circuit.state == CircuitState.CLOSED
