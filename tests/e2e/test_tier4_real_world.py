"""
tests/e2e/test_tier4_real_world.py
Tier 4: Realistic Field Workload Application Scenarios & Adversarial Verification.

Verifies end-to-end operational scenarios modeled on real-world agricultural conditions:
- Scenario 1: Early-season cotton field with sparse broadleaf weeds (targeted selective spraying with >85% chemical reduction).
- Scenario 2: Late-season sugar beet field with heavy grass weed infestation (dense spray zones, safe bounds clamping, and >85% saturation safety suppression).
- Scenario 3: Banned chemical interception scenario (attempted unapproved herbicide query intercepted by statutory safety filter).
- Scenario 4: Unknown / out-of-distribution invasive weed scenario (graceful no-knowledge-found fallback without hallucination).
- Scenario 5: Edge actuator network loss scenario (Clef Flash router simulated timeout falls back safely to local deterministic reflex).
"""

import io
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from src.agents.clef_flash_router import ClefFlashRouter
from src.agents.deterministic_router import DeterministicRouter
from src.agents.laya_router import LayaTriageRouter
from src.agents.router_contract import RouterAction, RouterBackend, RouterDecision
from src.agronomy.knowledge_store import InMemoryKnowledgeStore as StoreWithCanonicals
from src.agronomy.prescription import (
    BANNED_HERBICIDES,
    DISCLAIMER,
    check_banned_chemicals,
    create_chemical_prescription,
    get_herbicide_prescription,
)
from src.agronomy.prescription_schema import ChemicalPrescription
from src.evaluation.iou_dice import compute_herbicide_savings, compute_iou
from src.state import Artifact, ArtifactType, Box, GraphState, Mask
from src.vision.grounding_dino import GroundingDINOEngine
from src.vision.sam2_wrapper import SAM2Segmenter
from src.workflow import VisionWorkflowRunner, create_initial_state
from tests.e2e.fixtures import (
    InMemoryKnowledgeStore,
    create_synthetic_box,
    create_synthetic_mask,
    create_test_field_image,
    get_sample_image_path,
)


