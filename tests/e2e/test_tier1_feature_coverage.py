"""
tests/e2e/test_tier1_feature_coverage.py
Tier 1: Feature Coverage & Core Pipeline Integration Tests.

Verifies:
1. End-to-end perception-to-actuation pipeline from image input to spray map output.
2. Pipeline execution against real agricultural field imagery (Cotton & Sugarbeet fixtures).
3. Contract compliance of all output state dictionaries (GraphState, Box, Mask, SprayMap, Artifact).
4. Closed-loop active mask refinement state transitions.
5. Agronomy RAG safe no-knowledge handling and evidence traceability.
6. System-1 to System-2 deliberation escalation flow.
7. Deterministic spray map calculation invariants on nominal field imagery.
"""

import unittest
from pathlib import Path
import numpy as np
from PIL import Image

from src.state import Artifact, ArtifactType, Box, GraphState, Mask
from src.workflow import VisionWorkflowRunner, create_initial_state
from src.agronomy.prescription import get_herbicide_prescription, DISCLAIMER
from src.agronomy.system2_node import System2Reasoner
from src.evaluation.iou_dice import compute_iou, compute_dice, compute_herbicide_savings
from tests.e2e.fixtures import (
    InMemoryKnowledgeStore,
    create_test_field_image,
    get_sample_image_path,
)


