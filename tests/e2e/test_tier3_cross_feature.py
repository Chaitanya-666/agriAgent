"""
tests/e2e/test_tier3_cross_feature.py
Tier 3: Pairwise Integration & Cross-Feature Interaction Test Suite.

Verifies major cross-feature interactions across AgriAgent subsystems:
1. Vision Perception + Morphological Refinement + Spray Map Generation:
   - Zero-shot detection -> SAM 2 initial instance segmentation -> closed-loop active refinement
     via morphological contour / error centroid heuristic -> composite spray map generation with
     physical buffer dilation and chemical savings.
2. Perception + Triage Routing + System 2 Statutory RAG:
   - Ambiguous or sub-confidence detections trigger triage escalation (ESCALATE_SYSTEM2), which
     activates the deliberative System-2 node, querying the ICAR/CIBRC statutory corpus and returning
     an evidence-grounded prescription report with citations.
3. Ambiguous Weed Detection + Clef Flash Multimodal Router + Fail-Safe Local Fallback:
   - Multimodal telemetry and image crop evaluation using Clef Flash router.
   - Simulated cloud network timeout / connectivity loss triggers transparent, fail-safe fallback
     to local DeterministicRouter without crashing the actuator pipeline.
4. Ground-Truth Evaluation Harness + Benchmark Runner + JSON Metrics Serialization:
   - End-to-end benchmark evaluation over manifest items, computing precision, recall, F1, mean box IoU,
     weed mask IoU/Dice, and chemical savings, followed by lossless JSON serialization and Markdown reporting.
5. Streamlit App Image Decoding + Workflow Execution + Dynamic KPI Extraction + GeoJSON Export:
   - Uploaded image decoding -> full workflow execution -> dynamic KPI extraction -> valid GeoJSON
     FeatureCollection export with polygon geometries and prescription properties.
6. CIBRC Banned Chemical Detection + Statutory Dosage Ceiling Clamping + Disclaimer Generation:
   - Statutory safety filter intercepts unapproved herbicides (Table 3.3) with unapproved_chemical_flagged status.
   - Statutory dosage ceiling checks clamp excessive chemical dosages to Table 4.3 upper bounds.
   - Mandatory advisory disclaimer is unconditionally preserved.
"""

import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from app.components.pipeline import (
    ImageDecodeError,
    build_spray_geojson,
    decode_uploaded_image,
    execute_agriagent_workflow,
    extract_kpis,
    format_prescription_report,
)
from src.agents.clef_flash_router import ClefFlashRouter
from src.agents.deterministic_router import DeterministicRouter
from src.agents.router_contract import RouterAction, RouterBackend, RouterDecision
from src.agronomy.knowledge_store import InMemoryKnowledgeStore as StoreWithCanonicals
from src.agronomy.prescription import (
    BANNED_HERBICIDES,
    DISCLAIMER,
    check_banned_chemicals,
    create_chemical_prescription,
    get_dosage_ceiling,
    get_herbicide_prescription,
)
from src.agronomy.prescription_schema import ChemicalPrescription
from src.agronomy.system2_node import System2Reasoner
from src.evaluation.benchmark_runner import BenchmarkRunner, ImageBenchmarkResult
from src.evaluation.iou_dice import compute_dice, compute_herbicide_savings, compute_iou
from src.state import Artifact, ArtifactType, Box, GraphState, Mask
from src.vision.grounding_dino import GroundingDINOEngine
from src.vision.refinement import (
    compute_error_centroid,
    get_negative_prompt_points,
    get_refinement_point,
    should_refine,
)
from src.vision.sam2_wrapper import SAM2Segmenter
from src.workflow import VisionWorkflowRunner, create_initial_state
from tests.e2e.fixtures import (
    InMemoryKnowledgeStore,
    create_synthetic_box,
    create_synthetic_mask,
    create_test_field_image,
    get_sample_image_path,
)


