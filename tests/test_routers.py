"""
tests/test_routers.py
Unit and contract test suite for AgriAgent System-1 routers:
- DeterministicRouter (sub-millisecond fast reflex)
- LayaTriageRouter (non-autoregressive triage engine)
- ClefFlashRouter (Cloudflare Clef Flash / Qwen3.5-9B multimodal model)
"""

import time
import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from PIL import Image

from src.agents import (
    BaseRouter,
    ClefFlashRouter,
    DeterministicRouter,
    LayaTriageRouter,
    RouterAction,
    RouterBackend,
    RouterDecision,
)


class TestRouterContractCompliance(unittest.TestCase):
    """Verifies all routers implement the BaseRouter contract and return valid RouterDecision objects."""

    def setUp(self):
        self.deterministic_router = DeterministicRouter()
        self.laya_router = LayaTriageRouter()
        self.clef_flash_router = ClefFlashRouter(mock_mode=True)
        self.routers = [
            self.deterministic_router,
            self.laya_router,
            self.clef_flash_router,
        ]

    def test_inheritance_and_backends(self):
        for router in self.routers:
            self.assertIsInstance(router, BaseRouter)
            self.assertIsInstance(router.backend, RouterBackend)

        self.assertEqual(self.deterministic_router.backend, RouterBackend.DETERMINISTIC)
        self.assertEqual(self.laya_router.backend, RouterBackend.LAYA)
        self.assertEqual(self.clef_flash_router.backend, RouterBackend.CLEF_FLASH)

    def test_decision_structure_validity(self):
        for router in self.routers:
            decision = router.route(
                detection_confidence=0.92,
                predicted_iou=0.94,
                area_pixels=1500,
                species_ambiguity=False,
            )
            self.assertIsInstance(decision, RouterDecision)
            self.assertIsInstance(decision.action, RouterAction)
            self.assertIsInstance(decision.reason, str)
            self.assertGreater(len(decision.reason), 0)
            self.assertIsInstance(decision.latency_ms, float)
            self.assertGreaterEqual(decision.latency_ms, 0.0)
            self.assertEqual(decision.backend, router.backend)
            self.assertTrue(0.0 <= decision.confidence <= 1.0)
            self.assertIsInstance(decision.probabilities, dict)
            self.assertIsInstance(decision.metadata, dict)


class TestDeterministicRouter(unittest.TestCase):
    """Tests sub-millisecond System 1 fast reflex router."""

    def setUp(self):
        self.router = DeterministicRouter()

    def test_sub_millisecond_latency(self):
        """Deterministic reflex decisions must execute in sub-millisecond time (<1.0 ms)."""
        latencies = []
        for _ in range(100):
            decision = self.router.route(detection_confidence=0.95, predicted_iou=0.92)
            latencies.append(decision.latency_ms)

        mean_latency = sum(latencies) / len(latencies)
        self.assertLess(mean_latency, 1.0, f"Mean latency {mean_latency:.4f} ms must be sub-millisecond.")

    def test_accept_high_confidence_clean_mask(self):
        decision = self.router.route(
            detection_confidence=0.90,
            predicted_iou=0.88,
        )
        self.assertEqual(decision.action, RouterAction.ACCEPT)
        self.assertIn("approved", decision.reason.lower())

    def test_refine_sub_threshold_iou(self):
        decision = self.router.route(
            detection_confidence=0.90,
            predicted_iou=0.74,
            iou_threshold=0.85,
        )
        self.assertEqual(decision.action, RouterAction.REFINE)
        self.assertIn("refinement", decision.reason.lower())

    def test_escalate_low_detection_confidence(self):
        decision = self.router.route(
            detection_confidence=0.55,
            predicted_iou=0.90,
            min_confidence=0.70,
        )
        self.assertEqual(decision.action, RouterAction.ESCALATE_SYSTEM2)
        self.assertIn("low detection confidence", decision.reason.lower())

    def test_escalate_species_ambiguity(self):
        decision = self.router.route(
            detection_confidence=0.90,
            predicted_iou=0.90,
            species_ambiguity=True,
            label="parthenium",
        )
        self.assertEqual(decision.action, RouterAction.ESCALATE_SYSTEM2)
        self.assertIn("ambiguity", decision.reason.lower())

    def test_suppress_spray_excessive_infestation(self):
        decision = self.router.route(
            detection_confidence=0.90,
            predicted_iou=0.90,
            infestation_pct=92.5,
            max_allowed_infestation=85.0,
        )
        self.assertEqual(decision.action, RouterAction.SUPPRESS_SPRAY)
        self.assertIn("suppressed", decision.reason.lower())

    def test_fast_helper_methods(self):
        self.assertTrue(self.router.evaluate_mask_refinement(0.80, threshold=0.85))
        self.assertFalse(self.router.evaluate_mask_refinement(0.88, threshold=0.85))

        esc, _ = self.router.evaluate_system2_escalation(0.60, min_confidence=0.70)
        self.assertTrue(esc)

        safe = self.router.verify_spray_safety(70.0, max_allowed_infestation=85.0)
        self.assertTrue(safe)
        unsafe = self.router.verify_spray_safety(90.0, max_allowed_infestation=85.0)
        self.assertFalse(unsafe)


