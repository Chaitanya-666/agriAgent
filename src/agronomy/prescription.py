"""
src/agronomy/prescription.py
Track 2 / Task 2.3: Structured Chemical Prescription and Statutory Safety Filter.
Builds statutory herbicide prescriptions from the knowledge store.

Guarantees:
1. Grounded evidence extraction from ICAR / CIBRC knowledge store.
2. Safe no_knowledge_found handling with zero hallucinated chemicals when evidence is absent.
3. Statutory Banned Chemical Filter (flag banned/withdrawn/refused herbicides from Table 3.3).
4. Statutory Dosage Ceiling Check (clamp dosages exceeding Table 4.3 upper bounds).
5. Mandatory statutory advisory disclaimer.
"""

import logging
import re
from typing import Any, Dict, List, Literal, Optional, Tuple

from src.agronomy.knowledge_store import InMemoryKnowledgeStore, KnowledgeStore
from src.agronomy.prescription_schema import ChemicalPrescription, CitationRecord

logger = logging.getLogger("agriagent.prescription")

DISCLAIMER = "Advisory only. Verify active ingredient, dose and PHI against the current CIBRC label before use."

# ==============================================================================
# STATUTORY RULES: CIBRC BANNED HERBICIDES & DOSAGE CEILINGS
# ==============================================================================

# Table 3.3: Banned, withdrawn, refused herbicides in India (Insecticides Act 1968)
BANNED_HERBICIDES: Dict[str, str] = {
    "nitrofen": "Banned in India (Table 3.3, Insecticides Act 1968)",
    "paraquat dimethyl sulphate": "Banned in India (Table 3.3, Insecticides Act 1968)",
    "metoxuron": "Banned in India (Table 3.3, Insecticides Act 1968)",
    "dalapon": "Withdrawn in India (Table 3.3, Insecticides Act 1968)",
    "simazine": "Withdrawn in India (Table 3.3, Insecticides Act 1968)",
    "2,4,5-t": "Registration refused in India (Table 3.3, Insecticides Act 1968)",
    "ammonium sulphamate": "Registration refused in India (Table 3.3, Insecticides Act 1968)",
    "calcium arsenate": "Registration refused in India (Table 3.3, Insecticides Act 1968)",
    "tca": "Registration refused in India (Table 3.3, Insecticides Act 1968)",
}

# Table 4.1 to 4.8: Statutory maximum active ingredient dosage ceilings (g a.i. / ha)
STATUTORY_DOSAGE_CEILINGS_G_PER_HA: Dict[str, Dict[str, float]] = {
    "cotton": {
        "pyrithiobac-sodium": 75.0,
        "pyrithiobac": 75.0,
        "fenoxaprop-p-ethyl": 67.5,
        "fenoxaprop": 67.5,
        "quizalofop-ethyl": 50.5,
        "quizalofop": 50.5,
        "glufosinate-ammonium": 450.0,
        "glufosinate": 450.0,
        "fluchloralin": 1200.0,
        "pendimethalin": 1250.0,
        "diuron": 1500.0,
        "alachlor": 2500.0,
    },
    "beet root": {
        "pendimethalin": 1000.0,
    },
    "wheat": {
        "sulfosulfuron": 25.0,
        "clodinafop-propargyl": 60.0,
        "metsulfuron-methyl": 4.0,
        "2,4-d": 500.0,
        "isoproturon": 1000.0,
        "pendimethalin": 1000.0,
    },
    "rice": {
        "pyrazosulfuron-ethyl": 20.0,
        "bispyribac-sodium": 25.0,
        "pretilachlor": 750.0,
        "butachlor": 1500.0,
    },
}

ToxicityBand = Literal["RED", "YELLOW", "BLUE", "GREEN"]
TOXICITY_BANDS: Dict[str, ToxicityBand] = {
    "pyrithiobac-sodium": "BLUE",
    "fenoxaprop-p-ethyl": "BLUE",
    "quizalofop-ethyl": "BLUE",
    "glufosinate-ammonium": "BLUE",
    "fluchloralin": "BLUE",
    "pendimethalin": "BLUE",
    "diuron": "BLUE",
    "alachlor": "YELLOW",
    "2,4-d": "YELLOW",
    "sulfosulfuron": "GREEN",
    "pyrazosulfuron-ethyl": "GREEN",
    "clodinafop-propargyl": "BLUE",
    "bispyribac-sodium": "BLUE",
}


def check_banned_chemicals(query_or_text: str) -> Optional[Tuple[str, str]]:
    """Check if query or document text mentions a statutory banned/withdrawn herbicide."""
    text_lower = query_or_text.lower()
    for chemical, reason in BANNED_HERBICIDES.items():
        # Match whole word or explicit chemical token
        pattern = r"\b" + re.escape(chemical) + r"\b"
        if re.search(pattern, text_lower):
            return chemical, reason
    return None


