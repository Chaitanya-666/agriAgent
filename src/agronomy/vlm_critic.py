"""
src/agronomy/vlm_critic.py
Track 2 / Task 2.1: Multimodal VLM critic (System-2). Default: Qwen3-VL-2B-Instruct.
mock_mode=True returns a deterministic diagnosis so the pipeline runs on CPU laptops / CI.
"""
import json
import re
from typing import Any, Dict, Optional

from PIL import Image

DEFAULT_MODEL = "Qwen/Qwen3-VL-2B-Instruct"

DIAGNOSIS_PROMPT = (
    "You are an expert Indian agronomist. Look at this field photo"
    "{ctx}. Identify the crop, the dominant weed or disease, the crop growth stage "
    "(seedling / vegetative / flowering / boll-formation / maturity) and the severity. "
    'Reply ONLY with JSON: {{"crop": str, "weed_or_disease": str, "crop_stage": str, '
    '"severity": "low|medium|high", "explanation": str}}'
)

MOCK_RESULT = {
    "crop": "cotton", "weed_or_disease": "Parthenium hysterophorus",
    "crop_stage": "vegetative", "severity": "medium",
    "explanation": "[MOCK] Broadleaf weed canopy competing with young cotton.",
}


def parse_json(text: str) -> Dict[str, Any]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"explanation": text.strip(), "parse_error": True}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"explanation": text.strip(), "parse_error": True}


class VLMCritic:
    def __init__(self, model_name: str = DEFAULT_MODEL, mock_mode: bool = False):
        self.model_name, self.mock_mode = model_name, mock_mode
        self.model = self.processor = None

    def _load(self):
        from transformers import AutoModelForImageTextToText, AutoProcessor
        self.processor = AutoProcessor.from_pretrained(self.model_name)
        self.model = AutoModelForImageTextToText.from_pretrained(
            self.model_name, torch_dtype="auto", device_map="auto")

    def diagnose(self, image: Image.Image, crop_hint: Optional[str] = None) -> Dict[str, Any]:
        if self.mock_mode:
            return dict(MOCK_RESULT)
        if self.model is None:
            self._load()
        ctx = f" (crop reported by farmer: {crop_hint})" if crop_hint else ""
        messages = [{"role": "user", "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": DIAGNOSIS_PROMPT.format(ctx=ctx)}]}]
        inputs = self.processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True,
            return_dict=True, return_tensors="pt").to(self.model.device)
        out = self.model.generate(**inputs, max_new_tokens=256)
        text = self.processor.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
        return parse_json(text)
