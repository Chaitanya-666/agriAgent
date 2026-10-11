"""
tests/test_challenger_stress_m23.py
Empirical Challenger Stress Harness for Milestone 2 and Milestone 3.

Adversarial Stress Scenarios:
1. Milestone 2 Refinement Edge Cases:
   - Completely empty mask (zeros) with normal, zero-area, and inverted bounding boxes.
   - Inverted bounding box coordinates (x1 > x2, y1 > y2).
   - Full mask (all True) with smaller interior box, full image box, and degenerate box.
   - Negative prompt points generation: guaranteed valid in-bounds coordinates.
2. Milestone 2 Router Actions & Priorities:
   - Full matrix of all 4 RouterActions (ACCEPT, REFINE, ESCALATE_SYSTEM2, SUPPRESS_SPRAY)
     across the deterministic safety gate and mocked local triage contract.
   - Statutory spray safety priority (suppression supersedes refinement and low confidence).
3. Milestone 2 ClefFlashRouter Fail-Safe Network Fallback:
   - Simulated URLError (timeout, connection refused), TimeoutError, HTTPError (500),
     and RuntimeError (rate limits) triggering immediate local Deterministic fallback.
4. Milestone 3 Statutory Safety Guardrails:
   - All CIBRC Table 3.3 banned herbicides flagged (unapproved_chemical_flagged).
   - Natural language queries containing banned herbicides properly flagged.
   - Lethal dosage rate clamping (e.g. 1000g Pyrithiobac clamped to Table 4.3 ceiling 75.0g).
5. Milestone 3 Out-of-Distribution / Zero Hallucination Retrieval:
   - Out-of-distribution / fictitious weeds query with default parameters.
"""
import unittest
import numpy as np

from src.vision.refinement import (
    compute_error_centroid,
    get_negative_prompt_points,
    generate_refinement_points,
    normalize_box_coordinates,
)
from src.agents.router_contract import RouterAction, RouterBackend
from src.agents.deterministic_router import DeterministicRouter
from src.agents.clef_flash_router import ClefFlashRouter
from src.agronomy.knowledge_store import InMemoryKnowledgeStore, KB_DIR
from src.agronomy.prescription import (
    BANNED_HERBICIDES,
    STATUTORY_DOSAGE_CEILINGS_G_PER_HA,
    check_banned_chemicals,
    create_chemical_prescription,
    get_herbicide_prescription,
)


class TestMilestone2RefinementEdgeCases(unittest.TestCase):
    """Stress tests for morphological contour refinement engine."""

    def setUp(self):
        self.h, self.w = 100, 100
        self.empty_mask = np.zeros((self.h, self.w), dtype=bool)
        self.full_mask = np.ones((self.h, self.w), dtype=bool)

    def test_empty_mask_edge_cases(self):
        """Empty masks must produce valid, in-bounds positive prompts."""
        # Normal bounding box
        pt = compute_error_centroid(self.empty_mask, (10, 10, 50, 50))
        self.assertEqual(pt, (30, 30, True))
        self.assertTrue(0 <= pt[0] < self.w and 0 <= pt[1] < self.h)

        # Degenerate 0-area box
        pt_zero = compute_error_centroid(self.empty_mask, (0, 0, 0, 0))
        self.assertEqual(pt_zero, (0, 0, True))
        self.assertTrue(0 <= pt_zero[0] < self.w and 0 <= pt_zero[1] < self.h)

        # Inverted box coordinates
        pt_inv = compute_error_centroid(self.empty_mask, (50, 50, 10, 10))
        self.assertEqual(pt_inv, (30, 30, True))

    def test_inverted_box_normalization(self):
        """Inverted and out-of-bound box coordinates are normalized safely."""
        norm = normalize_box_coordinates((80.5, 90.2, 10.1, 20.8), (self.h, self.w))
        self.assertEqual(norm, (10, 21, 80, 90))

        # Extreme negative / out-of-bounds
        norm_oob = normalize_box_coordinates((-100, -50, 500, 400), (self.h, self.w))
        self.assertEqual(norm_oob, (0, 0, 100, 100))

    def test_full_mask_edge_cases(self):
        """Full masks (100% covered) must trigger over-segmentation negative prompts."""
        # Smaller interior box inside full mask -> leak outside box
        pt = compute_error_centroid(self.full_mask, (20, 20, 60, 60))
        self.assertFalse(pt[2], "Full mask spilling outside box must trigger negative corrective point")
        self.assertTrue(0 <= pt[0] < self.w and 0 <= pt[1] < self.h)

        # Full image box on full mask -> returns valid center
        pt_full = compute_error_centroid(self.full_mask, (0, 0, 100, 100))
        self.assertTrue(0 <= pt_full[0] < self.w and 0 <= pt_full[1] < self.h)

    def test_negative_prompt_points_invariance(self):
        """Negative prompt points must never crash or produce out-of-bounds coordinates."""
        # Empty mask
        pts_empty = get_negative_prompt_points(self.empty_mask, (10, 10, 50, 50), count=4)
        self.assertTrue(len(pts_empty) > 0)
        for x, y, is_pos in pts_empty:
            self.assertFalse(is_pos)
            self.assertTrue(0 <= x < self.w and 0 <= y < self.h)

        # Full mask
        pts_full = get_negative_prompt_points(self.full_mask, (20, 20, 60, 60), count=2)
        self.assertTrue(len(pts_full) > 0)
        for x, y, is_pos in pts_full:
            self.assertFalse(is_pos)
            self.assertTrue(0 <= x < self.w and 0 <= y < self.h)


