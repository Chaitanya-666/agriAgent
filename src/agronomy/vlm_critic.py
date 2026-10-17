"""
src/agronomy/vlm_critic.py
Track 2 / Task 2.1: Multimodal VLM critic (System-2).
Default back-end: Groq qwen/qwen3.8-27b (cloud, sees the image). The local llama-server
provider is used only when passed in explicitly (team decision, 17 Oct).
Provides Pydantic schema validation for diagnoses and robust JSON parsing.
mock_mode=True returns a deterministic diagnosis so the pipeline runs on CPU laptops / CI.
"""
import json
import logging
import os
import re
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from PIL import Image
from src.agronomy.provider_contract import BaseAgronomyProvider, LLMRequest
from src.agronomy.providers.hosted_groq import DEFAULT_GROQ_MODEL, HostedGroqProvider

logger = logging.getLogger("agriagent.vlm_critic")

# Groq model identifier; GROQ_MODEL_NAME in .env overrides it.
DEFAULT_MODEL = DEFAULT_GROQ_MODEL

DIAGNOSIS_PROMPT = (
    "You are an expert Indian agronomist. Look at this field photo"
    "{ctx}. Identify the crop, the dominant weed or disease, the crop growth stage "
    "(seedling / vegetative / flowering / boll-formation / maturity) and the severity. "
    'Reply ONLY with JSON: {{"crop": str, "weed_or_disease": str, "crop_stage": str, '
    '"severity": "low|medium|high", "explanation": str}}'
)

MOCK_RESULT = {
    "crop": "cotton",
    "weed_or_disease": "Parthenium hysterophorus",
    "crop_stage": "vegetative",
    "severity": "medium",
    "explanation": "[MOCK] Broadleaf weed canopy competing with young cotton.",
}


class VLMDiagnosis(BaseModel):
    """Pydantic schema contract for agronomist visual diagnosis."""
    model_config = ConfigDict(extra="allow")

    crop: str = "cotton"
    weed_or_disease: str = "Parthenium hysterophorus"
    crop_stage: str = "vegetative"
    severity: Literal["low", "medium", "high"] = "medium"
    explanation: str = ""


def parse_json(text: str) -> Dict[str, Any]:
    """
    Robust JSON parser using markdown fence stripping and Pydantic validation.
    Falls back to explanation and parse_error=True on failure.
    """
    cleaned = text.strip()

    # Strip markdown code blocks if present
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        json_candidate = fence_match.group(1)
    else:
        # Match braces
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not m:
            return {"explanation": cleaned, "parse_error": True}
        json_candidate = m.group(0)

    try:
        data = json.loads(json_candidate)
        if isinstance(data, dict):
            # Validate via Pydantic schema
            diag = VLMDiagnosis.model_validate(data)
            return diag.model_dump()
        return {"explanation": cleaned, "parse_error": True}
    except (json.JSONDecodeError, ValidationError):
        return {"explanation": cleaned, "parse_error": True}


class VLMCritic:
    """Multimodal System-2 agronomist critic evaluating field imagery."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        mock_mode: bool = False,
        provider: Optional[BaseAgronomyProvider] = None,
    ):
        self.model_name = model_name or os.getenv("GROQ_MODEL_NAME") or DEFAULT_MODEL
        self.mock_mode = mock_mode
        self.provider = provider or HostedGroqProvider(
            model_name=self.model_name,
            mock_mode=mock_mode,
        )

    def diagnose(self, image: Image.Image, crop_hint: Optional[str] = None) -> Dict[str, Any]:
        if self.mock_mode:
            return dict(MOCK_RESULT)
        ctx = f" (crop reported by farmer: {crop_hint})" if crop_hint else ""
        response = self.provider.generate(
            LLMRequest(
                system_prompt="Return an evidence-based crop and weed diagnosis as JSON.",
                user_prompt=DIAGNOSIS_PROMPT.format(ctx=ctx),
                image=image,
            )
        )
        if response.error:
            raise RuntimeError(f"VLM diagnosis failed ({response.provider}): {response.error}")
        if response.parsed_json is not None:
            diagnosis = VLMDiagnosis.model_validate(response.parsed_json)
            return diagnosis.model_dump()
        return parse_json(response.text_content)
