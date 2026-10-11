"""
src/agronomy/vlm_critic.py
Track 2 / Task 2.1: Multimodal VLM critic (System-2).
Verified default model: Qwen/Qwen2.5-VL-7B-Instruct.
Provides Pydantic schema validation for diagnoses and robust JSON parsing.
mock_mode=True returns a deterministic diagnosis so the pipeline runs on CPU laptops / CI.
"""
import json
import logging
import re
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from PIL import Image

logger = logging.getLogger("agriagent.vlm_critic")

# Verified Hugging Face / vLLM model repository
DEFAULT_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"

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

    def __init__(self, model_name: str = DEFAULT_MODEL, mock_mode: bool = False):
        self.model_name = model_name
        self.mock_mode = mock_mode
        self.model = None
        self.processor = None

    def _load(self):
        try:
            from transformers import AutoModelForImageTextToText, AutoProcessor
            self.processor = AutoProcessor.from_pretrained(self.model_name)
            self.model = AutoModelForImageTextToText.from_pretrained(
                self.model_name, torch_dtype="auto", device_map="auto"
            )
        except Exception as exc:
            logger.error("Failed to load VLM model %s: %s", self.model_name, exc)
            raise

    def diagnose(self, image: Image.Image, crop_hint: Optional[str] = None) -> Dict[str, Any]:
        if self.mock_mode:
            return dict(MOCK_RESULT)
        if self.model is None:
            self._load()
        ctx = f" (crop reported by farmer: {crop_hint})" if crop_hint else ""
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": DIAGNOSIS_PROMPT.format(ctx=ctx)},
            ],
        }]
        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.model.device)
        out = self.model.generate(**inputs, max_new_tokens=256)
        text = self.processor.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
        return parse_json(text)
