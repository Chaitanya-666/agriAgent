"""
src/vision/grounding_dino.py
Open-Vocabulary Zero-Shot Object Detector Wrapper for AgriAgent.

Architecture Rationale:
-----------------------
Traditional agricultural detectors (YOLOv8, Faster R-CNN) require hundreds of
manually labeled bounding boxes for each specific weed species and are closed-vocabulary.
Grounding DINO (IDEA-Research) performs open-vocabulary detection by fusing a
Swin Transformer vision backbone with a BERT text encoder via cross-modality attention.
This allows AgriAgent to detect arbitrary weeds and plant conditions using natural language
prompts (e.g., "cotton weed . broadleaf plant . dry yellow grass .") with ZERO fine-tuning.

Operational Modes:
------------------
1. Live Mode (GPU / PyTorch):
   Uses Hugging Face `transformers` with `IDEA-Research/grounding-dino-tiny`.
   Executes multimodal cross-attention to produce precise bounding boxes.
2. Mock / Fallback Mode (`mock_mode=True` or when PyTorch/Transformers are missing):
   Synthesizes deterministic, realistic bounding boxes on any input image.
   Enables teammates (UI dashboard, Data test harness) and unit tests to run
   frictionless on standard development laptops without downloading 1.5 GB weights.
"""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image

# Import typed state schema
from src.state import Box

logger = logging.getLogger("agriagent.vision.grounding_dino")


@dataclass
class DetectionResult:
    """Strongly typed container for an individual detected object."""
    box: Tuple[float, float, float, float]  # (x1, y1, x2, y2) in pixel coordinates
    normalized_box: Tuple[float, float, float, float]  # (x1, y1, x2, y2) in [0, 1] range
    label: str
    confidence: float

    def to_dict(self) -> Box:
        """Serialize to GraphState Box TypedDict format."""
        return {
            "x1": round(self.box[0], 2),
            "y1": round(self.box[1], 2),
            "x2": round(self.box[2], 2),
            "y2": round(self.box[3], 2),
            "label": self.label,
            "score": round(self.confidence, 4),
        }


