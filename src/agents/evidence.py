"""
src/agents/evidence.py
Evidence sources for "is this plant crop or weed?", used by the escalation agent (T1.7) and
by scripts/compare_crop_or_weed.py (T2.2).

Each source looks at one plant (its box in the full photo) and returns an Evidence record:
a verdict ("crop", "weed" or None when it cannot tell), a confidence in [0, 1] for that verdict,
and its cost in calls. The sources only advise; the deterministic gate decides what is sprayed.
"""

import base64
import io
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import requests
from PIL import Image

from src.agronomy.provider_contract import LLMRequest
from src.agronomy.provider_contract import BaseAgronomyProvider
from src.agronomy.providers import reasoning_provider
from src.evaluation.crop_protection import vegetation_mask

logger = logging.getLogger("agriagent.evidence")


@dataclass
class Evidence:
    source: str
    verdict: Optional[str]  # "crop", "weed" or None
    confidence: float  # confidence in the verdict, 0 when there is none
    cost: int
    detail: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


def cut_patch(image: Image.Image, box: List[float], long_side: int = 384) -> Image.Image:
    """The box plus a 15% margin (at least 64 px), scaled so the long side is long_side px."""
    x1, y1, x2, y2 = box
    mx = max(0.15 * (x2 - x1), (64 - (x2 - x1)) / 2)
    my = max(0.15 * (y2 - y1), (64 - (y2 - y1)) / 2)
    crop = image.crop(
        (max(0, x1 - mx), max(0, y1 - my), min(image.width, x2 + mx), min(image.height, y2 + my))
    )
    scale = long_side / max(crop.size)
    return crop.resize((max(1, round(crop.width * scale)), max(1, round(crop.height * scale))))


def data_url(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


class RowRuleEvidence:
    """
    No model: crops are sown in rows, so a plant whose centre lies on the densest vegetation
    band of the whole photo is called crop, anything off that band weed. Abstains when the
    photo shows no clear rows (close-ups).
    """

    name = "row_rule"
    cost = 0

    def __init__(self, min_peakiness: float = 2.0, confidence: float = 0.6):
        self.min_peakiness = min_peakiness
        self.confidence = confidence

    def __call__(self, image: Image.Image, box: List[float], crop: str) -> Evidence:
        vegetation = vegetation_mask(np.asarray(image.convert("RGB")))
        best = None
        for axis, orientation in ((1, "horizontal"), (0, "vertical")):
            profile = np.convolve(vegetation.sum(axis=axis), np.ones(15) / 15, mode="same")
            peakiness = profile.max() / (profile.mean() + 1e-6)
            if best is None or peakiness > best[0]:
                best = (peakiness, orientation, profile)
        assert best is not None
        peakiness, orientation, profile = best
        if peakiness < self.min_peakiness:
            return Evidence(
                self.name, None, 0.0, self.cost, f"no clear rows (peakiness {peakiness:.1f})"
            )
        centre = (box[1] + box[3]) / 2 if orientation == "horizontal" else (box[0] + box[2]) / 2
        on_row = profile[int(min(max(centre, 0), len(profile) - 1))] >= 0.5 * profile.max()
        return Evidence(
            self.name,
            "crop" if on_row else "weed",
            self.confidence,
            self.cost,
            f"{orientation} rows, peakiness {peakiness:.1f}, plant {'on' if on_row else 'off'} the row",
        )


class ClefEvidence:
    """Cloudflare Workers AI Clef Flash: a 'choice' question with the plant patch as image."""

    name = "clef_flash"
    cost = 1

    def __init__(self, timeout: float = 60.0):
        self.account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
        self.token = os.getenv("CLOUDFLARE_API_TOKEN", "")
        self.timeout = timeout

    def __call__(self, image: Image.Image, box: List[float], crop: str) -> Evidence:
        if not self.account or not self.token:
            return Evidence(
                self.name, None, 0.0, 0, "CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN not set"
            )
        url = f"https://api.cloudflare.com/client/v4/accounts/{self.account}/ai/run/@cf/cloudflare/clef-flash"
        body: Dict[str, Any] = {
            "model": "clef-flash",
            "state": f"A close-up cut from a photo of a {crop} field.",
            "images": [data_url(cut_patch(image, box))],
            "questions": {
                "plant": {
                    "type": "choice",
                    "instructions": f"Is the plant in the centre of the image the crop ({crop}) or a weed?",
                    "criteria": {
                        "crop": f"a {crop} plant",
                        "weed": f"any plant that is not {crop}",
                    },
                }
            },
        }
        try:
            resp = requests.post(
                url,
                headers={"Authorization": f"Bearer {self.token}"},
                json=body,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            return Evidence(self.name, None, 0.0, self.cost, f"request failed: {exc}")
        if resp.status_code != 200:
            return Evidence(
                self.name, None, 0.0, self.cost, f"HTTP {resp.status_code}: {resp.text[:200]}"
            )
        answer = resp.json().get("result", {}).get("answers", {}).get("plant", {})
        choice = answer.get("choice")
        probabilities = answer.get("probabilities", {})
        if choice not in ("crop", "weed"):
            return Evidence(self.name, None, 0.0, self.cost, f"unexpected answer {answer}")
        return Evidence(
            self.name,
            choice,
            float(probabilities.get(choice, 0.5)),
            self.cost,
            f"probabilities {probabilities}",
            {"raw": answer},
        )


class QwenVlmEvidence:
    """
    Qwen vision-language model (qwen3.8-27b) on the plant patch, told the field's crop. Served by
    Cloudflare by default (REASONING_PROVIDER); until 30 Oct 2026 by Groq as "groq_vlm".
    """

    name = "qwen_vlm"
    cost = 3

    def __init__(self, provider: Optional[BaseAgronomyProvider] = None, max_retries: int = 4):
        self.provider = provider or reasoning_provider()
        self.max_retries = max_retries

    def __call__(self, image: Image.Image, box: List[float], crop: str) -> Evidence:
        prompt = (
            f"This close-up is cut from a photo of a {crop} field. Is the plant in the centre of the "
            f"image the crop ({crop}) or a weed? Reply ONLY with JSON: "
            '{"answer": "crop" or "weed", "confidence": number between 0 and 1}'
        )
        patch = cut_patch(image, box)
        for attempt in range(self.max_retries + 1):
            resp = self.provider.generate(
                LLMRequest(user_prompt=prompt, image=patch, timeout_seconds=60)
            )
            if resp.error and "429" in resp.error and attempt < self.max_retries:
                time.sleep(15 * (attempt + 1))  # Groq free tier: about 8,000 tokens per minute
                continue
            if resp.error:
                return Evidence(self.name, None, 0.0, self.cost, f"error: {resp.error}")
            parsed = resp.parsed_json or {}
            answer = str(parsed.get("answer", "")).lower()
            if answer not in ("crop", "weed"):
                return Evidence(
                    self.name, None, 0.0, self.cost, f"unparsed reply: {resp.text_content[:120]}"
                )
            try:
                confidence = min(1.0, max(0.0, float(parsed.get("confidence", 0.7))))
            except (TypeError, ValueError):
                confidence = 0.7
            return Evidence(self.name, answer, confidence, self.cost, resp.text_content[:200])
        return Evidence(self.name, None, 0.0, self.cost, "rate limited")


GroqEvidence = QwenVlmEvidence  # earlier name, kept for scripts/compare_crop_or_weed.py