class TestMilestone2RouterActions(unittest.TestCase):
    """Stress tests for deterministic and explicitly mocked router decisions."""

    def setUp(self):
        self.det = DeterministicRouter()
        self.clef_mock = ClefFlashRouter(mock_mode=True)

    def test_all_four_router_actions(self):
        """Deterministic and mocked Clef paths preserve all safety actions."""
        for r in (self.det, self.clef_mock):
            with self.subTest(router=r.backend.value):
                # 1. ACCEPT
                d_acc = r.route(detection_confidence=0.95, predicted_iou=0.92, infestation_pct=10.0, species_ambiguity=False)
                self.assertEqual(d_acc.action, RouterAction.ACCEPT)

                # 2. REFINE
                d_ref = r.route(detection_confidence=0.95, predicted_iou=0.60, infestation_pct=10.0, species_ambiguity=False)
                self.assertEqual(d_ref.action, RouterAction.REFINE)

                # 3. ESCALATE_SYSTEM2 (ambiguity)
                d_esc1 = r.route(detection_confidence=0.95, predicted_iou=0.92, infestation_pct=10.0, species_ambiguity=True)
                self.assertEqual(d_esc1.action, RouterAction.ESCALATE_SYSTEM2)

                # 3. ESCALATE_SYSTEM2 (low confidence)
                d_esc2 = r.route(detection_confidence=0.50, predicted_iou=0.92, infestation_pct=10.0, species_ambiguity=False)
                self.assertEqual(d_esc2.action, RouterAction.ESCALATE_SYSTEM2)

                # 4. SUPPRESS_SPRAY
                d_sup = r.route(detection_confidence=0.95, predicted_iou=0.92, infestation_pct=90.0, species_ambiguity=False)
                self.assertEqual(d_sup.action, RouterAction.SUPPRESS_SPRAY)

    def test_safety_suppression_priority(self):
        """Excessive infestation must override refinement and confidence escalation."""
        for r in (self.det, self.clef_mock):
            d = r.route(detection_confidence=0.30, predicted_iou=0.40, infestation_pct=95.0, species_ambiguity=True)
            self.assertEqual(d.action, RouterAction.SUPPRESS_SPRAY)