class TestLayaRouter(unittest.TestCase):
    """Tests Laya router contract implementation and backward compatibility."""

    def setUp(self):
        self.router = LayaTriageRouter()

    def test_laya_backend_identifier(self):
        self.assertEqual(self.router.backend, RouterBackend.LAYA)

    def test_laya_route_accept_flow(self):
        decision = self.router.route(
            detection_confidence=0.88,
            predicted_iou=0.90,
        )
        self.assertEqual(decision.action, RouterAction.ACCEPT)
        self.assertEqual(decision.backend, RouterBackend.LAYA)

    def test_laya_route_refine_flow(self):
        decision = self.router.route(
            detection_confidence=0.88,
            predicted_iou=0.78,
            iou_threshold=0.85,
        )
        self.assertEqual(decision.action, RouterAction.REFINE)

    def test_laya_route_escalate_flow(self):
        decision = self.router.route(
            detection_confidence=0.55,
            predicted_iou=0.90,
            min_confidence=0.70,
        )
        self.assertEqual(decision.action, RouterAction.ESCALATE_SYSTEM2)

    def test_laya_route_safety_suppression(self):
        decision = self.router.route(
            detection_confidence=0.90,
            predicted_iou=0.90,
            infestation_pct=95.0,
            max_allowed_infestation=85.0,
        )
        self.assertEqual(decision.action, RouterAction.SUPPRESS_SPRAY)

    def test_laya_backward_compatibility_methods(self):
        """Preserves existing helper methods with unchanged behavior."""
        self.assertTrue(self.router.evaluate_mask_refinement(0.82, 400, "weed", threshold=0.85))
        self.assertFalse(self.router.evaluate_mask_refinement(0.86, 400, "weed", threshold=0.85))

        esc, reason = self.router.evaluate_system2_escalation(0.85, "weed", 0.90)
        self.assertFalse(esc)
        self.assertIn("approved", reason.lower())

        self.assertTrue(self.router.verify_spray_safety(50.0))
        self.assertFalse(self.router.verify_spray_safety(90.0))


