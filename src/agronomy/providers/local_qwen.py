"""
src/agronomy/providers/local_qwen.py
Local Qwen inference provider connecting to an OpenAI-compatible endpoint.
Default model: Qwen/Qwen3.5-4B.
Supports structured JSON parsing, multimodal image inputs, and deterministic offline mock.
"""

import base64
import io
import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional
import requests
from PIL import Image

from src.agronomy.provider_contract import BaseAgronomyProvider, LLMRequest, LLMResponse

logger = logging.getLogger("agriagent.providers.local_qwen")

DEFAULT_LOCAL_URL = "http://127.0.0.1:8888/v1"
DEFAULT_MODEL = "Qwen/Qwen3.5-4B"

MOCK_LOCAL_RESPONSE = {
    "crop": "cotton",
    "weed_or_disease": "Parthenium hysterophorus",
    "crop_stage": "vegetative",
    "severity": "medium",
    "explanation": "[LOCAL-QWEN-MOCK] Broadleaf weed canopy competing with vegetative cotton crop.",
}


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Robustly extract structured JSON from model response text or markdown fences."""
    # Try direct parse
    try:
        return json.loads(text.strip())
    except Exception:
        pass

    # Try markdown code fences ```json ... ```
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except Exception:
            pass

    # Try finding first balanced or greedy braces
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except Exception:
            pass

    return None


MAX_IMAGE_SIDE = 768


def image_to_base64_url(image: Any) -> Optional[str]:
    """
    Convert PIL image or bytes into base64 data URL. PIL images are shrunk so the long side is at
    most MAX_IMAGE_SIDE px: a full-size phone photo cost 12,349 prompt tokens, the same photo at
    512 px 247 tokens with the same answer (measured 30 Oct 2026, finding F22).
    """
    if image is None:
        return None
    try:
        if isinstance(image, Image.Image):
            image = image.convert("RGB")
            if max(image.size) > MAX_IMAGE_SIDE:
                image = image.copy()
                image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=85)
            b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{b64_str}"
        if isinstance(image, (bytes, bytearray)):
            b64_str = base64.b64encode(image).decode("utf-8")
            return f"data:image/jpeg;base64,{b64_str}"
    except Exception as exc:
        logger.warning("Failed to encode image to base64: %s", exc)
    return None


class LocalQwenProvider(BaseAgronomyProvider):
    """
    OpenAI-compatible client for locally hosted Qwen models (vLLM, Ollama, LM Studio).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_MODEL,
        mock_mode: bool = False,
    ):
        self.base_url = (base_url or os.getenv("LOCAL_BASE_URL") or DEFAULT_LOCAL_URL).rstrip("/")
        self.api_key = api_key or os.getenv("LOCAL_API_KEY", "dummy")
        self.model_name = model_name or os.getenv("LOCAL_MODEL_NAME", DEFAULT_MODEL)
        self.mock_mode = mock_mode

    def generate(self, request: LLMRequest) -> LLMResponse:
        start_time = time.time()

        if self.mock_mode:
            latency_ms = (time.time() - start_time) * 1000.0
            return LLMResponse(
                provider="local_qwen",
                model_name=self.model_name,
                text_content=json.dumps(MOCK_LOCAL_RESPONSE),
                parsed_json=MOCK_LOCAL_RESPONSE,
                prompt_tokens=42,
                completion_tokens=35,
                latency_ms=max(1.0, latency_ms),
            )

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        user_content: Any = []
        img_url = image_to_base64_url(request.image)
        if img_url:
            user_content.append({"type": "image_url", "image_url": {"url": img_url}})
            user_content.append({"type": "text", "text": request.user_prompt})
        else:
            user_content = request.user_prompt

        messages.append({"role": "user", "content": user_content})

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": 1024,
        }

        url = f"{self.base_url}/chat/completions"
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=request.timeout_seconds,
            )
            latency_ms = (time.time() - start_time) * 1000.0
            resp.raise_for_status()
            data = resp.json()

            choice = data.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})

            parsed = extract_json(text)
            return LLMResponse(
                provider="local_qwen",
                model_name=self.model_name,
                text_content=text,
                parsed_json=parsed,
                prompt_tokens=usage.get("prompt_tokens", len(request.user_prompt) // 4),
                completion_tokens=usage.get("completion_tokens", len(text) // 4),
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = (time.time() - start_time) * 1000.0
            logger.warning("LocalQwenProvider failed (%s): %s", url, exc)
            # If server unavailable, return structured error response
            return LLMResponse(
                provider="local_qwen",
                model_name=self.model_name,
                text_content="",
                parsed_json=None,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=latency_ms,
                error=str(exc),
            )