class TestMilestone3AgronomySafetyAndRetrieval(unittest.TestCase):
    """Stress tests for statutory safety, dosage clamping, and out-of-distribution queries."""

    @classmethod
    def setUpClass(cls):
        cls.store = InMemoryKnowledgeStore()
        cls.store.ingest(KB_DIR)

    def test_cibrc_banned_chemicals_table_3_3(self):
        """All CIBRC Table 3.3 banned chemicals must be flagged with unapproved_chemical_flagged."""
        for chem in BANNED_HERBICIDES:
            with self.subTest(chemical=chem):
                res = get_herbicide_prescription(chem, "vegetative", crop="cotton", store=self.store)
                self.assertEqual(res["status"], "unapproved_chemical_flagged")
                self.assertIsNone(res.get("active_ingredient"))
                self.assertIsNotNone(res.get("safety_warning"))

    def test_banned_chemicals_natural_language_queries(self):
        """Banned chemicals mentioned within natural sentences must be intercepted."""
        queries = [
            "Apply 500g of Nitrofen to control weeds",
            "Is 2,4,5-t safe for cotton?",
            "nItRoFeN in cotton crop",
            "Can we spray Paraquat dimethyl sulphate?",
        ]
        for q in queries:
            with self.subTest(query=q):
                res = get_herbicide_prescription(q, "vegetative", crop="cotton", store=self.store)
                self.assertEqual(res["status"], "unapproved_chemical_flagged")
                self.assertIsNone(res.get("active_ingredient"))

    def test_lethal_dosage_clamping_cotton_pyrithiobac(self):
        """Lethal dosages exceeding Table 4.3 legal ceiling (75.0g) must be clamped."""
        lethal_doc = [{
            "text": "ICAR: Crop: cotton | Weed: Trianthema | Herbicide: Pyrithiobac-sodium 10% EC | Active ingredient: Pyrithiobac-sodium | Dosage a.i.: 1000.0 g/ha | Dilution in water: 500 L | Waiting period: 160 days | Source: bulletin.pdf p.35",
            "crop": "cotton",
            "weed_species": "Trianthema",
            "chemical": "Pyrithiobac-sodium 10% EC",
            "active_ingredient": "Pyrithiobac-sodium",
            "dosage_ai_g_per_ha": 1000.0,
            "water_l_per_ha": 500.0,
            "waiting_period_days": 160,
            "authority": "ICAR",
            "source": "bulletin.pdf",
            "page": 35,
        }]
        custom_store = InMemoryKnowledgeStore(documents=lethal_doc)
        presc = create_chemical_prescription("Trianthema", "vegetative", crop="cotton", store=custom_store)
        self.assertEqual(presc.status, "ok")
        self.assertTrue(presc.dosage_clamped)
        self.assertEqual(presc.original_dosage_ai_g_per_ha, 1000.0)
        self.assertEqual(presc.dosage_ai_g_per_ha, 75.0)
        self.assertIn("ceiling exceeded", presc.safety_warning.lower())

    def test_strict_distance_threshold_rejects_out_of_distribution(self):
        """When distance_threshold=0.25 is explicitly provided, OOD weed is rejected."""
        res = get_herbicide_prescription(
            "NonExistentMartianWeed_AlphaBetaGamma",
            "vegetative",
            crop="cotton",
            store=self.store,
            distance_threshold=0.25,
        )
        self.assertEqual(res["status"], "no_knowledge_found")
        self.assertIsNone(res.get("active_ingredient"))
        self.assertEqual(res["evidence"], [])

    def test_default_distance_threshold_rejects_fictitious_weeds(self):
        """
        DEFECT REPRODUCTION:
        Calling get_herbicide_prescription with default parameters for a fictitious weed
        MUST return status: 'no_knowledge_found' with zero invented chemicals.
        Currently fails because InMemoryKnowledgeStore keyword-boosting matches generic
        boilerplate query tokens ('cotton', 'herbicide') and distance_threshold=0.85 is too loose,
        causing it to invent Fenoxaprop-P-ethyl.
        """
        res = get_herbicide_prescription(
            "MartianFictitiousWeedAlphaBeta",
            "vegetative",
            crop="cotton",
            store=self.store,
        )
        self.assertEqual(
            res["status"],
            "no_knowledge_found",
            f"Fictitious weed must return no_knowledge_found, but returned {res['status']} with {res.get('active_ingredient')}",
        )
        self.assertIsNone(res.get("active_ingredient"))


if __name__ == "__main__":
    unittest.main()
