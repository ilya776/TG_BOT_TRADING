"""Base Query class для CQRS pattern.

Query - запит на отримання даних (read operation).
Queries НЕ мають side effects (не змінюють дані).
"""

from abc import ABC
from dataclasses import dataclass


@dataclass(frozen=True)
class Query(ABC):
    """Base class для всіх queries.

    Query характеристики:
    - **Read-only**: Не змінює дані, тільки читає
    - **Noun-based naming**: GetUserTrades, GetOpenPositions (не Query suffix)
    - **Cacheable**: Можна cache результати (бо no side effects)
    - **Fast**: Queries мають бути швидкими (use indexes, materialized views)

    Example:
        >>> @dataclass(frozen=True)
        ... class GetUserTradesQuery(Query):
        ...     user_id: int
        ...     status: TradeStatus | None = None
        ...     limit: int = 100

        >>> query = GetUserTradesQuery(user_id=456, status=TradeStatus.FILLED)
        >>> trades = await handler.handle(query)

    CQRS Benefits:
        - **Separation**: Read model ≠ Write model (different optimization strategies)
        - **Scalability**: Queries можуть use read replicas, caches
        - **Simplicity**: Handlers simpler (either read OR write, not both)
    """

    pass
