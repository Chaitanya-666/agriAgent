"""
src/state.py
Extended GraphState for AgriAgent vision pipeline.
Builds on SmartDesk's existing state.
"""
from typing import TypedDict, Optional, List, Dict, Any
from PIL import Image
from langchain_core.messages import AnyMessage


class Box(TypedDict):
    x1: float
    y1: float
    x2: float
    y2: float
    label: str
    score: float


class Mask(TypedDict):
    mask_array: Any        # NumPy binary array
    predicted_iou: float
    box: Box               # Source bounding box
    label: str


class GraphState(TypedDict):
    # === SmartDesk Existing Fields ===
    messages: List[AnyMessage]
    current_task: Optional[Dict]
    completed_tasks: List[Dict]
    artifacts: Dict[str, Any]

    # === SmartDesk Agent Histories ===
    workspace_messages: List[AnyMessage]
    knowledge_messages: List[AnyMessage]
    productivity_messages: List[AnyMessage]

    # === AgriAgent Vision Extensions ===
    image: Optional[Image.Image]            # Input field image
    image_path: Optional[str]               # Path to uploaded image
    text_prompt: Optional[str]              # Natural language command
    boxes: List[Box]                        # Grounding DINO outputs
    masks: List[Mask]                       # SAM 2 outputs
    refinement_count: int                   # Refinement iterations (max 2)
    spray_map: Optional[Dict]               # GPS-tagged spray coordinates
    analysis_report: Optional[Dict]         # Per-app metrics
    application_id: Optional[int]           # Which of 5 apps is active

    # === Evaluation Fields ===
    ground_truth_masks: Optional[List]      # For IoU/Dice computation
    evaluation_metrics: Optional[Dict]      # Computed metrics
