"""
src/agronomy/providers/hosted_groq.py
Hosted Groq API provider for fast cloud agronomic deliberation.
Default model: qwen/qwen3.8-27b.
Supports rate-limit backoff, structured output parsing, and seamless fallback provider chain.
"""
import json
import logging
import os
import time
from typing import Any, Dict, Optional
import requests

from src.agronomy.provider_contract import BaseAgronomyProvider, LLMRequest, LLMResponse
from src.agronomy.providers.local_qwen import extract_json

logger = logging.getLogger("agriagent.providers.hosted_groq")

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"

MOCK_GROQ_RESPONSE = {
    "crop": "cotton",
    "weed_or_disease": "Trianthema portulacastrum",
    "crop_stage": "vegetative",
    "severity": "high",
    "explanation": "[GROQ-HOSTED-MOCK] Severe carpetweed competition identified in cotton furrow.",
}


class HostedGroqProvider(BaseAgronomyProvider):
    """
    Hosted cloud inference provider connecting to Groq Cloud API.
    Provides structured output extraction, configurable fallback, and mock support.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        fallback_provider: Optional[BaseAgronomyProvider] = None,
        mock_mode: bool = False,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model_name = model_name or os.getenv("GROQ_MODEL_NAME", DEFAULT_GROQ_MODEL)
        self.fallback_provider = fallback_provider
        self.mock_mode = mock_mode

    def generate(self, request: LLMRequest) -> LLMResponse:
        start_time = time.time()

        if self.mock_mode:
            latency_ms = (time.time() - start_time) * 1000.0
            return LLMResponse(
                provider="hosted_groq",
                model_name=self.model_name,
                text_content=json.dumps(MOCK_GROQ_RESPONSE),
                parsed_json=MOCK_GROQ_RESPONSE,
                prompt_tokens=48,
                completion_tokens=38,
                latency_ms=max(1.0, latency_ms),
            )
        if not self.api_key:
            if self.fallback_provider:
                logger.info("GROQ_API_KEY is absent; using explicitly configured local provider.")
                return self.fallback_provider.generate(request)
            return LLMResponse(
                provider="hosted_groq",
                model_name=self.model_name,
                text_content="",
                parsed_json=None,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=(time.time() - start_time) * 1000.0,
                error="GROQ_API_KEY is required for live Groq inference; mock_mode is disabled.",
            )

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_prompt})

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": 1024,
        }

        try:
            resp = requests.post(
                GROQ_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=request.timeout_seconds,
            )
            latency_ms = (time.time() - start_time) * 1000.0

            # Handle rate-limit 429 or auth errors with fallback
            if resp.status_code in (429, 401, 503) and self.fallback_provider:
                logger.warning("Groq returned %d; triggering fallback provider.", resp.status_code)
                return self.fallback_provider.generate(request)

            resp.raise_for_status()
            data = resp.json()

            choice = data.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})
            parsed = extract_json(text)

            return LLMResponse(
                provider="hosted_groq",
                model_name=self.model_name,
                text_content=text,
                parsed_json=parsed,
                prompt_tokens=usage.get("prompt_tokens", len(request.user_prompt) // 4),
                completion_tokens=usage.get("completion_tokens", len(text) // 4),
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = (time.time() - start_time) * 1000.0
            logger.warning("HostedGroqProvider request failed: %s", exc)
            if self.fallback_provider:
                logger.info("Executing fallback provider after exception: %s", exc)
                return self.fallback_provider.generate(request)

            return LLMResponse(
                provider="hosted_groq",
                model_name=self.model_name,
                text_content="",
                parsed_json=None,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=latency_ms,
                error=str(exc),
            )