class TestClefFlashRouter(unittest.TestCase):
    """Tests Cloudflare Clef Flash router multimodal capabilities, probability parsing, and fallback."""

    def setUp(self):
        self.router = ClefFlashRouter(mock_mode=True)

    def test_clef_flash_backend_identifier(self):
        self.assertEqual(self.router.backend, RouterBackend.CLEF_FLASH)

    def test_multimodal_image_crop_handling(self):
        """Supports numpy arrays, PIL images, and None as image crops."""
        # 1. NumPy array crop
        np_crop = np.full((64, 64, 3), [40, 180, 50], dtype=np.uint8)
        dec_np = self.router.route(
            detection_confidence=0.90,
            predicted_iou=0.88,
            image_crop=np_crop,
        )
        self.assertTrue(dec_np.metadata.get("multimodal_image_present"))

        # 2. PIL Image crop
        pil_crop = Image.new("RGB", (64, 64), color=(30, 150, 40))
        dec_pil = self.router.route(
            detection_confidence=0.90,
            predicted_iou=0.88,
            image_crop=pil_crop,
        )
        self.assertTrue(dec_pil.metadata.get("multimodal_image_present"))

        # 3. None crop
        dec_none = self.router.route(
            detection_confidence=0.90,
            predicted_iou=0.88,
            image_crop=None,
        )
        self.assertFalse(dec_none.metadata.get("multimodal_image_present"))

    def test_probability_distribution_normalization(self):
        """Probabilities across candidate actions must sum approximately to 1.0."""
        decision = self.router.route(
            detection_confidence=0.85,
            predicted_iou=0.72,
        )
        self.assertIn(RouterAction.REFINE.value, decision.probabilities)
        prob_sum = sum(decision.probabilities.values())
        self.assertAlmostEqual(prob_sum, 1.0, places=2)

    def test_fail_safe_network_fallback(self):
        """When cloud inference raises an exception, the router must fall back to local deterministic router without crashing."""
        live_router = ClefFlashRouter(
            api_token="dummy-token",
            account_id="dummy-account",
            mock_mode=False,
        )

        # Force network exception
        with patch.object(live_router, "_execute_cloud_inference", side_effect=TimeoutError("Connection timed out")):
            decision = live_router.route(
                detection_confidence=0.92,
                predicted_iou=0.90,
            )

            self.assertIsInstance(decision, RouterDecision)
            self.assertEqual(decision.backend, RouterBackend.CLEF_FLASH)
            self.assertTrue(decision.metadata.get("fallback_triggered"))
            self.assertIn("Connection timed out", decision.metadata.get("fallback_reason"))
            # High confidence and clean IoU falls back to ACCEPT
            self.assertEqual(decision.action, RouterAction.ACCEPT)


class TestRouterComparisonBenchmark(unittest.TestCase):
    """Compares decisions and latencies across Deterministic, Laya, and Clef Flash routers."""

    def setUp(self):
        self.det = DeterministicRouter()
        self.laya = LayaTriageRouter()
        self.clef = ClefFlashRouter(mock_mode=True)

    def test_statutory_spray_safety_consensus(self):
        """All three routers must unconditionally suppress spray when infestation exceeds 85%."""
        for router in [self.det, self.laya, self.clef]:
            decision = router.route(
                detection_confidence=0.95,
                predicted_iou=0.95,
                infestation_pct=90.0,
                max_allowed_infestation=85.0,
            )
            self.assertEqual(
                decision.action,
                RouterAction.SUPPRESS_SPRAY,
                f"Router {router.backend} failed to suppress spray at 90% infestation.",
            )

    def test_refinement_trigger_consensus(self):
        """All three routers must trigger REFINE when mask IoU < threshold."""
        for router in [self.det, self.laya, self.clef]:
            decision = router.route(
                detection_confidence=0.90,
                predicted_iou=0.75,
                iou_threshold=0.85,
            )
            self.assertEqual(
                decision.action,
                RouterAction.REFINE,
                f"Router {router.backend} failed to trigger refinement on IoU 0.75.",
            )

    def test_escalation_trigger_consensus(self):
        """All three routers must escalate to System 2 when species is ambiguous or confidence low."""
        for router in [self.det, self.laya, self.clef]:
            decision = router.route(
                detection_confidence=0.50,
                predicted_iou=0.90,
                min_confidence=0.70,
            )
            self.assertEqual(
                decision.action,
                RouterAction.ESCALATE_SYSTEM2,
                f"Router {router.backend} failed to escalate on confidence 0.50.",
            )

    def test_deterministic_router_latency_advantage(self):
        """Deterministic router must exhibit significantly lower latency than simulated network models."""
        det_dec = self.det.route(detection_confidence=0.90, predicted_iou=0.90)
        self.assertLess(det_dec.latency_ms, 0.5, "Deterministic reflex should be sub-millisecond.")


