"""
src/agronomy/provider_contract.py
Unified LLM / VLM Provider Interface for AgriAgent System-2 Reasoning.
Conforms strictly to PROJECT.md Section 3 Interface Contracts.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class LLMRequest(BaseModel):
    """Unified request model for LLM/VLM inference."""
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    system_prompt: str = ""
    user_prompt: str
    image: Optional[Any] = None  # PIL.Image, numpy array, bytes, or None
    temperature: float = 0.0
    timeout_seconds: float = 30.0


class LLMResponse(BaseModel):
    """Unified response model for LLM/VLM inference."""
    model_config = ConfigDict(extra="allow")

    provider: str
    model_name: str
    text_content: str
    parsed_json: Optional[Dict[str, Any]] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    error: Optional[str] = None


class BaseAgronomyProvider(ABC):
    """Abstract base class for agronomy deliberation providers."""

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Execute inference against the LLM/VLM backend.
        Must return structured LLMResponse with parsed_json, latency, and token metrics.
        """
        pass