class TestTier3CrossFeature(unittest.TestCase):
    """Tier 3: Pairwise Integration & Cross-Feature Test Suite."""

    def setUp(self):
        self.test_image = create_test_field_image(width=640, height=480)
        self.mock_store = InMemoryKnowledgeStore()
        self.canonical_store = StoreWithCanonicals()
        self.canonical_store.ingest()

    # =========================================================================
    # 1. Vision Perception + Morphological Refinement + Spray Map Generation
    # =========================================================================
    def test_cross_feature_perception_refinement_spraymap(self):
        """
        Verify interaction across detection, active morphological refinement,
        and spray map generation.
        """
        # Configure runner with low initial IoU to guarantee refinement trigger
        runner = VisionWorkflowRunner(
            mock_mode=True,
            iou_threshold=0.85,
            max_refinements=2,
            buffer_pixels=10,
        )
        runner.segmenter.default_mock_iou = 0.70  # Sub-threshold to trigger active refinement

        initial_state = create_initial_state(
            image=self.test_image,
            text_prompt="cotton weed . broadleaf plant .",
        )

        final_state = runner.run(initial_state)

        # 1. Detection produced candidate boxes
        self.assertGreater(len(final_state["boxes"]), 0)
        for b in final_state["boxes"]:
            self.assertGreaterEqual(b["score"], 0.0)
            self.assertLessEqual(b["score"], 1.0)

        # 2. Refinement loop was actively triggered and improved mask IoUs
        self.assertGreater(final_state["refinement_count"], 0)
        self.assertLessEqual(final_state["refinement_count"], 2)
        for m in final_state["masks"]:
            self.assertGreater(
                m["predicted_iou"],
                0.70,
                "Refinement must improve mask predicted IoU above initial sub-threshold value",
            )

        # 3. Spray map correctly synthesizes refined masks with buffer
        self.assertIn("spray_map", final_state)
        sm = final_state["spray_map"]
        self.assertEqual(sm["weed_count"], len(final_state["masks"]))
        self.assertEqual(sm["buffer_pixels"], 10)
        self.assertGreater(sm["infestation_percentage"], 0.0)
        self.assertLessEqual(sm["infestation_percentage"], 100.0)
        self.assertGreater(sm["chemical_savings_percentage"], 0.0)
        self.assertLessEqual(sm["chemical_savings_percentage"], 100.0)

        # 4. Artifact payload contains valid 2D composite mask
        spray_artifact = final_state["artifacts"]["spray_map"]
        self.assertEqual(spray_artifact.type, ArtifactType.SPRAY_MAP)
        comp_mask = spray_artifact.payload["composite_mask"]
        self.assertEqual(comp_mask.shape, (480, 640))
        self.assertEqual(comp_mask.dtype, bool)
        self.assertEqual(int(comp_mask.sum()), int(np.sum([m["mask_array"] for m in final_state["masks"]], axis=0).astype(bool).sum()))

    def test_direct_morphological_refinement_to_spraymap_invariants(self):
        """
        Verify that refining an under-segmented mask expands the mask towards the foliage
        boundary and preserves physical spray savings invariants.
        """
        h, w = 300, 400
        box_coords = (50.0, 50.0, 150.0, 150.0)
        box = create_synthetic_box(50.0, 50.0, 150.0, 150.0, label="cotton_weed")

        # Initial under-segmented mask: small 20x20 core inside 100x100 box
        initial_mask = np.zeros((h, w), dtype=bool)
        initial_mask[80:100, 80:100] = True

        # Calculate error centroid via morphological heuristic
        pt = get_refinement_point(initial_mask, box_coords, predicted_iou=0.65, threshold=0.85)
        self.assertIsNotNone(pt)
        px, py, is_pos = pt
        self.assertTrue(0 <= px < w)
        self.assertTrue(0 <= py < h)
        self.assertTrue(is_pos, "Under-segmented mask must generate a positive corrective point")

        # Generate background soil negative prompt points
        neg_pts = get_negative_prompt_points(initial_mask, box_coords, count=2)
        self.assertEqual(len(neg_pts), 2)
        for nx, ny, is_p in neg_pts:
            self.assertFalse(is_p, "Soil prompts must be negative")
            self.assertFalse(initial_mask[ny, nx], "Soil point must not be on foreground mask")

        # Compute herbicide savings before and after mock refinement
        savings_initial = compute_herbicide_savings(initial_mask, (h, w), buffer_pixels=5)

        # Simulate refined mask expanded by corrective point
        refined_mask = initial_mask.copy()
        refined_mask[60:130, 60:130] = True
        savings_refined = compute_herbicide_savings(refined_mask, (h, w), buffer_pixels=5)

        # Monotonicity: expanded weed area reduces or maintains chemical savings
        self.assertLess(savings_refined, savings_initial)
        self.assertGreaterEqual(savings_refined, 0.0)

    # =========================================================================
    # 2. Perception + Triage Routing + System 2 Statutory RAG
    # =========================================================================
    def test_cross_feature_perception_triage_system2_rag(self):
        """
        Verify end-to-end flow from low-confidence / ambiguous detection
        through triage escalation to System-2 RAG prescription.
        """
        s2_reasoner = System2Reasoner(store=self.mock_store, mock_mode=True)
        runner = VisionWorkflowRunner(
            mock_mode=True,
            system2=s2_reasoner,
        )

        initial_state = create_initial_state(self.test_image)
        # Inject ambiguous weed detection that requires System 2 deliberation
        initial_state["boxes"] = [
            create_synthetic_box(100.0, 100.0, 200.0, 200.0, label="ambiguous_weed_foliage", score=0.48)
        ]
        initial_state["masks"] = [
            create_synthetic_mask(480, 640, box=initial_state["boxes"][0], predicted_iou=0.65, label="ambiguous_weed_foliage")
        ]
        initial_state["field_metadata"] = {"crop": "cotton"}

        # Run triage node
        triage_res = runner.triage_node(initial_state)
        self.assertTrue(triage_res.get("system2_needed"), "Ambiguous / low score detection must trigger System 2 escalation")
        self.assertIn("vlm_reasoning", triage_res)

        initial_state.update(triage_res)

        # Run deliberative System 2 node
        s2_res = runner.system2_node(initial_state)
        self.assertIn("prescription_report", s2_res)
        self.assertIn("vlm_reasoning", s2_res)
        self.assertIn("prescription_report", s2_res["artifacts"])

        report = s2_res["prescription_report"]
        self.assertIn(report["status"], ["ok", "no_knowledge_found"])
        self.assertEqual(report["disclaimer"], DISCLAIMER)

        # Verify prescription artifact contract
        artifact = s2_res["artifacts"]["prescription_report"]
        self.assertEqual(artifact.type, ArtifactType.PRESCRIPTION_REPORT)
        self.assertEqual(artifact.payload, report)

    # =========================================================================
    # 3. Ambiguous Weed + Clef Flash Router + Fail-Safe Local Fallback
    # =========================================================================
    def test_cross_feature_clef_flash_multimodal_and_network_fallback(self):
        """
        Verify Clef Flash router processes multimodal telemetry and gracefully
        falls back to local DeterministicRouter on network failure.
        """
        # Crop sample for multimodal router
        crop_arr = np.array(self.test_image.crop((50, 50, 150, 150)))

        # 1. Normal execution with multimodal crop
        router = ClefFlashRouter(mock_mode=True)
        decision = router.route(
            detection_confidence=0.88,
            predicted_iou=0.91,
            area_pixels=3500,
            species_ambiguity=False,
            image_crop=crop_arr,
            label="cotton_weed",
        )
        self.assertIsInstance(decision, RouterDecision)
        self.assertEqual(decision.backend, RouterBackend.CLEF_FLASH)
        self.assertEqual(decision.action, RouterAction.ACCEPT)
        self.assertTrue(decision.metadata.get("multimodal_image_present"))
        self.assertIn("ACCEPT", decision.probabilities)

        # 2. Simulated Network Loss / Timeout -> Fail-safe local fallback
        live_router = ClefFlashRouter(
            mock_mode=False,
            api_token="test_token_cf",
            account_id="test_account_cf",
            timeout_seconds=0.1,
            fallback_router=DeterministicRouter(),
        )

        with patch.object(
            live_router,
            "_execute_cloud_inference",
            side_effect=TimeoutError("Connection timed out to Cloudflare edge"),
        ):
            fallback_decision = live_router.route(
                detection_confidence=0.92,
                predicted_iou=0.95,
                area_pixels=2000,
                species_ambiguity=False,
                image_crop=crop_arr,
                label="cotton_weed",
            )

            # Fallback router completed decision safely without raising exception
            self.assertIsInstance(fallback_decision, RouterDecision)
            self.assertEqual(fallback_decision.backend, RouterBackend.CLEF_FLASH)
            self.assertEqual(fallback_decision.action, RouterAction.ACCEPT)
            self.assertIn("Clef Flash Fallback", fallback_decision.reason)
            self.assertGreater(fallback_decision.latency_ms, 0.0)

    # =========================================================================
    # 4. Ground-Truth Evaluation Harness + Benchmark Runner + JSON Serialization
    # =========================================================================
    def test_cross_feature_ground_truth_benchmark_and_json_serialization(self):
        """
        Verify BenchmarkRunner loads manifests, computes detection/segmentation metrics,
        and serializes results to JSON and Markdown reports.
        """
        manifest_path = Path("data/manifests/eval_manifest_v1.json")
        self.assertTrue(manifest_path.exists(), "Evaluation manifest must exist")

        runner = BenchmarkRunner(
            manifest_path=manifest_path,
            mock_mode=True,
            iou_threshold=0.50,
        )

        # Run benchmark on a subset of validation split
        output = runner.run_benchmark(split="val", max_samples=2)

        self.assertIn("summary", output)
        self.assertIn("per_image_results", output)

        summary = output["summary"]
        self.assertEqual(summary["num_images_evaluated"], 2)
        self.assertIn("detection", summary)
        self.assertIn("segmentation", summary)
        self.assertIn("agronomy", summary)
        self.assertIn("latency", summary)
        self.assertIn("per_crop", summary)

        # Verify numerical ranges
        self.assertGreaterEqual(summary["detection"]["precision"], 0.0)
        self.assertLessEqual(summary["detection"]["precision"], 1.0)
        self.assertGreaterEqual(summary["segmentation"]["mean_weed_iou"], 0.0)
        self.assertLessEqual(summary["segmentation"]["mean_weed_iou"], 1.0)
        self.assertGreaterEqual(summary["agronomy"]["mean_pred_chemical_savings_pct"], 0.0)
        self.assertLessEqual(summary["agronomy"]["mean_pred_chemical_savings_pct"], 100.0)

        # Lossless JSON serialization verification
        json_str = json.dumps(output, indent=2)
        self.assertIsInstance(json_str, str)
        reloaded = json.loads(json_str)
        self.assertEqual(reloaded["summary"]["num_images_evaluated"], 2)
        self.assertEqual(len(reloaded["per_image_results"]), 2)

        # Markdown report generation
        md_report = runner.format_markdown_report(output)
        self.assertIn("# AgriAgent Vision Benchmark Evaluation Report", md_report)
        self.assertIn("Mean Weed Mask IoU", md_report)
        self.assertIn("Predicted Chemical Savings", md_report)

    # =========================================================================
    # 5. Streamlit App Image Decoding + Workflow Execution + KPI + GeoJSON
    # =========================================================================
    def test_cross_feature_streamlit_pipeline_geojson_export(self):
        """
        Verify Streamlit pipeline integration:
        Image decoding -> workflow execution -> dynamic KPI extraction -> GeoJSON export.
        """
        # 1. Test image decoding across formats
        # PIL input
        decoded_pil = decode_uploaded_image(self.test_image)
        self.assertIsInstance(decoded_pil, Image.Image)

        # Bytes input
        buf = io.BytesIO()
        self.test_image.save(buf, format="PNG")
        raw_bytes = buf.getvalue()
        decoded_bytes = decode_uploaded_image(raw_bytes)
        self.assertEqual(decoded_bytes.size, self.test_image.size)

        # Corrupt / empty bytes error handling
        with self.assertRaises(ImageDecodeError):
            decode_uploaded_image(b"")

        # 2. Execute workflow through Streamlit pipeline component
        final_state = execute_agriagent_workflow(
            image=decoded_bytes,
            mock_mode=True,
            crop="cotton",
            force_system2=True,
            target_weed_hint="Trianthema",
        )

        self.assertIn("spray_map", final_state)
        self.assertIn("prescription_report", final_state)

        # 3. Dynamic KPI extraction
        kpis = extract_kpis(final_state["spray_map"])
        self.assertIn("infestation_percentage", kpis)
        self.assertIn("chemical_savings_percentage", kpis)
        self.assertIn("weed_count", kpis)
        self.assertGreaterEqual(kpis["infestation_percentage"], 0.0)
        self.assertLessEqual(kpis["infestation_percentage"], 100.0)
        self.assertGreaterEqual(kpis["chemical_savings_percentage"], 0.0)
        self.assertLessEqual(kpis["chemical_savings_percentage"], 100.0)

        # 4. GeoJSON export
        geojson = build_spray_geojson(final_state, crop="cotton", field_id="FIELD-TEST-COTTON")
        self.assertEqual(geojson.get("type"), "FeatureCollection")
        self.assertIn("features", geojson)
        self.assertIn("metadata", geojson)

        for feature in geojson["features"]:
            self.assertEqual(feature["type"], "Feature")
            self.assertEqual(feature["geometry"]["type"], "Polygon")
            # Must have closed polygon (at least 5 points for a bounding box: 4 corners + closing point)
            coords = feature["geometry"]["coordinates"][0]
            self.assertEqual(len(coords), 5)
            self.assertEqual(coords[0], coords[-1], "Polygon must be closed")
            self.assertIn("zone_id", feature["properties"])
            self.assertIn("action", feature["properties"])
            self.assertEqual(feature["properties"]["action"], "SPRAY_ACTIVE")

        # 5. Format prescription report
        fmt_report = format_prescription_report(final_state["prescription_report"])
        self.assertIsNotNone(fmt_report)
        self.assertEqual(fmt_report["crop"], "cotton")
        self.assertIn("citations", fmt_report)
        self.assertEqual(fmt_report["disclaimer"], DISCLAIMER)

    # =========================================================================
    # 6. CIBRC Banned Chemical Detection + Dosage Ceiling Clamping + Disclaimer
    # =========================================================================
    def test_cross_feature_statutory_banned_filter_and_dosage_clamping(self):
        """
        Verify statutory regulatory safety:
        - Intercepts banned herbicides (Table 3.3) and suppresses spraying.
        - Clamps excessive dosages exceeding Table 4.3 statutory ceilings.
        - Preserves mandatory statutory disclaimer across all reports.
        """
        # 1. Banned herbicide in query
        for banned_chem in ["nitrofen", "paraquat dimethyl sulphate", "metoxuron", "2,4,5-t"]:
            with self.subTest(banned_chemical=banned_chem):
                presc = create_chemical_prescription(
                    weed_name=f"Invasive weed treated with {banned_chem}",
                    crop_stage="vegetative",
                    crop="cotton",
                    store=self.canonical_store,
                )
                self.assertEqual(presc.status, "unapproved_chemical_flagged")
                self.assertIsNone(presc.active_ingredient)
                self.assertIsNone(presc.dosage_ai_g_per_ha)
                self.assertIn("BANNED HERBICIDE", presc.safety_warning)
                self.assertEqual(presc.disclaimer, DISCLAIMER)

        # 2. Dosage ceiling clamping test
        # In cotton, Table 4.3 maximum approved ceiling for Pyrithiobac-sodium is 75.0 g a.i./ha
        ceiling = get_dosage_ceiling("cotton", "pyrithiobac-sodium")
        self.assertEqual(ceiling, 75.0)

        # Create custom mock store hit recommending excessive 180.0 g a.i./ha with explicit Herbicide label
        excessive_store = InMemoryKnowledgeStore(
            documents=[
                {
                    "text": (
                        "ICAR Trial: Herbicide: Pyrithiobac-sodium at 180.0 g a.i./ha "
                        "for resistant Trianthema in cotton. Dilute in 500 liters water."
                    ),
                    "source": "icar_experimental_bulletin.pdf",
                    "page": 12,
                    "authority": "ICAR",
                    "weed_keywords": ["trianthema"],
                }
            ]
        )

        presc_clamped = create_chemical_prescription(
            weed_name="Trianthema",
            crop_stage="vegetative",
            crop="cotton",
            store=excessive_store,
        )

        self.assertEqual(presc_clamped.status, "ok")
        self.assertTrue(presc_clamped.dosage_clamped, "Dosage exceeding 75 g a.i./ha must be flagged as clamped")
        self.assertEqual(presc_clamped.dosage_ai_g_per_ha, 75.0, "Dosage must be clamped to statutory ceiling (75.0)")
        self.assertEqual(presc_clamped.original_dosage_ai_g_per_ha, 180.0)
        self.assertIn("Statutory dosage ceiling exceeded", presc_clamped.safety_warning)
        self.assertEqual(presc_clamped.disclaimer, DISCLAIMER)


if __name__ == "__main__":
    unittest.main()