def get_dosage_ceiling(crop: str, active_ingredient: str) -> Optional[float]:
    """Retrieve statutory active ingredient dosage ceiling in g a.i./ha for crop and chemical."""
    crop_rules = STATUTORY_DOSAGE_CEILINGS_G_PER_HA.get(crop.lower().strip(), {})
    chem_clean = active_ingredient.lower().strip()
    if chem_clean in crop_rules:
        return crop_rules[chem_clean]
    for key, limit in crop_rules.items():
        if key in chem_clean or chem_clean in key:
            return limit
    return None


def extract_structured_fields_from_hit(hit: Dict[str, Any], crop: str) -> Dict[str, Any]:
    """Extract structured active ingredient, formulation, dosage, water volume, and PHI from hit."""
    res: Dict[str, Any] = {
        "active_ingredient": hit.get("active_ingredient"),
        "formulation": hit.get("chemical"),
        "dosage_ai_g_per_ha": hit.get("dosage_ai_g_per_ha"),
        "water_volume_l_per_ha": hit.get("water_l_per_ha"),
        "pre_harvest_interval_days": hit.get("waiting_period_days"),
    }

    # Clean "unknown" placeholders
    for k in ("active_ingredient", "formulation"):
        if res[k] in ("unknown", "", None):
            res[k] = None

    text = hit.get("text", "")

    # Fallback text extractors if fields are missing
    if not res["active_ingredient"]:
        ai_match = re.search(
            r"(?:Active ingredient|Herbicide):\s*([A-Za-z0-9\-\s%]+?)(?:at|\||\.|\n|$)",
            text,
            re.IGNORECASE,
        )
        if ai_match:
            cand = ai_match.group(1).strip()
            if cand.lower() not in ("unknown", ""):
                res["active_ingredient"] = cand

    if not res["formulation"] and res["active_ingredient"]:
        res["formulation"] = res["active_ingredient"]

    if res["dosage_ai_g_per_ha"] in (0.0, None):
        dose_match = re.search(
            r"([0-9\.]+)\s*(?:g|kg|units?)\s*(?:a\.i\.)?(?:\s*(?:per\s*hectare|/ha))?",
            text,
            re.IGNORECASE,
        )
        if dose_match:
            try:
                res["dosage_ai_g_per_ha"] = float(dose_match.group(1))
            except ValueError:
                pass

    if res["water_volume_l_per_ha"] in (0.0, None):
        water_match = re.search(
            r"(?:dilut(?:e|ion)\s*(?:in)?|water)[\s:]*([0-9\.]+)\s*(?:liters?|l)",
            text,
            re.IGNORECASE,
        )
        if water_match:
            try:
                res["water_volume_l_per_ha"] = float(water_match.group(1))
            except ValueError:
                pass

    if res["pre_harvest_interval_days"] in (0, None):
        phi_match = re.search(
            r"(?:waiting period|pre-harvest interval|phi)[\s:]*([0-9]+)\s*days?",
            text,
            re.IGNORECASE,
        )
        if phi_match:
            try:
                res["pre_harvest_interval_days"] = int(phi_match.group(1))
            except ValueError:
                pass

    return res


