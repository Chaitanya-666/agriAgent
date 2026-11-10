"""Input checks for the Field Service. Pure functions: no web framework, no database.

Every check raises ValidationError with the HTTP status the API should answer with, so the
rules can be unit tested on their own and the API layer only translates them.
"""

from __future__ import annotations

import io
import math
import warnings
from dataclasses import dataclass
from typing import Optional

from PIL import Image

from service import config

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"


class ValidationError(Exception):
    """A request the service refuses. `status` is the HTTP status code to send back."""

    def __init__(self, status: int, code: str, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.field = field


@dataclass(frozen=True)
class AnalysisParams:
    crop: str
    mode: str
    min_confidence: float


def parse_crop(value: Optional[str]) -> str:
    crop = (value or "").strip().lower()
    if crop not in config.CROPS:
        raise ValidationError(
            422, "invalid_crop", f"crop must be one of: {', '.join(config.CROPS)}", "crop"
        )
    return crop


def parse_mode(value: Optional[str], allow_real: bool) -> str:
    mode = (value or "").strip().lower()
    if mode not in config.MODES:
        raise ValidationError(422, "invalid_mode", "mode must be 'mock' or 'real'", "mode")
    if mode == "real" and not allow_real:
        raise ValidationError(
            403,
            "real_mode_disabled",
            "real mode is switched off on this server (start it with AGRIAGENT_ALLOW_REAL=1)",
            "mode",
        )
    return mode


def parse_min_confidence(value: Optional[str]) -> float:
    """Accept a number in [0.70, 1.00]. Text, NaN and infinity are refused."""
    text = (value or "").strip()
    if text == "":
        return config.DEFAULT_MIN_CONFIDENCE
    try:
        number = float(text)
    except ValueError:
        raise ValidationError(
            422, "invalid_min_confidence", "min_confidence must be a number", "min_confidence"
        ) from None
    # float() accepts "nan" and "inf"; both slip past < and > comparisons, so check first.
    if not math.isfinite(number):
        raise ValidationError(
            422, "invalid_min_confidence", "min_confidence must be a finite number", "min_confidence"
        )
    if number < config.MIN_CONFIDENCE_FLOOR or number > config.MIN_CONFIDENCE_CEILING:
        raise ValidationError(
            422,
            "invalid_min_confidence",
            f"min_confidence must be between {config.MIN_CONFIDENCE_FLOOR:.2f} and "
            f"{config.MIN_CONFIDENCE_CEILING:.2f} (the safety gate never accepts less than "
            f"{config.MIN_CONFIDENCE_FLOOR:.2f})",
            "min_confidence",
        )
    return number


def parse_params(
    crop: Optional[str], mode: Optional[str], min_confidence: Optional[str], allow_real: bool
) -> AnalysisParams:
    return AnalysisParams(
        crop=parse_crop(crop),
        mode=parse_mode(mode, allow_real),
        min_confidence=parse_min_confidence(min_confidence),
    )


def sniff_image_type(raw: bytes) -> Optional[str]:
    """Return "png" or "jpeg" from the file's first bytes, or None.

    The browser's Content-Type header is not trusted: it comes from the file name.
    """
    if raw.startswith(PNG_MAGIC):
        return "png"
    if raw.startswith(JPEG_MAGIC):
        return "jpeg"
    return None


def decode_image(raw: bytes) -> Image.Image:
    """Turn uploaded bytes into an RGB image, or raise ValidationError."""
    if not raw:
        raise ValidationError(422, "empty_file", "the uploaded file is empty", "image")
    if len(raw) > config.MAX_UPLOAD_BYTES:
        raise ValidationError(
            413,
            "file_too_large",
            f"the file is larger than {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MiB",
            "image",
        )
    if sniff_image_type(raw) is None:
        raise ValidationError(
            415, "unsupported_type", "only PNG and JPEG images are accepted", "image"
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(raw))
            width, height = img.size
            if width * height > config.MAX_IMAGE_PIXELS:
                raise ValidationError(
                    413,
                    "image_too_large",
                    f"the image has {width}x{height} pixels; the limit is "
                    f"{config.MAX_IMAGE_PIXELS:,} pixels",
                    "image",
                )
            img.load()
    except ValidationError:
        raise
    except Exception as exc:  # truncated or corrupt files, bombs flagged by Pillow
        raise ValidationError(
            422, "corrupt_image", f"the image could not be read: {exc}", "image"
        ) from None
    if min(width, height) < config.MIN_IMAGE_SIDE:
        raise ValidationError(
            422,
            "image_too_small",
            f"the image is {width}x{height}; each side must be at least "
            f"{config.MIN_IMAGE_SIDE} pixels",
            "image",
        )
    return img.convert("RGB")


def parse_page(limit: Optional[int], offset: Optional[int]) -> tuple[int, int]:
    limit = config.PAGE_LIMIT_DEFAULT if limit is None else limit
    offset = 0 if offset is None else offset
    if not 1 <= limit <= config.PAGE_LIMIT_MAX:
        raise ValidationError(
            422, "invalid_limit", f"limit must be between 1 and {config.PAGE_LIMIT_MAX}", "limit"
        )
    if offset < 0:
        raise ValidationError(422, "invalid_offset", "offset must be 0 or more", "offset")
    return limit, offset
