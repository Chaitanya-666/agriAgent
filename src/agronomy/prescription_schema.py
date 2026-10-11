"""
src/agronomy/prescription_schema.py
Pydantic schemas for Agronomy Chemical Prescriptions and Citation Records.
Adheres strictly to PROJECT.md Section 4 Interface Contracts.
"""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CitationRecord(BaseModel):
    """Statutory citation record referencing verified agronomic evidence."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    source: str
    page: int
    authority: str
    text_snippet: str
    text: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def sync_text_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "text" in data and "text_snippet" not in data:
                data["text_snippet"] = data["text"]
            elif "text_snippet" in data and "text" not in data:
                data["text"] = data["text_snippet"]
        return data


class ChemicalPrescription(BaseModel):
    """
    Structured chemical prescription contract conforming to PROJECT.md Section 4.
    Includes backward-compatible dictionary access for existing pipeline consumers.
    """
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    status: Literal["ok", "no_knowledge_found", "unapproved_chemical_flagged"]
    crop: str
    target_weed: str
    active_ingredient: Optional[str] = None
    formulation: Optional[str] = None
    dosage_ai_g_per_ha: Optional[float] = None
    water_volume_l_per_ha: Optional[float] = None
    pre_harvest_interval_days: Optional[int] = None
    toxicity_band: Optional[Literal["RED", "YELLOW", "BLUE", "GREEN"]] = None
    citations: List[CitationRecord] = Field(default_factory=list)
    disclaimer: str

    # Statutory safety audit trail
    safety_warning: Optional[str] = None
    dosage_clamped: bool = False
    original_dosage_ai_g_per_ha: Optional[float] = None
    crop_stage: Optional[str] = None

    def __getitem__(self, item: str) -> Any:
        if item == "weed":
            return self.target_weed
        if item == "evidence":
            return [
                {
                    "text": c.text_snippet or c.text or "",
                    "source": c.source,
                    "page": c.page,
                    "authority": c.authority,
                }
                for c in self.citations
            ]
        if hasattr(self, item):
            return getattr(self, item)
        extra = getattr(self, "__pydantic_extra__", None)
        if extra and item in extra:
            return extra[item]
        raise KeyError(item)

    def __setitem__(self, item: str, value: Any) -> None:
        if hasattr(self, item) and item in self.__class__.model_fields:
            setattr(self, item, value)
        elif item == "weed":
            self.target_weed = value
        elif item == "evidence":
            self.citations = [
                CitationRecord(**e) if isinstance(e, dict) else e for e in value
            ]
        else:
            extra = getattr(self, "__pydantic_extra__", None)
            if extra is None:
                self.__pydantic_extra__ = {}
                extra = self.__pydantic_extra__
            extra[item] = value

    def __contains__(self, item: str) -> bool:
        if item in ("weed", "evidence"):
            return True
        if hasattr(self, item):
            return True
        extra = getattr(self, "__pydantic_extra__", None)
        return bool(extra and item in extra)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default

    def to_dict(self) -> Dict[str, Any]:
        """Produce a complete dictionary containing standard and backward-compatible fields."""
        d = self.model_dump()
        d["weed"] = self.target_weed
        d["evidence"] = [
            {
                "text": c.text_snippet or c.text or "",
                "source": c.source,
                "page": c.page,
                "authority": c.authority,
            }
            for c in self.citations
        ]
        return d
