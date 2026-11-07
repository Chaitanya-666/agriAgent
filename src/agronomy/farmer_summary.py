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
# F23: without these the model wrote "शकरकंद" (sweet potato) for sugar beet (manual test, 30 Oct).
GLOSSARY = {
    "Hindi": "sugar beet = चुकंदर, cotton = कपास, weed = खरपतवार, crop = फसल, spray = छिड़काव",
    "Marathi": "sugar beet = साखर बीट, cotton = कापूस, weed = तण, crop = पीक, spray = फवारणी",
}
DOSE_WORDS = ("g/ha", "g a.i", "ml", "litre", "liter", "kg/ha", "grams")
CROP_NAMES = {
    "Hindi": {"sugar beet": "चुकंदर", "cotton": "कपास"},
    "Marathi": {"sugar beet": "साखर बीट", "cotton": "कापूस"},
}
# Safety sentences are never left to the model (F27: the Hindi summary dropped the wrong-crop
# warning; F29: it turned the ICAR suggestion into an instruction and dropped "read the label").
# They are fixed text, appended after the model's wording, in the chosen language.
WRONG_CROP_NOTE = {
    "English": (
        "Warning: no plant in this photo was recognised as {crop}. If the crop setting is wrong, "
        "crop plants may be marked for spraying; do not use this map until it is checked."
    ),
    "Hindi": (
        "चेतावनी: इस फ़ोटो में कोई भी पौधा {crop} के रूप में नहीं पहचाना गया। अगर फसल का चुनाव गलत "
        "है, तो फसल के पौधों पर भी छिड़काव का निशान लग सकता है; जाँच से पहले इस नक्शे का उपयोग न करें।"
    ),
    "Marathi": (
        "इशारा: या फोटोमधील कोणतेही रोप {crop} म्हणून ओळखले गेले नाही. पिकाची निवड चुकीची असल्यास "
        "पिकाच्या रोपांवरही फवारणीची खूण होऊ शकते; तपासणीपूर्वी हा नकाशा वापरू नका."
    ),
}
LABEL_NOTE = {
    "English": (
        "This is a suggestion from the ICAR table, not an instruction: read the product label "
        "and ask your local agriculture officer before spraying."
    ),
    "Hindi": (
        "यह ICAR तालिका का सुझाव है, निर्देश नहीं: छिड़काव से पहले उत्पाद का लेबल पढ़ें और अपने "
        "स्थानीय कृषि अधिकारी से सलाह लें।"
    ),
    "Marathi": (
        "हा ICAR तक्त्यातील सल्ला आहे, सूचना नाही: फवारणीपूर्वी उत्पादनाचे लेबल वाचा आणि स्थानिक "
        "कृषी अधिकाऱ्यांचा सल्ला घ्या."
    ),
}


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
        # F18/F27: the plant rules found no plant matching the declared crop.
        "crop_not_recognised": spray.get("crop_examples") == 0,
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
    if facts.get("crop_not_recognised"):
        lines.append(WRONG_CROP_NOTE["English"].format(crop=facts["crop"]))
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
            f"{facts['weed_named']}."
        )
        lines.append(LABEL_NOTE["English"])
    return " ".join(lines)


def safety_notes(facts: Dict[str, Any], language: str) -> str:
    """The fixed warning sentences for these facts, in the given language."""
    language = language if language in WRONG_CROP_NOTE else "English"
    notes = []
    if facts.get("crop_not_recognised"):
        crop = CROP_NAMES.get(language, {}).get(facts["crop"], facts["crop"])
        notes.append(WRONG_CROP_NOTE[language].format(crop=crop))
    if facts["herbicide"]:
        notes.append(LABEL_NOTE[language])
    return " ".join(notes)


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
        "plain words. Use only these facts; add no advice, chemical or dose that is not in them. "
        "Describe any herbicide only as what the ICAR table suggests, never as an instruction; "
        "leave out warnings, they are added separately.\n"
        f"Facts: {facts}\nEnglish version: {template}"
        + (f"\nUse these words: {GLOSSARY[language]}." if language in GLOSSARY else "")
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
    notes = safety_notes(facts, language)
    return {"text": f"{text} {notes}".strip(), "source": "model"}