class TestTier1FeatureCoverage(unittest.TestCase):
    """Tier 1 E2E Feature Coverage and Happy Path Test Suite."""

    def setUp(self):
        self.runner = VisionWorkflowRunner(mock_mode=True, iou_threshold=0.85, max_refinements=2)
        self.test_image = create_test_field_image(width=640, height=480)
        self.mock_store = InMemoryKnowledgeStore()

    def test_e2e_pipeline_execution_synthetic_image(self):
        """Verify full perception-to-spray-map execution on synthetic field imagery."""
        initial_state = create_initial_state(
            image=self.test_image,
            text_prompt="cotton weed . broadleaf plant .",
        )
        final_state = self.runner.run(initial_state)

        # 1. Pipeline produced detections and masks
        self.assertIn("boxes", final_state)
        self.assertIn("masks", final_state)
        self.assertGreater(len(final_state["boxes"]), 0, "Pipeline must detect candidate boxes")
        self.assertEqual(
            len(final_state["boxes"]),
            len(final_state["masks"]),
            "Every detected box must correspond to a segmented instance mask",
        )

        # 2. Pipeline generated valid spray map
        self.assertIn("spray_map", final_state)
        spray_map = final_state["spray_map"]
        self.assertIsNotNone(spray_map)
        self.assertIn("infestation_percentage", spray_map)
        self.assertIn("chemical_savings_percentage", spray_map)
        self.assertIn("weed_count", spray_map)
        self.assertEqual(spray_map["weed_count"], len(final_state["masks"]))

        # 3. Spray map artifact generated
        self.assertIn("artifacts", final_state)
        self.assertIn("spray_map", final_state["artifacts"])
        spray_artifact = final_state["artifacts"]["spray_map"]
        self.assertIsInstance(spray_artifact, Artifact)
        self.assertEqual(spray_artifact.type, ArtifactType.SPRAY_MAP)
        self.assertIn("composite_mask", spray_artifact.payload)
        self.assertEqual(spray_artifact.payload["composite_mask"].shape, (480, 640))

    def test_e2e_pipeline_with_real_cotton_fixture(self):
        """Verify end-to-end execution on real cotton field fixture image."""
        img_path = get_sample_image_path("cotton_20190613_6062W_CM_11.jpg")
        real_image = Image.open(img_path).convert("RGB")
        w, h = real_image.size

        initial_state = create_initial_state(
            image=real_image,
            text_prompt="cotton weed .",
            image_path=str(img_path),
        )
        final_state = self.runner.run(initial_state)

        # Confirm dimensions match the real image dimensions
        self.assertIn("spray_map", final_state)
        spray_map = final_state["spray_map"]
        self.assertEqual(spray_map["target_resolution"]["width"], w)
        self.assertEqual(spray_map["target_resolution"]["height"], h)

        composite_mask = final_state["artifacts"]["spray_map"].payload["composite_mask"]
        self.assertEqual(composite_mask.shape, (h, w))
        self.assertEqual(composite_mask.dtype, bool)

    def test_e2e_pipeline_with_real_sugarbeet_fixture(self):
        """Verify end-to-end execution on real sugarbeet field fixture image."""
        img_path = get_sample_image_path("beet_X-10-0.png")
        real_image = Image.open(img_path).convert("RGB")
        w, h = real_image.size

        initial_state = create_initial_state(
            image=real_image,
            text_prompt="sugarbeet weed . grass .",
            image_path=str(img_path),
        )
        final_state = self.runner.run(initial_state)

        spray_map = final_state["spray_map"]
        self.assertGreater(spray_map["chemical_savings_percentage"], 0.0)
        self.assertLessEqual(spray_map["chemical_savings_percentage"], 100.0)

    def test_contract_verification_graph_state_schema(self):
        """Validate all required keys and typing constraints of GraphState contract."""
        initial_state = create_initial_state(self.test_image)
        final_state = self.runner.run(initial_state)

        # Check all core GraphState fields from src/state.py
        expected_keys = [
            "messages", "artifacts", "error", "image", "image_path",
            "text_prompt", "field_metadata", "boxes", "masks",
            "refinement_count", "system2_needed", "vlm_reasoning",
            "prescription_report", "spray_map", "ground_truth_masks",
            "evaluation_metrics",
        ]
        for key in expected_keys:
            self.assertIn(key, final_state, f"GraphState missing mandatory key: {key}")

        self.assertIsInstance(final_state["boxes"], list)
        self.assertIsInstance(final_state["masks"], list)
        self.assertIsInstance(final_state["artifacts"], dict)
        self.assertIsInstance(final_state["refinement_count"], int)
        self.assertIsInstance(final_state["system2_needed"], bool)

    def test_contract_verification_box_contract(self):
        """Validate Box TypedDict spatial bounds and field types."""
        initial_state = create_initial_state(self.test_image)
        final_state = self.runner.run(initial_state)

        img_w, img_h = self.test_image.size
        for box in final_state["boxes"]:
            # Type and existence check
            self.assertIn("x1", box)
            self.assertIn("y1", box)
            self.assertIn("x2", box)
            self.assertIn("y2", box)
            self.assertIn("label", box)
            self.assertIn("score", box)

            # Spatial boundary invariants
            self.assertGreaterEqual(box["x1"], 0.0)
            self.assertGreaterEqual(box["y1"], 0.0)
            self.assertLess(box["x1"], box["x2"])
            self.assertLess(box["y1"], box["y2"])
            self.assertLessEqual(box["x2"], img_w)
            self.assertLessEqual(box["y2"], img_h)

            # Score and label invariants
            self.assertGreaterEqual(box["score"], 0.0)
            self.assertLessEqual(box["score"], 1.0)
            self.assertIsInstance(box["label"], str)
            self.assertTrue(len(box["label"]) > 0)

    def test_contract_verification_mask_contract(self):
        """Validate Mask TypedDict binary array and predicted IoU bounds."""
        initial_state = create_initial_state(self.test_image)
        final_state = self.runner.run(initial_state)

        img_w, img_h = self.test_image.size
        for mask in final_state["masks"]:
            self.assertIn("mask_array", mask)
            self.assertIn("predicted_iou", mask)
            self.assertIn("box", mask)
            self.assertIn("label", mask)

            # Mask array invariants
            arr = mask["mask_array"]
            self.assertIsInstance(arr, np.ndarray)
            self.assertEqual(arr.shape, (img_h, img_w))
            self.assertEqual(arr.dtype, bool)

            # Predicted IoU bounds
            self.assertGreaterEqual(mask["predicted_iou"], 0.0)
            self.assertLessEqual(mask["predicted_iou"], 1.0)

    def test_contract_verification_spray_map_contract(self):
        """Validate SprayMap structure, percentage bounds, and coordinate fidelity."""
        initial_state = create_initial_state(self.test_image)
        final_state = self.runner.run(initial_state)

        sm = final_state["spray_map"]
        self.assertIsInstance(sm["infestation_percentage"], float)
        self.assertIsInstance(sm["chemical_savings_percentage"], float)
        self.assertIsInstance(sm["weed_count"], int)
        self.assertIsInstance(sm["buffer_pixels"], int)

        # Invariant: percentages must be within [0.0, 100.0]
        self.assertGreaterEqual(sm["infestation_percentage"], 0.0)
        self.assertLessEqual(sm["infestation_percentage"], 100.0)
        self.assertGreaterEqual(sm["chemical_savings_percentage"], 0.0)
        self.assertLessEqual(sm["chemical_savings_percentage"], 100.0)

    def test_active_closed_loop_refinement_transition(self):
        """Verify active refinement loop triggers when mask IoU < threshold."""
        # Create segmenter with lower initial mock IoU to trigger refinement
        runner = VisionWorkflowRunner(
            mock_mode=True,
            iou_threshold=0.85,
            max_refinements=2,
        )
        runner.segmenter.default_mock_iou = 0.72  # Below 0.85 threshold

        initial_state = create_initial_state(self.test_image)
        final_state = runner.run(initial_state)

        # Refinement count must have advanced
        self.assertGreater(final_state["refinement_count"], 0)
        self.assertLessEqual(final_state["refinement_count"], 2)

        # Refined masks should have improved IoU
        for m in final_state["masks"]:
            self.assertGreater(m["predicted_iou"], 0.72)

    def test_agronomy_rag_known_query_returns_evidence(self):
        """Verify statutory RAG returns grounded citations for known weed queries."""
        report = get_herbicide_prescription(
            weed_name="Testweed alpha",
            crop_stage="vegetative",
            crop="cotton",
            store=self.mock_store,
        )

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["weed"], "Testweed alpha")
        self.assertEqual(report["crop"], "cotton")
        self.assertEqual(report["crop_stage"], "vegetative")
        self.assertGreater(len(report["evidence"]), 0)

        # Verify evidence citations contain source provenance
        first_citation = report["evidence"][0]
        self.assertIn("text", first_citation)
        self.assertIn("source", first_citation)
        self.assertIn("page", first_citation)
        self.assertIn("authority", first_citation)
        self.assertEqual(first_citation["source"], "agronomy_test_doc.txt")
        self.assertEqual(first_citation["authority"], "ICAR")
        self.assertEqual(report["disclaimer"], DISCLAIMER)

    def test_agronomy_rag_safe_no_knowledge_fallback(self):
        """Verify RAG returns safe no_knowledge_found without hallucinating on unknown weeds."""
        unknown_weed = "NonExistentExtraterrestrialWeed_XYZ"
        report = get_herbicide_prescription(
            weed_name=unknown_weed,
            crop_stage="flowering",
            crop="cotton",
            store=self.mock_store,
        )

        # Critical safety contract: status must be no_knowledge_found and evidence empty
        self.assertEqual(report["status"], "no_knowledge_found")
        self.assertEqual(report["evidence"], [])
        self.assertEqual(report["weed"], unknown_weed)
        self.assertIn("disclaimer", report)

    def test_system1_to_system2_escalation_flow(self):
        """Verify low-confidence or ambiguous detections escalate to System-2 reasoning."""
        s2_reasoner = System2Reasoner(store=self.mock_store, mock_mode=True)
        runner = VisionWorkflowRunner(
            mock_mode=True,
            system2=s2_reasoner,
        )

        # Force escalation by introducing low score box
        initial_state = create_initial_state(self.test_image)
        initial_state["boxes"] = [
            {"x1": 10.0, "y1": 10.0, "x2": 80.0, "y2": 80.0, "label": "ambiguous_foliage", "score": 0.45}
        ]
        initial_state["masks"] = [
            {
                "mask_array": np.zeros((480, 640), dtype=bool),
                "predicted_iou": 0.60,
                "box": initial_state["boxes"][0],
                "label": "ambiguous_foliage",
            }
        ]

        # Evaluate escalation directly through router
        escalate, reason = runner.laya_router.evaluate_system2_escalation(
            detection_confidence=0.45,
            label="ambiguous_foliage",
            predicted_iou=0.60,
            min_confidence=0.70,
        )
        self.assertTrue(escalate, "Low confidence must trigger System-2 escalation")
        self.assertIn("Low detection confidence", reason)

        # Run system2_node directly to verify state transition
        initial_state["system2_needed"] = True
        s2_out = s2_reasoner.system2_node(initial_state)

        self.assertIn("vlm_reasoning", s2_out)
        self.assertIn("prescription_report", s2_out)
        self.assertIn("prescription_report", s2_out["artifacts"])
        self.assertEqual(
            s2_out["artifacts"]["prescription_report"].type,
            ArtifactType.PRESCRIPTION_REPORT,
        )

    def test_deterministic_spray_map_invariants_nominal_run(self):
        """Verify physical conservation of area and herbicide savings invariants."""
        initial_state = create_initial_state(self.test_image)
        final_state = self.runner.run(initial_state)

        sm = final_state["spray_map"]
        comp_mask = final_state["artifacts"]["spray_map"].payload["composite_mask"]
        h, w = comp_mask.shape

        weed_pixels = int(comp_mask.sum())
        total_pixels = h * w

        expected_infestation = round((weed_pixels / total_pixels) * 100.0, 2)
        self.assertAlmostEqual(sm["infestation_percentage"], expected_infestation, places=2)

        # When weeds occupy < 50% of the image, chemical savings must be > 50% (minus buffer)
        if expected_infestation < 30.0:
            self.assertGreater(sm["chemical_savings_percentage"], 50.0)


if __name__ == "__main__":
    unittest.main()
