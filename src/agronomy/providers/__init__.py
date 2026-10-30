"""
src/agronomy/providers/__init__.py
Agronomy LLM / VLM Providers package.

reasoning_provider() picks the cloud reasoning model from REASONING_PROVIDER in .env:
"cloudflare" (default since 30 October 2026) or "groq" (the earlier provider, kept but off).
"""

import os

from src.agronomy.provider_contract import BaseAgronomyProvider
from src.agronomy.providers.hosted_cloudflare import HostedCloudflareProvider
from src.agronomy.providers.hosted_groq import HostedGroqProvider
from src.agronomy.providers.local_qwen import LocalQwenProvider

REASONING_PROVIDERS = ("cloudflare", "groq")


def reasoning_provider(mock_mode: bool = False) -> BaseAgronomyProvider:
    """The configured reasoning provider; mock mode always uses the Groq adapter's canned reply."""
    choice = os.getenv("REASONING_PROVIDER", "cloudflare").strip().lower()
    if mock_mode or choice == "groq":
        return HostedGroqProvider(mock_mode=mock_mode)
    if choice != "cloudflare":
        raise ValueError(f"REASONING_PROVIDER must be one of {REASONING_PROVIDERS}, not {choice!r}")
    return HostedCloudflareProvider()


__all__ = [
    "HostedCloudflareProvider",
    "HostedGroqProvider",
    "LocalQwenProvider",
    "REASONING_PROVIDERS",
    "reasoning_provider",
]
