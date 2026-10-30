"""
src/agronomy/farmer_summary.py
A short plain-language summary of one result for a farmer, in English, Hindi or Marathi.

The facts come only from the pipeline's own output (spray map, withheld plants, the escalation
agent's verdicts, the prescription). A language model may rewrite those facts in plain words or
another language, but it never adds advice: if it fails, or mentions a dose when no prescription
exists, the deterministic English template is used instead.
"""

import logging
from typing import Any, Dict, Optional

from src.agronomy.provider_contract import BaseAgronomyProvider, LLMRequest

logger = logging.getLogger("agriagent.farmer_summary")

LANGUAGES = ("English", "Hindi", "Marathi")
DOSE_WORDS = ("g/ha", "g a.i", "ml", "litre", "liter", "kg/ha", "grams")


def build_facts(state: Dict[str, Any], crop: str, mock_mode: bool) -> Dict[str, Any]:
    spray = state.get("spray_map") or {}
    reviews = spray.get("escalation") or []
    prescription = state.get("prescription_report") or {}
    has_prescription = prescription.get("status") == "ok" and bool(
        prescription.get("active_ingredient")
    )
    return {
        "mode": "MOCK (test data, not a real result)" if mock_mode else "REAL",
        "crop": crop,
        "zones_to_spray": int(spray.get("weed_count", 0)),
        "spray_allowed": bool(spray.get("spray_allowed", False)),
        # F4: with the plant rules on, "unsure" patches are the plants left for the farmer to check;
        # withheld detector masks are mostly crop plants the gate protected (and overlap).
        "plants_unsure": (
            int(spray["plant_rules"].get("unsure", 0))
            if spray.get("plant_rules")
            else len(spray.get("withheld_masks") or [])
        ),
        "agent_weed": sum(r.get("verdict") == "weed" for r in reviews),
        "agent_crop_or_unsure": sum(r.get("verdict") != "weed" for r in reviews),
        "sprayed_area_pct": spray.get("infestation_percentage", 0.0),
        "herbicide_saved_pct": spray.get("chemical_savings_percentage", 100.0),
        "herbicide": prescription.get("active_ingredient") if has_prescription else None,
        "dose_g_per_ha": prescription.get("dosage_ai_g_per_ha") if has_prescription else None,
        "weed_named": prescription.get("target_weed") if has_prescription else None,
    }


def template_summary(facts: Dict[str, Any]) -> str:
    """Deterministic English summary built only from the facts."""
    lines = []
    if facts["mode"] != "REAL":
        lines.append("This is test data, not a real field result.")
    if not facts["spray_allowed"]:
        lines.append("Weeds cover too much of this photo for spot spraying; do not use this map.")
    elif facts["zones_to_spray"] == 0:
        lines.append(
            f"No patch in this {facts['crop']} photo is sure enough to spray, so nothing is marked."
        )
    else:
        lines.append(
            f"{facts['zones_to_spray']} weed patch(es) in this {facts['crop']} photo are marked for spraying, "
            f"about {facts['sprayed_area_pct']}% of the photo; the rest, including the crop, is left alone."
        )
    if facts["plants_unsure"]:
        lines.append(
            f"{facts['plants_unsure']} plant(s) were not sprayed because the system was unsure; "
            "check them by eye."
        )
    if facts["herbicide"]:
        lines.append(
            f"The ICAR table suggests {facts['herbicide']} at {facts['dose_g_per_ha']} g a.i./ha for "
            f"{facts['weed_named']}; read the product label before use."
        )
    return " ".join(lines)


def farmer_summary(
    state: Dict[str, Any],
    crop: str,
    mock_mode: bool,
    language: str = "English",
    provider: Optional[BaseAgronomyProvider] = None,
) -> Dict[str, str]:
    """
    Returns {"text": ..., "source": "template" | "groq"}. The model is asked only when a
    provider is given, the result is real, and either another language is wanted or plain
    rewording helps; any doubt falls back to the template.
    """
    facts = build_facts(state, crop, mock_mode)
    template = template_summary(facts)
    if provider is None or mock_mode or language not in LANGUAGES:
        return {"text": template, "source": "template"}
    prompt = (
        f"Rewrite this field result for a farmer in {language}, in at most three short sentences of "
        "plain words. Use only these facts; add no advice, chemical or dose that is not in them.\n"
        f"Facts: {facts}\nEnglish version: {template}"
    )
    response = provider.generate(
        LLMRequest(user_prompt=prompt, temperature=0.2, timeout_seconds=30)
    )
    text = (response.text_content or "").strip()
    if response.error or not text:
        logger.warning("Farmer summary fell back to the template: %s", response.error)
        return {"text": template, "source": "template"}
    if facts["herbicide"] is None and any(word in text.lower() for word in DOSE_WORDS):
        logger.warning(
            "Farmer summary mentioned a dose without a prescription; using the template."
        )
        return {"text": template, "source": "template"}
    return {"text": text, "source": "model"}
