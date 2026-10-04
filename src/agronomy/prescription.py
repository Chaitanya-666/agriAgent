"""
src/agronomy/prescription.py
Track 2 / Task 2.3: get_herbicide_prescription(weed_name, crop_stage).

Returns ONLY what the indexed ICAR/CIBRC documents say (with citations).
It never invents chemicals or doses: if the store has nothing, it says so.
"""
from typing import Any, Dict, Optional

from src.agronomy.knowledge_store import KnowledgeStore

DISCLAIMER = "Advisory only. Verify active ingredient, dose and PHI against the current CIBRC label before use."


def get_herbicide_prescription(
    weed_name: str,
    crop_stage: str,
    crop: str = "cotton",
    store: Optional[KnowledgeStore] = None,
    k: int = 4,
) -> Dict[str, Any]:
    store = store or KnowledgeStore()
    q = f"{weed_name} control in {crop} at {crop_stage} stage herbicide dose pre-harvest interval"
    hits = store.query(q, k=k)
    return {
        "weed": weed_name,
        "crop": crop,
        "crop_stage": crop_stage,
        "status": "ok" if hits else "no_knowledge_found",
        "evidence": [
            {"text": h["text"], "source": h["source"], "page": h["page"], "authority": h["authority"]}
            for h in hits
        ],
        "disclaimer": DISCLAIMER,
    }
