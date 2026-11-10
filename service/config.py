"""Settings and fixed limits for the Field Service.

Fixed limits are module constants, so tests and the validation code read the same numbers.
Settings that differ per machine (database file, real mode on or off) come from environment
variables and are read once, when the app is created.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT_ROOT / "web"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "service" / "field_service.db"

# Same choices as the Streamlit sidebar (app/components/ui.py).
CROPS = ("cotton", "sugar beet", "wheat", "rice")
MODES = ("mock", "real")

# The spray safety gate never accepts a detection scored below 0.70 (pipeline docstring),
# so the API refuses lower values instead of silently raising them.
MIN_CONFIDENCE_FLOOR = 0.70
MIN_CONFIDENCE_CEILING = 1.00
DEFAULT_MIN_CONFIDENCE = 0.70

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB
MIN_IMAGE_SIDE = 32  # pixels; smaller images carry no usable field detail
MAX_IMAGE_PIXELS = 4096 * 4096  # about 16.8 megapixels; guards against decompression bombs

PAGE_LIMIT_MAX = 100
PAGE_LIMIT_DEFAULT = 20

OVERLAY_MAX_SIDE = 800  # stored result image is shrunk to this, then saved as JPEG
OVERLAY_JPEG_QUALITY = 82


@dataclass(frozen=True)
class Settings:
    """Per-machine settings."""

    db_path: Path
    allow_real_mode: bool = False


def load_settings() -> Settings:
    """Read settings from the environment.

    AGRIAGENT_DB         path of the SQLite file (default data/service/field_service.db)
    AGRIAGENT_ALLOW_REAL "1" lets clients ask for real mode (loads Grounding DINO + SAM 2)
    """
    return Settings(
        db_path=Path(os.environ.get("AGRIAGENT_DB", str(DEFAULT_DB_PATH))),
        allow_real_mode=os.environ.get("AGRIAGENT_ALLOW_REAL", "0") == "1",
    )
