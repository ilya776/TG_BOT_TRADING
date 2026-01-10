"""Signal Source - origin of trading signal."""

from enum import Enum


class SignalSource(str, Enum):
    """Source of trading signal.

    Sources:
        - WHALE: Signal from whale copy trading (most common)
        - INDICATOR: Signal from technical indicator
        - MANUAL: Manually created signal by user
        - BOT: Signal from trading bot/algorithm
        - WEBHOOK: Signal from external webhook
    """

    WHALE = "whale"
    INDICATOR = "indicator"
    MANUAL = "manual"
    BOT = "bot"
    WEBHOOK = "webhook"

    def is_automated(self) -> bool:
        """Check if source is automated (not manual).

        Returns:
            True if source is WHALE, INDICATOR, BOT, or WEBHOOK.
        """
        return self != SignalSource.MANUAL

    def requires_validation(self) -> bool:
        """Check if signal from this source requires validation.

        Returns:
            True if source is WEBHOOK or MANUAL (untrusted sources).
        """
        return self in (SignalSource.WEBHOOK, SignalSource.MANUAL)
