"""
tests/e2e/fixtures.py
Fixtures, synthetic generators, and test helpers for AgriAgent E2E tests.
Provides self-contained, isolated test assets adhering to opaque-box principles.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image

from src.state import Box, Mask

# Base directory for repository sample fixtures
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "sample"
DOC_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "agronomy_test_doc.txt"


def create_test_field_image(
    width: int = 640,
    height: int = 480,
    base_color: Tuple[int, int, int] = (95, 145, 60),
) -> Image.Image:
    """
    Generate a deterministic synthetic RGB crop field image.
    Includes background variation to simulate natural soil/canopy conditions.
    """
    img_array = np.zeros((height, width, 3), dtype=np.uint8)
    img_array[:, :] = base_color

    # Add subtle deterministic texture so it's not a flat single color
    yy, xx = np.mgrid[0:height, 0:width]
    texture = (np.sin(xx * 0.05) * np.cos(yy * 0.05) * 15.0).astype(np.int16)
    for c in range(3):
        channel = img_array[:, :, c].astype(np.int16) + texture
        img_array[:, :, c] = np.clip(channel, 0, 255).astype(np.uint8)

    return Image.fromarray(img_array, mode="RGB")


def create_blank_image(
    width: int = 640,
    height: int = 480,
    color: Tuple[int, int, int] = (0, 0, 0),
) -> Image.Image:
    """Generate a uniform single-color PIL image (e.g., all black, all white)."""
    return Image.new("RGB", (width, height), color=color)


def create_corrupt_image_bytes() -> bytes:
    """Generate a malformed byte sequence mimicking corrupted or truncated image data."""
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00\x00\x00\x10\x00\x00\x00\x10\x08\x02\x00\x00\x00" + b"\xff\x00\xdeadbeef"


def get_sample_image_path(filename: str) -> Path:
    """
    Resolve and verify path to a committed sample image fixture.
    Raises FileNotFoundError if the file is not present.
    """
    target = SAMPLE_FIXTURES_DIR / filename
    if not target.exists():
        raise FileNotFoundError(f"Sample fixture not found: {target}")
    return target


def create_synthetic_box(
    x1: float = 50.0,
    y1: float = 60.0,
    x2: float = 200.0,
    y2: float = 220.0,
    label: str = "cotton_weed",
    score: float = 0.88,
) -> Box:
    """Create a validated Box dictionary conforming to the Vision Perception contract."""
    return {
        "x1": float(x1),
        "y1": float(y1),
        "x2": float(x2),
        "y2": float(y2),
        "label": str(label),
        "score": float(score),
    }


def create_synthetic_mask(
    height: int = 480,
    width: int = 640,
    box: Optional[Box] = None,
    predicted_iou: float = 0.89,
    label: str = "cotton_weed",
) -> Mask:
    """Create a validated Mask dictionary conforming to the Vision Perception contract."""
    if box is None:
        box = create_synthetic_box(50.0, 60.0, 200.0, 220.0, label=label)

    mask_arr = np.zeros((height, width), dtype=bool)
    x1, y1 = max(0, int(box["x1"])), max(0, int(box["y1"]))
    x2, y2 = min(width, int(box["x2"])), min(height, int(box["y2"]))
    mask_arr[y1:y2, x1:x2] = True

    return {
        "mask_array": mask_arr,
        "predicted_iou": float(predicted_iou),
        "box": box,
        "label": str(label),
    }


class InMemoryKnowledgeStore:
    """
    Fast, deterministic in-memory mock knowledge store for E2E testing of RAG contracts.
    Implements the identical query interface as `KnowledgeStore` without requiring ChromaDB.
    """

    def __init__(self, documents: Optional[List[Dict[str, Any]]] = None):
        if documents is not None:
            self._docs = documents
        else:
            self._docs = [
                {
                    "text": (
                        "ICAR Weed Bulletin: Testweed alpha in cotton crop, vegetative stage. "
                        "Recommended herbicide is ExampleChem-X at 1 unit per hectare. "
                        "Pre-harvest interval is 99 days. Ensure targeted spot spraying."
                    ),
                    "source": "agronomy_test_doc.txt",
                    "page": 1,
                    "authority": "ICAR",
                    "weed_keywords": ["testweed", "testweed alpha"],
                },
                {
                    "text": (
                        "CIBRC Approved Use: Parthenium hysterophorus in cotton field. "
                        "Active ingredient: Pyrithiobac sodium 10% EC at 62.5 to 75 g a.i./ha. "
                        "Dilute in 500 liters of water per hectare. Pre-harvest interval: 60 days."
                    ),
                    "source": "cibrc_approved_herbicides_2024.pdf",
                    "page": 4,
                    "authority": "CIBRC",
                    "weed_keywords": ["parthenium", "parthenium hysterophorus"],
                },
                {
                    "text": (
                        "ICAR Technical Report: Fakegrass beta in sugarbeet fields at seedling stage. "
                        "Herbicide: ExampleChem-Y at 2 units per hectare. Maximum single dose: 250 g a.i./ha."
                    ),
                    "source": "sugarbeet_weed_manual.pdf",
                    "page": 2,
                    "authority": "ICAR",
                    "weed_keywords": ["fakegrass", "fakegrass beta"],
                },
            ]

    def query(self, q: str, k: int = 4) -> List[Dict[str, Any]]:
        """
        Query the in-memory documents using case-insensitive keyword matching.
        Returns matching hits with text, source, page, authority, and distance.
        """
        q_lower = q.lower()
        matched = []
        for doc in self._docs:
            weed_keywords = doc.get("weed_keywords", [])
            # Require matching the specific target weed/pest
            if any(kw.lower() in q_lower for kw in weed_keywords):
                matched.append({
                    "text": doc["text"],
                    "source": doc["source"],
                    "page": doc["page"],
                    "authority": doc["authority"],
                    "distance": 0.15,
                })

        # Sort by best pseudo-distance
        matched.sort(key=lambda x: x["distance"])
        return matched[:k]