class TestTier4RealWorld(unittest.TestCase):
    """Tier 4 Realistic Field Workload & Adversarial Safety Test Suite."""

    def setUp(self):
        self.canonical_store = StoreWithCanonicals()
        self.canonical_store.ingest()
        self.mock_store = InMemoryKnowledgeStore()

    # =========================================================================
    # Scenario 1: Early-Season Cotton Field with Sparse Broadleaf Weeds
    # =========================================================================
    def test_scenario1_early_season_cotton_sparse_weeds_high_savings(self):
        """
        Scenario 1: Early-season cotton field with sparse broadleaf weeds.
        Verifies targeted selective spraying achieves >85% chemical reduction.
        """
        # Load sample cotton fixture or synthesize realistic early-season field
        sample_path = get_sample_image_path("cotton_20190613_6062W_CM_11.jpg")
        cotton_image = Image.open(sample_path).convert("RGB")
        img_w, img_h = cotton_image.size

        runner = VisionWorkflowRunner(
            mock_mode=True,
            iou_threshold=0.85,
            buffer_pixels=5,
        )

        initial_state = create_initial_state(
            image=cotton_image,
            text_prompt="cotton weed . broadleaf weed .",
            image_path=str(sample_path),
        )
        initial_state["field_metadata"] = {
            "crop": "cotton",
            "growth_stage": "early_vegetative",
            "field_id": "PLOT-COTTON-NORTH-04",
        }

        final_state = runner.run(initial_state)

        # 1. Detection and Segmentation verification
        boxes = final_state.get("boxes", [])
        masks = final_state.get("masks", [])
        self.assertGreater(len(boxes), 0, "Sparse weeds must be detected")
        self.assertEqual(len(boxes), len(masks))

        # 2. Spray map selective spraying performance
        spray_map = final_state.get("spray_map")
        self.assertIsNotNone(spray_map)

        infestation_pct = spray_map["infestation_percentage"]
        savings_pct = spray_map["chemical_savings_percentage"]
        weed_count = spray_map["weed_count"]

        # In early-season sparse cotton, infestation must be low (<15%)
        self.assertLess(infestation_pct, 15.0, "Early-season weed infestation should be sparse")

        # Selective spraying must achieve >85% chemical reduction as specified
        self.assertGreater(
            savings_pct,
            85.0,
            f"Selective spraying must achieve >85% chemical reduction, got {savings_pct:.2f}%",
        )

        # 3. Artifact validity
        spray_artifact = final_state["artifacts"]["spray_map"]
        self.assertEqual(spray_artifact.type, ArtifactType.SPRAY_MAP)
        comp_mask = spray_artifact.payload["composite_mask"]
        self.assertEqual(comp_mask.shape, (img_h, img_w))
        self.assertEqual(comp_mask.dtype, bool)

        # 4. Conservation of area invariant: savings <= 1.0 - (weed_area / total_area)
        total_pixels = img_h * img_w
        weed_pixels = int(comp_mask.sum())
        raw_savings_upper_bound = (1.0 - (weed_pixels / total_pixels)) * 100.0
        self.assertLessEqual(savings_pct, round(raw_savings_upper_bound + 0.01, 2))

    # =========================================================================
    # Scenario 2: Late-Season Sugar Beet Field with Heavy Grass Weed Infestation
    # =========================================================================
    def test_scenario2_late_season_sugarbeet_dense_infestation_and_safety_suppression(self):
        """
        Scenario 2: Late-season sugar beet field with heavy grass weed infestation.
        Verifies dense spray zone aggregation, bounds clamping, and >85% saturation suppression.
        """
        # Load real sugar beet fixture
        sample_path = get_sample_image_path("beet_X-10-0.png")
        beet_image = Image.open(sample_path).convert("RGB")
        w, h = beet_image.size

        # Subtest 2A: Dense Infestation (multi-target clustering and union property)
        with self.subTest(facet="dense_multi_target_clustering"):
            # Create a dense set of weed boxes representing heavy infestation
            dense_boxes = [
                create_synthetic_box(20.0, 30.0, 180.0, 190.0, label="sugarbeet_weed", score=0.92),
                create_synthetic_box(150.0, 100.0, 320.0, 280.0, label="sugarbeet_weed", score=0.88),
                create_synthetic_box(280.0, 220.0, 460.0, 420.0, label="sugarbeet_weed", score=0.85),
                create_synthetic_box(80.0, 300.0, 240.0, 480.0, label="sugarbeet_weed", score=0.90),
            ]
            dense_masks = [
                create_synthetic_mask(h, w, box=b, predicted_iou=0.88, label="sugarbeet_weed")
                for b in dense_boxes
            ]

            runner = VisionWorkflowRunner(mock_mode=True, buffer_pixels=10)
            initial_state = create_initial_state(beet_image, text_prompt="sugarbeet weed . grass .")
            initial_state["boxes"] = dense_boxes
            initial_state["masks"] = dense_masks

            spray_out = runner.spray_map_node(initial_state)
            sm = spray_out["spray_map"]

            # Mathematical bounds clamping: strictly in [0.0, 100.0]
            self.assertGreaterEqual(sm["infestation_percentage"], 0.0)
            self.assertLessEqual(sm["infestation_percentage"], 100.0)
            self.assertGreaterEqual(sm["chemical_savings_percentage"], 0.0)
            self.assertLessEqual(sm["chemical_savings_percentage"], 100.0)

            # Area union property: composite dilated area <= sum of individually dilated areas
            composite_mask = spray_out["artifacts"]["spray_map"].payload["composite_mask"]
            comp_savings = compute_herbicide_savings(composite_mask, (h, w), buffer_pixels=10)

            # Sum of individual mask areas
            sum_indiv_areas = sum(m["mask_array"].sum() for m in dense_masks)
            union_area = composite_mask.sum()
            self.assertLessEqual(union_area, sum_indiv_areas, "Union of overlapping masks must be <= sum of areas")

        # Subtest 2B: Saturation Threshold (>85% Infestation triggers SUPPRESS_SPRAY)
        with self.subTest(facet="saturation_safety_suppression"):
            # Saturated field where weeds cover 90% of canopy
            saturated_infestation_pct = 90.0

            # 1. Test deterministic reflex router guardrail
            det_router = DeterministicRouter()
            det_decision = det_router.route(
                detection_confidence=0.95,
                predicted_iou=0.90,
                infestation_pct=saturated_infestation_pct,
                max_allowed_infestation=85.0,
            )
            self.assertEqual(
                det_decision.action,
                RouterAction.SUPPRESS_SPRAY,
                "Infestation >85% must trigger SUPPRESS_SPRAY guardrail",
            )
            self.assertIn("exceeds statutory safety ceiling (85.0%)", det_decision.reason)

            # 2. Test Laya router safety method
            laya_router = LayaTriageRouter()
            is_safe = laya_router.verify_spray_safety(
                infestation_pct=saturated_infestation_pct,
                max_allowed_infestation=85.0,
            )
            self.assertFalse(is_safe, "verify_spray_safety must return False when infestation > 85%")

            # 3. Test Clef Flash router safety suppression
            cf_router = ClefFlashRouter(mock_mode=True)
            cf_decision = cf_router.route(
                detection_confidence=0.95,
                predicted_iou=0.90,
                infestation_pct=saturated_infestation_pct,
                max_allowed_infestation=85.0,
            )
            self.assertEqual(
                cf_decision.action,
                RouterAction.SUPPRESS_SPRAY,
                "Clef Flash must also respect the statutory 85% spray suppression ceiling",
            )

    # =========================================================================
    # Scenario 3: Banned Chemical Interception Scenario
    # =========================================================================
    def test_scenario3_banned_chemical_interception_scenario(self):
        """
        Scenario 3: Banned chemical interception scenario.
        Verifies statutory filter intercepts unapproved herbicide requests,
        clears active ingredients and dosages, and generates strict warnings.
        """
        banned_queries = [
            ("Attempted spray of Nitrofen 25% EC", "nitrofen"),
            ("Apply Paraquat dimethyl sulphate as defoliant", "paraquat dimethyl sulphate"),
            ("Use Metoxuron for grass weed suppression", "metoxuron"),
            ("Spray Dalapon for reed grass control", "dalapon"),
            ("Pre-emergence treatment with Simazine 50% WP", "simazine"),
            ("Selective broadleaf treatment with 2,4,5-T ester", "2,4,5-t"),
        ]

        for query, chem_token in banned_queries:
            with self.subTest(query=query, banned_chemical=chem_token):
                # Execute prescription generation through statutory filter
                presc: ChemicalPrescription = create_chemical_prescription(
                    weed_name=query,
                    crop_stage="vegetative",
                    crop="cotton",
                    store=self.canonical_store,
                )

                # 1. Critical safety status check
                self.assertEqual(
                    presc.status,
                    "unapproved_chemical_flagged",
                    f"Banned herbicide {chem_token} must be flagged as unapproved",
                )

                # 2. Chemical fields must be strictly nullified
                self.assertIsNone(presc.active_ingredient, "Active ingredient must be nullified")
                self.assertIsNone(presc.dosage_ai_g_per_ha, "Dosage must be nullified")
                self.assertIsNone(presc.water_volume_l_per_ha, "Water volume must be nullified")
                self.assertIsNone(presc.formulation, "Formulation must be nullified")

                # 3. Safety warning must identify chemical and statutory authority
                self.assertIsNotNone(presc.safety_warning)
                self.assertIn("BANNED HERBICIDE", presc.safety_warning)
                self.assertIn(chem_token, presc.safety_warning.lower())
                self.assertIn("Insecticides Act 1968", presc.safety_warning)

                # 4. Mandatory statutory disclaimer must be preserved
                self.assertEqual(presc.disclaimer, DISCLAIMER)

    # =========================================================================
    # Scenario 4: Unknown / Out-of-Distribution Invasive Weed Scenario
    # =========================================================================
    def test_scenario4_unknown_ood_invasive_weed_scenario(self):
        """
        Scenario 4: Unknown / out-of-distribution invasive weed scenario.
        Verifies distance-gated retrieval cleanly triggers safe no_knowledge_found
        without hallucinating chemicals or fabricated dosages.
        """
        ood_weed_names = [
            "AlienInvasiveSuperWeed_2026_X",
            "NonExistentExtraterrestrialWeed_XYZ",
            "UnknownAsteraceae_OOD_Mutant",
            "CrypticUncataloguedGrass_Z99",
        ]

        for ood_weed in ood_weed_names:
            with self.subTest(target_weed=ood_weed):
                # Query with distance-gated retrieval
                presc: ChemicalPrescription = create_chemical_prescription(
                    weed_name=ood_weed,
                    crop_stage="vegetative",
                    crop="cotton",
                    store=self.canonical_store,
                    distance_threshold=0.25,
                )

                # 1. Status must indicate safe no-knowledge fallback
                self.assertEqual(
                    presc.status,
                    "no_knowledge_found",
                    f"Out-of-distribution weed '{ood_weed}' must return no_knowledge_found",
                )

                # 2. Strict anti-hallucination verification
                self.assertEqual(
                    len(presc.citations),
                    0,
                    "Citations must be empty on safe no-knowledge response",
                )
                self.assertIsNone(presc.active_ingredient, "Must NOT hallucinate active ingredient")
                self.assertIsNone(presc.formulation, "Must NOT hallucinate formulation")
                self.assertIsNone(presc.dosage_ai_g_per_ha, "Must NOT fabricate chemical dosage")
                self.assertIsNone(presc.water_volume_l_per_ha, "Must NOT fabricate water volume")
                self.assertIsNone(presc.pre_harvest_interval_days, "Must NOT fabricate PHI")

                # 3. Disclaimer must be present
                self.assertEqual(presc.disclaimer, DISCLAIMER)

    # =========================================================================
    # Scenario 5: Edge Actuator Network Loss Scenario
    # =========================================================================
    def test_scenario5_edge_actuator_network_loss_scenario(self):
        """
        Scenario 5: Edge actuator network loss scenario.
        Verifies that when cloud VLM / Clef Flash experiences network dropouts,
        simulated timeouts, or connection errors, the router automatically activates
        the local deterministic reflex fallback in sub-millisecond to low ms time.
        """
        crop_image = Image.new("RGB", (100, 100), color=(80, 140, 50))
        crop_np = np.array(crop_image)

        # Instantiate live-configured router with credentials
        router = ClefFlashRouter(
            api_token="cloudflare_edge_token_12345",
            account_id="cf_agri_account_67890",
            model_name="@cf/meta/clef-flash",
            timeout_seconds=0.05,
            fallback_router=DeterministicRouter(),
            mock_mode=False,
        )

        simulated_exceptions = [
            TimeoutError("Cloudflare Workers AI gateway request timed out after 50ms"),
            ConnectionResetError("Remote socket connection abruptly reset by edge peer"),
            RuntimeError("DNS resolution failed for cloudflare-ai-endpoint.internal"),
        ]

        for exc in simulated_exceptions:
            with self.subTest(exception_type=type(exc).__name__):
                with patch.object(router, "_execute_cloud_inference", side_effect=exc):
                    # Edge reflex triage call
                    decision: RouterDecision = router.route(
                        detection_confidence=0.89,
                        predicted_iou=0.92,
                        area_pixels=1500,
                        species_ambiguity=False,
                        image_crop=crop_np,
                        label="cotton_weed",
                    )

                    # 1. Decision produced safely without throwing unhandled exception
                    self.assertIsInstance(decision, RouterDecision)
                    self.assertEqual(decision.backend, RouterBackend.CLEF_FLASH)

                    # 2. Reflex decision accurately made by local fallback
                    self.assertEqual(decision.action, RouterAction.ACCEPT)
                    self.assertIn("Clef Flash Fallback", decision.reason)
                    self.assertIn(str(exc), decision.reason)

                    # 3. Decision completed with low latency
                    self.assertLess(
                        decision.latency_ms,
                        50.0,
                        f"Reflex fallback decision must complete in <50ms, took {decision.latency_ms:.2f}ms",
                    )


if __name__ == "__main__":
    unittest.main()