class TestWorkflowTopologyAndParity(unittest.TestCase):
    """Verifies VisionWorkflowRunner and create_langgraph_workflow parity, cyclic recursion, and System 2 integration."""

    def setUp(self):
        self.image = Image.new("RGB", (640, 480), color=(100, 150, 70))

    def test_workflow_runner_cyclic_refinement(self):
        """Verify VisionWorkflowRunner loops refinement up to max_refinements."""
        from src.workflow import VisionWorkflowRunner, create_initial_state

        runner = VisionWorkflowRunner(mock_mode=True, iou_threshold=0.85, max_refinements=2)
        runner.segmenter.default_mock_iou = 0.72  # Below 0.85 to force active refinement
        initial_state = create_initial_state(self.image)

        final_state = runner.run(initial_state)
        self.assertGreater(final_state["refinement_count"], 0)
        self.assertLessEqual(final_state["refinement_count"], 2)

    def test_workflow_runner_system2_escalation(self):
        """Verify VisionWorkflowRunner triage node escalates and invokes system2 when needed."""
        from src.workflow import VisionWorkflowRunner, create_initial_state

        mock_system2 = MagicMock()
        mock_system2.system2_node.return_value = {
            "prescription_report": {"status": "ok", "recommendation": "Selective herbicide"},
            "vlm_reasoning": "Escalated and resolved by System 2 reasoner.",
        }

        runner = VisionWorkflowRunner(mock_mode=True, system2=mock_system2)
        # Mock detector to emit low-confidence candidate
        runner.detector.detect_to_state_boxes = MagicMock(return_value=[
            {"x1": 20.0, "y1": 20.0, "x2": 60.0, "y2": 60.0, "label": "unknown_weed", "score": 0.45}
        ])

        initial_state = create_initial_state(self.image)
        final_state = runner.run(initial_state)
        self.assertTrue(final_state["system2_needed"])
        mock_system2.system2_node.assert_called_once()
        self.assertIsNotNone(final_state.get("prescription_report"))

    def test_langgraph_workflow_compilation_and_topology(self):
        """Verify create_langgraph_workflow builds the exact topological nodes and edges."""
        import sys
        from unittest.mock import MagicMock
        from src.workflow import create_langgraph_workflow, VisionWorkflowRunner

        mock_builder = MagicMock()
        mock_state_graph = MagicMock(return_value=mock_builder)
        mock_langgraph = MagicMock()
        mock_langgraph.StateGraph = mock_state_graph
        mock_langgraph.START = "START"
        mock_langgraph.END = "END"

        with patch.dict(sys.modules, {"langgraph": mock_langgraph, "langgraph.graph": mock_langgraph}):
            runner = VisionWorkflowRunner(mock_mode=True)
            create_langgraph_workflow(runner)

            # Assert all 6 nodes were registered
            node_names = [call.args[0] for call in mock_builder.add_node.call_args_list]
            self.assertIn("detect", node_names)
            self.assertIn("segment", node_names)
            self.assertIn("refine", node_names)
            self.assertIn("spray_map", node_names)
            self.assertIn("triage", node_names)
            self.assertIn("system2", node_names)

            # Assert conditional edges for cyclic refinement and triage
            conditional_edge_sources = [call.args[0] for call in mock_builder.add_conditional_edges.call_args_list]
            self.assertIn("segment", conditional_edge_sources)
            self.assertIn("refine", conditional_edge_sources)  # CYCLIC RECURSION
            self.assertIn("triage", conditional_edge_sources)

            # Verify edges connect spray_map -> triage and system2 -> END
            edge_calls = [call.args for call in mock_builder.add_edge.call_args_list]
            self.assertIn(("spray_map", "triage"), edge_calls)
            self.assertIn(("system2", "END"), edge_calls)

    def test_workflow_runner_defaults_to_deterministic_router(self):
        """Verify VisionWorkflowRunner defaults to DeterministicRouter."""
        from src.workflow import VisionWorkflowRunner
        runner = VisionWorkflowRunner(mock_mode=True)
        self.assertIsInstance(runner.laya_router, DeterministicRouter)
        self.assertEqual(runner.laya_router.backend, RouterBackend.DETERMINISTIC)

    def test_spray_map_strict_weed_isolation_and_fail_closed(self):
        """
        Verify that crop masks, unknown labels, and missing labels are never sprayed.
        Only explicitly recognized weed labels can enter the composite spray map.
        """
        from src.workflow import VisionWorkflowRunner

        runner = VisionWorkflowRunner(mock_mode=True)
        # Create test masks with crop, unknown, None, and weed labels
        h, w = 100, 100
        crop_mask = np.zeros((h, w), dtype=bool)
        crop_mask[10:30, 10:30] = True

        unknown_mask = np.zeros((h, w), dtype=bool)
        unknown_mask[40:60, 40:60] = True

        missing_label_mask = np.zeros((h, w), dtype=bool)
        missing_label_mask[70:80, 70:80] = True

        weed_mask = np.zeros((h, w), dtype=bool)
        weed_mask[50:70, 10:30] = True

        masks = [
            {"mask_array": crop_mask, "label": "cotton", "predicted_iou": 0.95},
            {"mask_array": crop_mask, "label": "sugarbeet", "predicted_iou": 0.95},
            {"mask_array": crop_mask, "label": "cash_crop", "predicted_iou": 0.95},
            {"mask_array": unknown_mask, "label": "unknown_foliage", "predicted_iou": 0.85},
            {"mask_array": missing_label_mask, "label": None, "predicted_iou": 0.80},
            {"mask_array": weed_mask, "label": "cotton weed", "predicted_iou": 0.92},
        ]

        test_state = {
            "image": Image.new("RGB", (w, h), color=(128, 128, 128)),
            "masks": masks,
            "artifacts": {},
        }

        output = runner.spray_map_node(test_state)
        spray_map = output["spray_map"]
        composite = output["artifacts"]["spray_map"].payload["composite_mask"]

        # Only the 1 weed mask should have contributed
        self.assertEqual(spray_map["weed_count"], 1)
        self.assertEqual(spray_map["total_masks_evaluated"], 6)

        # Pixels in crop, unknown, and missing masks must NOT be in composite_mask
        self.assertFalse(np.any(composite[10:30, 10:30]), "Crops must never be sprayed")
        self.assertFalse(np.any(composite[40:60, 40:60]), "Unknown labels must fail closed")
        self.assertFalse(np.any(composite[70:80, 70:80]), "Missing labels must fail closed")

        # Weed pixels must be present
        self.assertTrue(np.all(composite[50:70, 10:30]), "Weeds must be targeted in spray map")

    def test_spray_map_empty_mask_handling(self):
        """Empty mask list produces zero-infestation spray map safely."""
        from src.workflow import VisionWorkflowRunner

        runner = VisionWorkflowRunner(mock_mode=True)
        test_state = {
            "image": Image.new("RGB", (100, 100)),
            "masks": [],
            "artifacts": {},
        }
        output = runner.spray_map_node(test_state)
        self.assertEqual(output["spray_map"]["weed_count"], 0)
        self.assertEqual(output["spray_map"]["infestation_percentage"], 0.0)
        self.assertEqual(output["spray_map"]["chemical_savings_percentage"], 100.0)


if __name__ == "__main__":
    unittest.main()
