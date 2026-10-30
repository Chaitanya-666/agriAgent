"""
src/agronomy/providers/hosted_cloudflare.py
Cloudflare Workers AI provider for the reasoning model (the default since 30 October 2026).
Default model: @cf/qwen/qwen3.8-27b, the same Qwen model we used on Groq, so results carry over.

Why Cloudflare: Groq's free tier allows about 8,000 tokens per minute, and one app run (System 2,
the agent's checks, the farmer summary) used most of it, so bursts failed with 429. Cloudflare
counts a daily allowance (10,000 neurons on the free plan) instead of a per-minute one. Uses the
OpenAI-compatible endpoint, so the request shape matches the Groq provider.
"""

import logging
import os
import time
from typing import Any, Dict, Optional

import requests

from src.agronomy.provider_contract import BaseAgronomyProvider, LLMRequest, LLMResponse
from src.agronomy.providers.local_qwen import extract_json, image_to_base64_url

logger = logging.getLogger("agriagent.providers.hosted_cloudflare")

CLOUDFLARE_ENDPOINT = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1/chat/completions"
DEFAULT_CLOUDFLARE_MODEL = "@cf/qwen/qwen3.8-27b"


class HostedCloudflareProvider(BaseAgronomyProvider):
    """Reasoning model on Cloudflare Workers AI; keys from CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN."""

    def __init__(
        self,
        account_id: Optional[str] = None,
        api_token: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.account_id = account_id or os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
        self.api_token = api_token or os.getenv("CLOUDFLARE_API_TOKEN", "")
        self.model_name: str = (
            model_name or os.getenv("CLOUDFLARE_REASONING_MODEL") or DEFAULT_CLOUDFLARE_MODEL
        )

    def _failure(self, start_time: float, error: str) -> LLMResponse:
        return LLMResponse(
            provider="hosted_cloudflare",
            model_name=self.model_name,
            text_content="",
            parsed_json=None,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=(time.time() - start_time) * 1000.0,
            error=error,
        )

    def generate(self, request: LLMRequest) -> LLMResponse:
        start_time = time.time()
        if not self.account_id or not self.api_token:
            return self._failure(
                start_time, "CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN are required (see .env.example)."
            )

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        user_content: Any = request.user_prompt
        img_url = image_to_base64_url(request.image)
        if img_url:
            user_content = [
                {"type": "image_url", "image_url": {"url": img_url}},
                {"type": "text", "text": request.user_prompt},
            ]
        messages.append({"role": "user", "content": user_content})

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": 1024,
        }
        if "qwen" in self.model_name:
            # Qwen 3 thinks out loud by default. Cloudflare rejects Groq's reasoning_effort "none";
            # the chat-template switch turns thinking off instead (checked 30 Oct 2026).
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        if "json" in f"{request.system_prompt} {request.user_prompt}".lower():
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = requests.post(
                CLOUDFLARE_ENDPOINT.format(account=self.account_id),
                headers={"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"},
                json=payload,
                timeout=request.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
            usage = data.get("usage", {})
            return LLMResponse(
                provider="hosted_cloudflare",
                model_name=self.model_name,
                text_content=text,
                parsed_json=extract_json(text),
                prompt_tokens=usage.get("prompt_tokens", len(request.user_prompt) // 4),
                completion_tokens=usage.get("completion_tokens", len(text) // 4),
                latency_ms=(time.time() - start_time) * 1000.0,
            )
        except Exception as exc:
            logger.warning("HostedCloudflareProvider request failed: %s", exc)
            return self._failure(start_time, str(exc))