class GroundingDINOEngine:
    """
    Production wrapper for Grounding DINO open-vocabulary zero-shot detection.
    
    Attributes:
        model_id (str): Hugging Face model repository ID.
        box_threshold (float): Confidence threshold for bounding box extraction.
        text_threshold (float): Cross-modal similarity threshold for token association.
        mock_mode (bool): If True, bypasses heavy deep learning inference.
        device (str): Inference device ('cuda' or 'cpu').
    """

    def __init__(
        self,
        model_id: str = "IDEA-Research/grounding-dino-tiny",
        box_threshold: float = 0.35,
        text_threshold: float = 0.25,
        mock_mode: bool = False,
        device: Optional[str] = None,
    ):
        self.model_id = model_id
        self.box_threshold = box_threshold
        self.text_threshold = text_threshold
        self.mock_mode = mock_mode

        self._model = None
        self._processor = None
        self.device = device

        if not self.mock_mode:
            self._initialize_model()

    def _initialize_model(self) -> None:
        """Safely initialize Hugging Face transformers pipeline."""
        try:
            import torch
            from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

            if self.device is None:
                self.device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info("Loading Grounding DINO [%s] on device [%s]...", self.model_id, self.device)
            self._processor = AutoProcessor.from_pretrained(self.model_id)
            self._model = AutoModelForZeroShotObjectDetection.from_pretrained(self.model_id).to(self.device)
            self._model.eval()
            logger.info("Grounding DINO initialized successfully.")
        except ImportError as err:
            logger.warning(
                "PyTorch or Transformers not installed (%s). Falling back to mock_mode=True.",
                err,
            )
            self.mock_mode = True
        except Exception as err:
            logger.warning(
                "Failed to download/load model weights (%s). Falling back to mock_mode=True.",
                err,
            )
            self.mock_mode = True

    def _normalize_image_input(self, image_input: Union[str, Path, Image.Image, np.ndarray]) -> Image.Image:
        """Ensure input is converted into a standard RGB PIL Image."""
        if isinstance(image_input, (str, Path)):
            path = Path(image_input)
            if not path.exists():
                raise FileNotFoundError(f"Image file not found: {path}")
            return Image.open(path).convert("RGB")
        elif isinstance(image_input, np.ndarray):
            return Image.fromarray(image_input).convert("RGB")
        elif isinstance(image_input, Image.Image):
            return image_input.convert("RGB")
        else:
            raise TypeError(f"Unsupported image input type: {type(image_input)}")

    def _generate_mock_detections(
        self,
        image_width: int,
        image_height: int,
        text_prompt: str,
    ) -> List[DetectionResult]:
        """
        Generate deterministic, realistic bounding boxes for development/testing.
        
        Extracts candidate labels from the prompt (separated by periods or commas)
        and places synthetic weed bounding boxes at realistic spatial positions.
        """
        # Parse prompt categories (e.g. 'cotton weed . broadleaf plant' -> ['cotton weed', 'broadleaf plant'])
        raw_tokens = [tok.strip().strip(".") for tok in text_prompt.replace(",", ".").split(".") if tok.strip()]
        primary_label = raw_tokens[0] if raw_tokens else "weed"

        # Deterministic relative coordinates for mock weed patches in a typical field photo
        mock_relative_boxes = [
            (0.18, 0.22, 0.38, 0.44, 0.91),
            (0.55, 0.30, 0.78, 0.58, 0.86),
            (0.32, 0.62, 0.52, 0.85, 0.79),
        ]

        results: List[DetectionResult] = []
        for norm_x1, norm_y1, norm_x2, norm_y2, conf in mock_relative_boxes:
            if conf < self.box_threshold:
                continue

            abs_x1 = norm_x1 * image_width
            abs_y1 = norm_y1 * image_height
            abs_x2 = norm_x2 * image_width
            abs_y2 = norm_y2 * image_height

            results.append(
                DetectionResult(
                    box=(abs_x1, abs_y1, abs_x2, abs_y2),
                    normalized_box=(norm_x1, norm_y1, norm_x2, norm_y2),
                    label=primary_label,
                    confidence=conf,
                )
            )

        return results

    def detect(
        self,
        image: Union[str, Path, Image.Image, np.ndarray],
        text_prompt: str = "cotton weed . broadleaf plant . unwanted vegetation .",
        box_threshold: Optional[float] = None,
        text_threshold: Optional[float] = None,
    ) -> List[DetectionResult]:
        """
        Execute zero-shot detection on the input image using natural language query.
        
        Args:
            image: Path to image file, PIL Image, or NumPy array.
            text_prompt: Dot-separated phrases describing target objects.
                         Grounding DINO convention requires trailing periods:
                         e.g. "cotton weed . broadleaf plant ."
            box_threshold: Override instance default bounding box threshold.
            text_threshold: Override instance default text token threshold.

        Returns:
            List[DetectionResult]: Detected objects with absolute & normalized boxes.
        """
        pil_img = self._normalize_image_input(image)
        w, h = pil_img.size

        effective_box_th = box_threshold if box_threshold is not None else self.box_threshold
        effective_text_th = text_threshold if text_threshold is not None else self.text_threshold

        # Ensure text prompt conforms to Grounding DINO syntax (ends with a period)
        formatted_prompt = text_prompt.strip()
        if not formatted_prompt.endswith("."):
            formatted_prompt += " ."

        # Branch 1: Mock / Fallback execution
        if self.mock_mode or self._model is None or self._processor is None:
            logger.debug("Executing Grounding DINO in mock mode.")
            return self._generate_mock_detections(w, h, formatted_prompt)

        # Branch 2: Live Deep Learning Inference
        import torch

        inputs = self._processor(images=pil_img, text=formatted_prompt, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self._model(**inputs)

        # Post-process raw logits to target image dimensions
        results = self._processor.post_process_grounded_object_detection(
            outputs=outputs,
            input_ids=inputs.input_ids,
            box_threshold=effective_box_th,
            text_threshold=effective_text_th,
            target_sizes=[(h, w)],
        )[0]

        detections: List[DetectionResult] = []
        for box, score, label in zip(results["boxes"], results["scores"], results["labels"]):
            abs_box = box.cpu().tolist()
            x1, y1, x2, y2 = abs_box
            norm_box = (x1 / w, y1 / h, x2 / w, y2 / h)
            conf = float(score.cpu().item())

            detections.append(
                DetectionResult(
                    box=(x1, y1, x2, y2),
                    normalized_box=norm_box,
                    label=str(label),
                    confidence=conf,
                )
            )

        logger.info("Grounding DINO detected %d instances for query: '%s'", len(detections), formatted_prompt)
        return detections

    def detect_to_state_boxes(
        self,
        image: Union[str, Path, Image.Image, np.ndarray],
        text_prompt: str = "cotton weed . broadleaf plant .",
        box_threshold: Optional[float] = None,
    ) -> List[Box]:
        """Convenience method returning detections directly formatted for LangGraph GraphState."""
        detections = self.detect(image, text_prompt=text_prompt, box_threshold=box_threshold)
        return [d.to_dict() for d in detections]