def create_chemical_prescription(
    weed_name: str,
    crop_stage: str,
    crop: str = "cotton",
    store: Optional[Any] = None,
    k: int = 4,
    distance_threshold: Optional[float] = 0.25,
) -> ChemicalPrescription:
    """
    Generate validated ChemicalPrescription object conforming to statutory rules.
    """
    if store is None:
        try:
            store = KnowledgeStore()
        except ImportError:
            store = InMemoryKnowledgeStore()
            store.ingest()

    # 1. Check for banned chemicals in the query itself
    banned_in_query = check_banned_chemicals(weed_name)
    if banned_in_query:
        chem, reason = banned_in_query
        return ChemicalPrescription(
            status="unapproved_chemical_flagged",
            crop=crop,
            target_weed=weed_name,
            active_ingredient=None,
            formulation=None,
            dosage_ai_g_per_ha=None,
            water_volume_l_per_ha=None,
            pre_harvest_interval_days=None,
            toxicity_band=None,
            citations=[],
            disclaimer=DISCLAIMER,
            safety_warning=f"BANNED HERBICIDE: {chem} is {reason}. Prescription refused.",
            crop_stage=crop_stage,
        )

    # 2. Query knowledge store
    q = f"{weed_name} control in {crop} at {crop_stage} stage herbicide dose pre-harvest interval"
    try:
        raw_hits = store.query(q, k=k, distance_threshold=distance_threshold)
    except TypeError:
        # Fallback for store implementations that don't accept distance_threshold argument
        raw_hits = store.query(q, k=k)

    # 3. Filter distance if store did not filter
    hits = []
    for h in raw_hits:
        if distance_threshold is not None and "distance" in h:
            if float(h["distance"]) > distance_threshold:
                continue
        hits.append(h)

    # 4. Safe fallback if zero relevant knowledge hits
    if not hits:
        return ChemicalPrescription(
            status="no_knowledge_found",
            crop=crop,
            target_weed=weed_name,
            active_ingredient=None,
            formulation=None,
            dosage_ai_g_per_ha=None,
            water_volume_l_per_ha=None,
            pre_harvest_interval_days=None,
            toxicity_band=None,
            citations=[],
            disclaimer=DISCLAIMER,
            safety_warning=None,
            crop_stage=crop_stage,
        )

    # 5. Build citations
    citations: List[CitationRecord] = []
    for h in hits:
        text_content = h.get("text", "")
        citations.append(
            CitationRecord(
                source=str(h.get("source", "icar_dwr_herbicide_use_bulletin22.pdf")),
                page=int(h.get("page", 1)),
                authority=str(h.get("authority", "ICAR")),
                text_snippet=text_content[:400],
                text=text_content[:400],
            )
        )

    # 6. Extract structured fields from top hit
    top_hit = hits[0]
    extracted = extract_structured_fields_from_hit(top_hit, crop=crop)

    # 7. Check if extracted chemical is banned
    hit_text = top_hit.get("text", "") + " " + str(extracted.get("active_ingredient", ""))
    banned_in_hit = check_banned_chemicals(hit_text)
    if banned_in_hit:
        chem, reason = banned_in_hit
        return ChemicalPrescription(
            status="unapproved_chemical_flagged",
            crop=crop,
            target_weed=weed_name,
            active_ingredient=None,
            formulation=None,
            dosage_ai_g_per_ha=None,
            water_volume_l_per_ha=None,
            pre_harvest_interval_days=None,
            toxicity_band=None,
            citations=citations,
            disclaimer=DISCLAIMER,
            safety_warning=f"BANNED HERBICIDE: {chem} is {reason}. Spot spraying strictly suppressed.",
            crop_stage=crop_stage,
        )

    active_ing = extracted.get("active_ingredient")
    formulation = extracted.get("formulation")
    dosage = extracted.get("dosage_ai_g_per_ha")
    water_vol = extracted.get("water_volume_l_per_ha")
    phi = extracted.get("pre_harvest_interval_days")

    # 8. Statutory Dosage Ceiling Check
    dosage_clamped = False
    original_dosage = dosage
    safety_warning = None

    if active_ing and dosage is not None and dosage > 0.0:
        ceiling = get_dosage_ceiling(crop, active_ing)
        if ceiling is not None and dosage > ceiling:
            dosage_clamped = True
            dosage = ceiling
            safety_warning = (
                f"Statutory dosage ceiling exceeded: proposed dosage {original_dosage} g a.i./ha "
                f"exceeds CIBRC approved maximum label claim of {ceiling} g a.i./ha (Table 4.3). "
                f"Dosage clamped to statutory ceiling."
            )

    # 9. Toxicity Band
    toxicity_band = None
    if active_ing:
        chem_clean = active_ing.lower().strip()
        for k_chem, band in TOXICITY_BANDS.items():
            if k_chem in chem_clean or chem_clean in k_chem:
                toxicity_band = band
                break
        if not toxicity_band:
            toxicity_band = "BLUE"  # Default moderate cautionary label under Insecticides Act

    return ChemicalPrescription(
        status="ok",
        crop=crop,
        target_weed=weed_name,
        active_ingredient=active_ing,
        formulation=formulation,
        dosage_ai_g_per_ha=dosage,
        water_volume_l_per_ha=water_vol,
        pre_harvest_interval_days=phi,
        toxicity_band=toxicity_band,
        citations=citations,
        disclaimer=DISCLAIMER,
        safety_warning=safety_warning,
        dosage_clamped=dosage_clamped,
        original_dosage_ai_g_per_ha=original_dosage,
        crop_stage=crop_stage,
    )


def get_herbicide_prescription(
    weed_name: str,
    crop_stage: str,
    crop: str = "cotton",
    store: Optional[Any] = None,
    k: int = 4,
    distance_threshold: Optional[float] = 0.25,
) -> Dict[str, Any]:
    """
    Public entry point for herbicide prescription generation.
    Returns a complete dictionary satisfying ChemicalPrescription schema and backward compatibility.
    """
    presc = create_chemical_prescription(
        weed_name=weed_name,
        crop_stage=crop_stage,
        crop=crop,
        store=store,
        k=k,
        distance_threshold=distance_threshold,
    )
    return presc.to_dict()
