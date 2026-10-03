"""
src/state.py
Production State Schema for AgriAgent.

Defines the centralized LangGraph state, data models, and typed contracts
for the dual-brain precision agriculture pipeline:
  - System-1: Fast reflex vision (Grounding DINO + SAM 2 + IoU refinement)
  - System-2: Deliberative reasoning (Qwen2.5-VL + ICAR RAG knowledge engine)
"""

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, Tuple, TypedDict
from pydantic import BaseModel, Field
from PIL import Image
try:
    from langchain_core.messages import AnyMessage
except ImportError:
    AnyMessage = Any  # type: ignore # Graceful fallback when langchain-core is not installed


def merge_dicts(a: dict, b: dict) -> dict:
    """Utility to merge two dictionaries safely without mutating originals."""
    c = a.copy()
    c.update(b)
    return c


# ── Artifact Types ─────────────────────────────────────────────────────────────
class ArtifactType(str, Enum):
    """Types of persistent artifacts generated during AgriAgent execution."""
    VISION_MASK = "vision_mask"              # 2D NumPy binary instance segmentation mask
    SPRAY_MAP = "spray_map"                  # GPS-tagged precision spray coordinates & GeoJSON
    PRESCRIPTION_REPORT = "prescription_report" # ICAR/CIBRC weed diagnosis & chemical dosage
    METRIC_EVALUATION = "metric_evaluation"  # IoU, Dice coefficient, chemical savings %
    LOG_SUMMARY = "log_summary"              # Text summary of agent reasoning steps


class Artifact(BaseModel):
    """Container for any serializable artifact output by the pipeline."""
    id: str = Field(..., description="Unique identifier for the artifact")
    type: ArtifactType = Field(..., description="Category of the artifact")
    title: str = Field(..., description="Human-readable title")
    description: str = Field("", description="Detailed explanation of the artifact contents")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata (e.g. coordinates, timestamps)")
    payload: Any = Field(default=None, description="In-memory or serialized object (mask array, dict, text)")


# ── Vision Data Structures ─────────────────────────────────────────────────────
class Box(TypedDict):
    """Normalized or absolute bounding box prediction from Grounding DINO."""
    x1: float
    y1: float
    x2: float
    y2: float
    label: str
    score: float


class Mask(TypedDict):
    """Binary instance segmentation mask prediction from SAM 2."""
    mask_array: Any        # 2D numpy.ndarray of shape [H, W], dtype bool or uint8
    predicted_iou: float   # SAM 2 internal confidence score
    box: Box               # Source bounding box that prompted SAM 2
    label: str             # Classification label (e.g., 'cotton_weed', 'parthenium')


# ── Central Pipeline Graph State ───────────────────────────────────────────────
class GraphState(TypedDict):
    """
    Central LangGraph state passed through the AgriAgent execution graph.
    
    Decoupled into:
      1. Execution control & message history
      2. Input sensor payloads (image, text prompts, metadata)
      3. System-1 Vision outputs (bounding boxes, masks, refinement loops)
      4. System-2 Agronomy outputs (VLM diagnosis, chemical prescription)
      5. Downstream actuators (precision spray map, evaluation benchmarks)
    """

    # 1. Execution History & Artifacts
    messages: List[AnyMessage]
    artifacts: Dict[str, Any]
    error: Optional[str]

    # 2. Input Sensor Payloads
    image: Optional[Image.Image]            # In-memory PIL Image of field patch
    image_path: Optional[str]               # Path to source image file on disk
    text_prompt: Optional[str]              # Detection prompt (e.g. "cotton weed . broadleaf plant")
    field_metadata: Optional[Dict[str, Any]] # Crop type, location, GPS, drone altitude

    # 3. System-1 Vision Pipeline Outputs (Fast Reflex)
    boxes: List[Box]                        # Grounding DINO detected boxes
    masks: List[Mask]                       # SAM 2 instance segmentation masks
    refinement_count: int                   # Active refinement counter (max iterations: 2)

    # 4. System-2 Deliberative Reasoning (Slow Thinking)
    system2_needed: bool                    # Set True if confidence low or weed is unverified
    vlm_reasoning: Optional[str]            # Visual explanation from Qwen2.5-VL / Florence-2
    prescription_report: Optional[Dict[str, Any]] # ICAR herbicide, dosage, water dilution

    # 5. Downstream Actuator & Evaluation
    spray_map: Optional[Dict[str, Any]]     # Nozzle on/off pulses, GeoJSON polygons, savings %
    ground_truth_masks: Optional[List[Any]] # For offline evaluation harness
    evaluation_metrics: Optional[Dict[str, float]] # IoU, Dice, Herbicide savings %
