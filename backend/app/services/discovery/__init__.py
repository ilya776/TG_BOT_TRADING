"""
Discovery Services
Multi-source whale discovery from CEX leaderboards and on-chain data.
"""

from app.services.discovery.onchain.etherscan import EtherscanDiscovery
from app.services.discovery.onchain.swap_detector import SwapDetector, SwapInfo

__all__ = [
    "EtherscanDiscovery",
    "SwapDetector",
    "SwapInfo",
]
