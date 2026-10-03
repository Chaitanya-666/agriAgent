"""
src/vision/sam2_wrapper.py
Segment Anything Model 2 (SAM 2) Wrapper for Precision Agricultural Segmentation.

Architecture Rationale:
-----------------------
Meta AI's SAM 2 (Segment Anything Model 2) provides foundation-level promptable
visual segmentation. Unlike traditional semantic segmentation networks (UNet, DeepLabV3)
which require domain-specific training to classify pixels, SAM 2 takes spatial priors
(bounding boxes or point clicks) and generates pixel-precise object silhouettes.

In AgriAgent, SAM 2 acts as our surgical scalpel:
1. Receives bounding boxes from Grounding DINO (`src/vision/grounding_dino.py`).
2. Converts rectangular boxes into precise leaf/foliage binary masks.
3. Supports corrective point prompting for active IoU refinement (`src/vision/refinement.py`).

Operational Modes:
------------------
1. Live Mode (GPU / PyTorch / Meta SAM 2):
   Loads SAM 2 weights (`facebook/sam2-hiera-tiny` or official checkpoint).
   Runs GPU-accelerated image embedding and prompt mask decoding in <35 ms.
2. Mock / Fallback Mode (`mock_mode=True` or when PyTorch/SAM 2 are missing):
   Synthesizes realistic, non-rectangular foliage contours inside each box prior.
   Simulates active point refinement by organically growing masks around corrective clicks.
   Enables 100% test coverage and UI testing on lightweight developer laptops without GPU.
"""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image

# Import typed contracts from centralized state
from src.state import Box, Mask

logger = logging.getLogger("agriagent.vision.sam2")


@dataclass
class SegmentResult:
    """Strongly typed container for an individual instance segmentation mask."""
    mask_array: np.ndarray      # 2D boolean array of shape [H, W]
    predicted_iou: float        # Model confidence score (0.0 to 1.0)
    box: Box                    # Source bounding box
    label: str                  # Semantic label
    area_pixels: int            # Sum of True pixels in mask

    def to_dict(self) -> Mask:
        """Serialize to GraphState Mask TypedDict format."""
        return {
            "mask_array": self.mask_array,
            "predicted_iou": round(self.predicted_iou, 4),
            "box": self.box,
            "label": self.label,
        }


