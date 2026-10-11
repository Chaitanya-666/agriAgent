"""Contracts for deterministic safety and local Clef triage."""

import unittest

from src.agents.clef_flash_router import ClefFlashRouter
from src.agents.deterministic_router import DeterministicRouter
from src.agents.router_contract import RouterAction, RouterBackend
from src.workflow import VisionWorkflowRunner


class DeterministicRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = DeterministicRouter()

    def test_clean_detection_is_accepted(self):
        decision = self.router.route(detection_confidence=0.95, predicted_iou=0.92)
        self.assertEqual(decision.action, RouterAction.ACCEPT)
        self.assertEqual(decision.backend, RouterBackend.DETERMINISTIC)

    def test_poor_mask_requests_refinement(self):
        decision = self.router.route(detection_confidence=0.95, predicted_iou=0.70)
        self.assertEqual(decision.action, RouterAction.REFINE)

    def test_low_confidence_escalates(self):
        decision = self.router.route(detection_confidence=0.4, predicted_iou=0.95)
        self.assertEqual(decision.action, RouterAction.ESCALATE_SYSTEM2)

    def test_high_infestation_suppresses_spray(self):
        decision = self.router.route(
            detection_confidence=0.95, predicted_iou=0.95, infestation_pct=86.0
        )
        self.assertEqual(decision.action, RouterAction.SUPPRESS_SPRAY)
        self.assertFalse(self.router.verify_spray_safety(86.0))


class ClefFlashRouterTests(unittest.TestCase):
    def test_explicit_mock_mode_reports_mock_and_cannot_override_safety(self):
        router = ClefFlashRouter(mock_mode=True)
        safe = router.route(detection_confidence=0.95, predicted_iou=0.95)
        unsafe = router.route(
            detection_confidence=0.95, predicted_iou=0.95, infestation_pct=90.0
        )
        self.assertEqual(safe.action, RouterAction.ACCEPT)
        self.assertTrue(safe.metadata["mock_mode"])
        self.assertEqual(unsafe.action, RouterAction.SUPPRESS_SPRAY)

    def test_known_ambiguity_escalates(self):
        decision = ClefFlashRouter(mock_mode=True).route(
            detection_confidence=0.95,
            predicted_iou=0.95,
            species_ambiguity=True,
            label="unidentified",
        )
        self.assertEqual(decision.action, RouterAction.ESCALATE_SYSTEM2)

    def test_missing_local_runtime_does_not_become_mock_acceptance(self):
        router = ClefFlashRouter(mock_mode=False)
        router._load_model = lambda: (_ for _ in ()).throw(RuntimeError("weights unavailable"))
        decision = router.route(detection_confidence=0.95, predicted_iou=0.95)
        self.assertEqual(decision.action, RouterAction.ESCALATE_SYSTEM2)
        self.assertIn("unavailable", decision.reason)
        self.assertFalse(decision.metadata["mock_mode"])

    def test_workflow_defaults_to_clef_triage_and_deterministic_safety(self):
        runner = VisionWorkflowRunner(mock_mode=True)
        self.assertIsInstance(runner.router, ClefFlashRouter)
        self.assertIsInstance(runner.safety_router, DeterministicRouter)
        self.assertTrue(runner.router.mock_mode)


if __name__ == "__main__":
    unittest.main()