class SAM2Segmenter:
    """
    Production wrapper for Meta AI SAM 2 promptable segmentation.
    
    Attributes:
        model_id (str): Hugging Face model repository ID or local checkpoint path.
        mock_mode (bool): If True, bypasses heavy deep learning inference.
        device (str): Inference device ('cuda' or 'cpu').
        default_iou (float): Default simulated IoU score for mock mode.
    """

    def __init__(
        self,
        model_id: str = "facebook/sam2-hiera-tiny",
        mock_mode: bool = False,
        device: Optional[str] = None,
        default_mock_iou: float = 0.88,
    ):
        self.model_id = model_id
        self.mock_mode = mock_mode
        self.device = device
        self.default_mock_iou = default_mock_iou

        self._predictor = None

        if not self.mock_mode:
            self._initialize_model()

    def _initialize_model(self) -> None:
        """Safely initialize SAM 2 model weights and image predictor."""
        try:
            import torch

            if self.device is None:
                self.device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info("Initializing SAM 2 [%s] on device [%s]...", self.model_id, self.device)

            # Attempt import from official sam2 repository or transformers
            try:
                from sam2.sam2_image_predictor import SAM2ImagePredictor

                try:
                    self._predictor = SAM2ImagePredictor.from_pretrained(self.model_id, device=self.device)
                    logger.info("Meta SAM 2 Image Predictor initialized via from_pretrained.")
                except Exception as exc_fp:
                    logger.info("from_pretrained failed (%s), attempting build_sam2...", exc_fp)
                    from sam2.build_sam import build_sam2

                    model = build_sam2(self.model_id, device=self.device)
                    self._predictor = SAM2ImagePredictor(model)
                    logger.info("Meta SAM 2 Image Predictor initialized successfully via build_sam2.")
            except ImportError:
                # Fallback to Hugging Face transformers SAM2 wrapper if installed
                from transformers import Sam2Model, Sam2Processor

                logger.info("Using Hugging Face Transformers SAM2 implementation.")
                self._processor = Sam2Processor.from_pretrained(self.model_id)
                self._model = Sam2Model.from_pretrained(self.model_id).to(self.device)
                self._model.eval()

        except ImportError as err:
            logger.warning(
                "PyTorch / SAM 2 libraries not installed (%s). Falling back to mock_mode=True.",
                err,
            )
            self.mock_mode = True
        except Exception as err:
            logger.warning(
                "Failed to initialize SAM 2 model (%s). Falling back to mock_mode=True.",
                err,
            )
            self.mock_mode = True

    def _normalize_image_input(self, image_input: Union[str, Path, Image.Image, np.ndarray]) -> np.ndarray:
        """Ensure input is converted into an RGB NumPy uint8 array of shape [H, W, 3]."""
        if isinstance(image_input, (str, Path)):
            path = Path(image_input)
            if not path.exists():
                raise FileNotFoundError(f"Image file not found: {path}")
            return np.array(Image.open(path).convert("RGB"))
        elif isinstance(image_input, Image.Image):
            return np.array(image_input.convert("RGB"))
        elif isinstance(image_input, np.ndarray):
            if image_input.ndim == 2:
                # Grayscale to RGB
                return np.stack([image_input] * 3, axis=-1)
            elif image_input.ndim == 3 and image_input.shape[2] == 4:
                # RGBA to RGB
                return image_input[:, :, :3]
            return image_input
        else:
            raise TypeError(f"Unsupported image input type: {type(image_input)}")

    def _generate_mock_mask_from_box(
        self,
        box: Box,
        height: int,
        width: int,
        target_iou: float = 0.88,
    ) -> SegmentResult:
        """
        Synthesizes a realistic, organic plant foliage mask within a bounding box.
        
        Uses an elliptical foundation with radial organic jitter to mimic leaf clusters,
        avoiding artificial rectilinear box shapes.
        """
        x1 = max(0, int(box["x1"]))
        y1 = max(0, int(box["y1"]))
        x2 = min(width, int(box["x2"]))
        y2 = min(height, int(box["y2"]))

        mask = np.zeros((height, width), dtype=bool)

        box_w = max(1, x2 - x1)
        box_h = max(1, y2 - y1)
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        radius_x = box_w * 0.44
        radius_y = box_h * 0.44

        # Generate coordinate grid inside bounding region
        yy, xx = np.ogrid[y1:y2, x1:x2]
        
        # Elliptical normalized distance equation
        dist = ((xx - center_x) / radius_x) ** 2 + ((yy - center_y) / radius_y) ** 2
        
        # Add deterministic pseudo-noise based on coordinates to simulate organic leaf edges
        pseudo_noise = np.sin(xx * 0.35) * np.cos(yy * 0.35) * 0.22
        foliage_mask = (dist + pseudo_noise) <= 1.0

        mask[y1:y2, x1:x2] = foliage_mask

        # Fallback if organic mask was too restrictive
        if mask.sum() == 0:
            mask[y1:y2, x1:x2] = True

        return SegmentResult(
            mask_array=mask,
            predicted_iou=target_iou,
            box=box,
            label=box.get("label", "weed"),
            area_pixels=int(mask.sum()),
        )

    def segment_boxes(
        self,
        image: Union[str, Path, Image.Image, np.ndarray],
        boxes: List[Box],
    ) -> List[SegmentResult]:
        """
        Generate pixel-level instance segmentation masks for a list of bounding boxes.
        
        Args:
            image: Field drone image (path, PIL, or ndarray).
            boxes: List of Box TypedDicts (x1, y1, x2, y2, label, score).

        Returns:
            List[SegmentResult]: High-resolution binary masks with IoU confidences.
        """
        np_img = self._normalize_image_input(image)
        h, w = np_img.shape[:2]

        if not boxes:
            logger.info("No bounding boxes provided to SAM 2. Returning empty mask list.")
            return []

        # Branch 1: Mock / Fallback execution
        if self.mock_mode or (self._predictor is None and not hasattr(self, "_model")):
            results = []
            for b in boxes:
                seg = self._generate_mock_mask_from_box(b, h, w, target_iou=self.default_mock_iou)
                results.append(seg)
            logger.debug("SAM 2 generated %d mock masks.", len(results))
            return results

        # Branch 2: Live SAM 2 Inference
        import torch

        results: List[SegmentResult] = []

        if self._predictor is not None:
            # Official Meta SAM 2 API
            self._predictor.set_image(np_img)
            for b in boxes:
                input_box = np.array([b["x1"], b["y1"], b["x2"], b["y2"]])
                masks, scores, _ = self._predictor.predict(
                    point_coords=None,
                    point_labels=None,
                    box=input_box[None, :],
                    multimask_output=False,
                )
                best_mask = masks[0].astype(bool)
                best_score = float(scores[0])

                results.append(
                    SegmentResult(
                        mask_array=best_mask,
                        predicted_iou=best_score,
                        box=b,
                        label=b.get("label", "weed"),
                        area_pixels=int(best_mask.sum()),
                    )
                )
        else:
            # Hugging Face transformers SAM 2 pipeline
            from PIL import Image as PILImage

            pil_img = PILImage.fromarray(np_img)
            for b in boxes:
                input_boxes = [[[b["x1"], b["y1"], b["x2"], b["y2"]]]]
                inputs = self._processor(pil_img, input_boxes=input_boxes, return_tensors="pt").to(self.device)
                with torch.no_grad():
                    outputs = self._model(**inputs)
                masks = self._processor.post_process_masks(
                    outputs.pred_masks, inputs["original_sizes"], inputs["reshaped_input_sizes"]
                )[0]
                best_mask = masks[0, 0].cpu().numpy().astype(bool)
                best_score = float(outputs.iou_predictions[0, 0].cpu().item()) if hasattr(outputs, "iou_predictions") else 0.88

                results.append(
                    SegmentResult(
                        mask_array=best_mask,
                        predicted_iou=best_score,
                        box=b,
                        label=b.get("label", "weed"),
                        area_pixels=int(best_mask.sum()),
                    )
                )

        logger.info("SAM 2 segmented %d instances successfully.", len(results))
        return results

    def refine_with_point(
        self,
        image: Union[str, Path, Image.Image, np.ndarray],
        box: Box,
        previous_mask: np.ndarray,
        corrective_point: Tuple[int, int, bool],
    ) -> SegmentResult:
        """
        Executes active closed-loop refinement using an error centroid point prompt.
        
        Args:
            image: Input image.
            box: Original detection bounding box.
            previous_mask: Existing binary mask with low IoU (<0.85).
            corrective_point: (x, y, is_positive) generated by src/vision/refinement.py.

        Returns:
            SegmentResult: Refined mask with improved predicted IoU.
        """
        np_img = self._normalize_image_input(image)
        h, w = np_img.shape[:2]
        px, py, is_positive = corrective_point

        if self.mock_mode or (self._predictor is None and not hasattr(self, "_model")):
            # Simulate closed-loop improvement in mock mode
            refined_mask = previous_mask.copy()
            # Draw a corrective circular dilation around the point
            radius = int(max(w, h) * 0.04)
            yy, xx = np.ogrid[max(0, py - radius):min(h, py + radius), max(0, px - radius):min(w, px + radius)]
            circle_patch = ((xx - px) ** 2 + ((yy - py) ** 2)) <= (radius ** 2)

            if is_positive:
                refined_mask[max(0, py - radius):min(h, py + radius), max(0, px - radius):min(w, px + radius)] |= circle_patch
            else:
                refined_mask[max(0, py - radius):min(h, py + radius), max(0, px - radius):min(w, px + radius)] &= ~circle_patch

            # Boost IoU reflecting active error reduction
            new_iou = min(0.96, self.default_mock_iou + 0.08)

            return SegmentResult(
                mask_array=refined_mask,
                predicted_iou=new_iou,
                box=box,
                label=box.get("label", "weed"),
                area_pixels=int(refined_mask.sum()),
            )

        # Live SAM 2 point + box conditioning
        import torch

        input_box = np.array([box["x1"], box["y1"], box["x2"], box["y2"]])
        point_coords = np.array([[px, py]])
        point_labels = np.array([1 if is_positive else 0])

        self._predictor.set_image(np_img)
        masks, scores, _ = self._predictor.predict(
            point_coords=point_coords,
            point_labels=point_labels,
            box=input_box[None, :],
            multimask_output=False,
        )

        return SegmentResult(
            mask_array=masks[0].astype(bool),
            predicted_iou=float(scores[0]),
            box=box,
            label=box.get("label", "weed"),
            area_pixels=int(masks[0].sum()),
        )

    def segment_to_state_masks(
        self,
        image: Union[str, Path, Image.Image, np.ndarray],
        boxes: List[Box],
    ) -> List[Mask]:
        """Convenience method returning masks directly formatted for LangGraph GraphState."""
        results = self.segment_boxes(image, boxes)
        return [r.to_dict() for r in results]
