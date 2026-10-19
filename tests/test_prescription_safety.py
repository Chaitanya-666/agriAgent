"""
tests/test_prescription_safety.py
Statutory Safety & Guardrail Test Suite:
1. Pydantic ChemicalPrescription & CitationRecord schema contracts.
2. Safe no_knowledge_found handling with zero hallucinated chemicals.
3. CIBRC Banned Chemical Filter (Table 3.3).
4. Statutory Dosage Ceiling Check (Table 4.3 upper limits).
5. Mandatory Statutory Disclaimer presence.
"""

import unittest
from typing import Any, Dict, List

from src.agronomy.knowledge_store import InMemoryKnowledgeStore, KB_DIR
from src.agronomy.prescription import (
    BANNED_HERBICIDES,
    DISCLAIMER,
    STATUTORY_DOSAGE_CEILINGS_G_PER_HA,
    check_banned_chemicals,
    create_chemical_prescription,
    get_dosage_ceiling,
    get_herbicide_prescription,
)
from src.agronomy.prescription_schema import ChemicalPrescription, CitationRecord


class TestPrescriptionSafety(unittest.TestCase):
    """Statutory agronomy safety and prescription guardrail tests."""

    @classmethod
    def setUpClass(cls):
        cls.store = InMemoryKnowledgeStore()
        cls.store.ingest(KB_DIR)
        cls.empty_store = InMemoryKnowledgeStore(documents=[])

    def test_citation_record_schema(self):
        """Verify CitationRecord schema validation and field synchronization."""
        rec = CitationRecord(
            source="icar_bulletin.pdf",
            page=35,
            authority="ICAR",
            text_snippet="Sample citation text.",
        )
        self.assertEqual(rec.source, "icar_bulletin.pdf")
        self.assertEqual(rec.page, 35)
        self.assertEqual(rec.authority, "ICAR")
        self.assertEqual(rec.text_snippet, "Sample citation text.")
        self.assertEqual(rec.text, "Sample citation text.")

    def test_chemical_prescription_schema(self):
        """Verify ChemicalPrescription schema fields, validation, and dict access."""
        presc = ChemicalPrescription(
            status="ok",
            crop="cotton",
            target_weed="Parthenium",
            active_ingredient="Pyrithiobac-sodium",
            formulation="Pyrithiobac-sodium 10% EC",
            dosage_ai_g_per_ha=75.0,
            water_volume_l_per_ha=500.0,
            pre_harvest_interval_days=160,
            toxicity_band="BLUE",
            citations=[
                CitationRecord(
                    source="icar_bulletin.pdf",
                    page=35,
                    authority="ICAR",
                    text_snippet="Pyrithiobac snippet",
                )
            ],
            disclaimer=DISCLAIMER,
        )
        self.assertEqual(presc.status, "ok")
        self.assertEqual(presc.crop, "cotton")
        self.assertEqual(presc["weed"], "Parthenium")
        self.assertEqual(len(presc["evidence"]), 1)
        self.assertEqual(presc["evidence"][0]["source"], "icar_bulletin.pdf")

        dump = presc.to_dict()
        self.assertEqual(dump["target_weed"], "Parthenium")
        self.assertEqual(dump["weed"], "Parthenium")
        self.assertIn("evidence", dump)

    def test_empty_store_returns_no_knowledge_zero_chemicals(self):
        """Verify querying an empty store yields no_knowledge_found with zero chemicals."""
        report = get_herbicide_prescription(
            "Parthenium", "vegetative", crop="cotton", store=self.empty_store
        )
        self.assertEqual(report["status"], "no_knowledge_found")
        self.assertIsNone(report["active_ingredient"])
        self.assertIsNone(report["formulation"])
        self.assertIsNone(report["dosage_ai_g_per_ha"])
        self.assertEqual(report["evidence"], [])
        self.assertEqual(report["citations"], [])
        self.assertEqual(report["disclaimer"], DISCLAIMER)

    def test_unsupported_out_of_distribution_weed_returns_no_knowledge(self):
        """Verify arbitrary unknown weed query does not hallucinate chemicals."""
        report = get_herbicide_prescription(
            "NonExistentMartianWeed_AlphaBetaGamma",
            "vegetative",
            crop="cotton",
            store=self.store,
            distance_threshold=0.25,
        )
        self.assertEqual(report["status"], "no_knowledge_found")
        self.assertIsNone(report["active_ingredient"])
        self.assertEqual(report["evidence"], [])

    def test_banned_chemical_filter_nitrofen(self):
        """Verify CIBRC banned chemical Nitrofen triggers unapproved_chemical_flagged."""
        report = get_herbicide_prescription(
            "Nitrofen", "vegetative", crop="cotton", store=self.store
        )
        self.assertEqual(report["status"], "unapproved_chemical_flagged")
        self.assertIsNone(report["active_ingredient"])
        self.assertIsNotNone(report["safety_warning"])
        self.assertIn("nitrofen", report["safety_warning"].lower())

    def test_banned_chemical_filter_all_table_3_3_entries(self):
        """Verify all Table 3.3 banned/withdrawn/refused herbicides are recognized."""
        for banned_chem in BANNED_HERBICIDES:
            with self.subTest(chemical=banned_chem):
                match = check_banned_chemicals(f"Apply {banned_chem} to weeds")
                self.assertIsNotNone(match, f"Failed to identify banned chemical: {banned_chem}")
                self.assertEqual(match[0], banned_chem)

                report = get_herbicide_prescription(
                    banned_chem, "vegetative", crop="cotton", store=self.store
                )
                self.assertEqual(report["status"], "unapproved_chemical_flagged")
                self.assertIsNone(report["active_ingredient"])

    def test_statutory_dosage_ceiling_cotton_pyrithiobac(self):
        """Verify Pyrithiobac-sodium dosage ceiling in cotton (max 75.0 g a.i./ha)."""
        ceiling = get_dosage_ceiling("cotton", "Pyrithiobac-sodium")
        self.assertEqual(ceiling, 75.0)

        # Compliant custom store document: 70 g a.i./ha
        compliant_doc = [
            {
                "text": "ICAR Recommendation: Crop: cotton | Weed: Trianthema | Herbicide: Pyrithiobac-sodium 10% EC | Active ingredient: Pyrithiobac-sodium | Dosage a.i.: 70.0 g/ha | Dilution in water: 500 L | Waiting period: 160 days | Source: bulletin.pdf p.35",
                "crop": "cotton",
                "weed_species": "Trianthema",
                "chemical": "Pyrithiobac-sodium 10% EC",
                "active_ingredient": "Pyrithiobac-sodium",
                "dosage_ai_g_per_ha": 70.0,
                "water_l_per_ha": 500.0,
                "waiting_period_days": 160,
                "authority": "ICAR",
                "source": "bulletin.pdf",
                "page": 35,
            }
        ]
        comp_store = InMemoryKnowledgeStore(documents=compliant_doc)
        presc_comp = create_chemical_prescription(
            "Trianthema", "vegetative", crop="cotton", store=comp_store
        )
        self.assertEqual(presc_comp.status, "ok")
        self.assertEqual(presc_comp.dosage_ai_g_per_ha, 70.0)
        self.assertFalse(presc_comp.dosage_clamped)

        # Excessive dosage custom store document: 150 g a.i./ha (exceeds 75 g ceiling)
        excessive_doc = [
            {
                "text": "ICAR Recommendation: Crop: cotton | Weed: Trianthema | Herbicide: Pyrithiobac-sodium 10% EC | Active ingredient: Pyrithiobac-sodium | Dosage a.i.: 150.0 g/ha | Dilution in water: 500 L | Waiting period: 160 days | Source: bulletin.pdf p.35",
                "crop": "cotton",
                "weed_species": "Trianthema",
                "chemical": "Pyrithiobac-sodium 10% EC",
                "active_ingredient": "Pyrithiobac-sodium",
                "dosage_ai_g_per_ha": 150.0,
                "water_l_per_ha": 500.0,
                "waiting_period_days": 160,
                "authority": "ICAR",
                "source": "bulletin.pdf",
                "page": 35,
            }
        ]
        excess_store = InMemoryKnowledgeStore(documents=excessive_doc)
        presc_excess = create_chemical_prescription(
            "Trianthema", "vegetative", crop="cotton", store=excess_store
        )
        self.assertEqual(presc_excess.status, "ok")
        self.assertTrue(presc_excess.dosage_clamped)
        self.assertEqual(presc_excess.original_dosage_ai_g_per_ha, 150.0)
        self.assertEqual(
            presc_excess.dosage_ai_g_per_ha,
            75.0,
            "Over-dosage must be clamped to statutory ceiling of 75.0 g/ha",
        )
        self.assertIsNotNone(presc_excess.safety_warning)
        self.assertIn("ceiling exceeded", presc_excess.safety_warning.lower())

    def test_statutory_dosage_ceilings_cotton_chemicals(self):
        """Verify Table 4.3 ceilings for all registered cotton herbicides."""
        cotton_ceilings = STATUTORY_DOSAGE_CEILINGS_G_PER_HA["cotton"]
        self.assertEqual(cotton_ceilings["fenoxaprop-p-ethyl"], 67.5)
        self.assertEqual(cotton_ceilings["quizalofop-ethyl"], 50.5)
        self.assertEqual(cotton_ceilings["glufosinate-ammonium"], 450.0)
        self.assertEqual(cotton_ceilings["fluchloralin"], 1200.0)
        self.assertEqual(cotton_ceilings["pendimethalin"], 1250.0)
        self.assertEqual(cotton_ceilings["diuron"], 1500.0)
        self.assertEqual(cotton_ceilings["alachlor"], 2500.0)

    def test_mandatory_statutory_disclaimer_present(self):
        """Verify statutory disclaimer is present in every prescription status."""
        for weed in ["Parthenium", "Nitrofen", "NonExistentWeed"]:
            report = get_herbicide_prescription(weed, "vegetative", crop="cotton", store=self.store)
            self.assertIn("disclaimer", report)
            self.assertEqual(report["disclaimer"], DISCLAIMER)


if __name__ == "__main__":
    unittest.main()


class TestIcarTableMatchesBulletin(unittest.TestCase):
    """K12: values checked against icar_dwr_herbicide_use_bulletin22.pdf on 20 Oct 2026."""

    def row(self, crop, chemical):
        from src.agronomy.knowledge_store import CANONICAL_ICAR_TABLE_ROWS

        return next(
            r for r in CANONICAL_ICAR_TABLE_ROWS if r["crop"] == crop and r["chemical"] == chemical
        )

    def test_rice_pyrazosulfuron_row(self):
        # The old row said 20 g and 75 days: above the approved dose, 20 days short on waiting.
        r = self.row("rice", "Pyrazosulfuron-ethyl 10% WP")
        self.assertEqual(
            (r["dosage_ai_g_per_ha"], r["waiting_period_days"], r["page"]), (15.0, 95, 33)
        )
        self.assertNotIn("Echinochloa", r["weed_species"])

    def test_dose_ceilings(self):
        from src.agronomy.prescription import get_dosage_ceiling

        self.assertEqual(get_dosage_ceiling("rice", "pyrazosulfuron-ethyl"), 15.0)
        self.assertEqual(get_dosage_ceiling("rice", "bispyribac-sodium"), 20.0)
        self.assertEqual(get_dosage_ceiling("wheat", "2,4-d"), 750.0)

    def test_missing_waiting_period_is_not_zero_days(self):
        from src.agronomy.knowledge_store import format_table_row_document

        r = self.row("cotton", "Diuron 80% WP")
        self.assertIsNone(r["waiting_period_days"])
        self.assertIn(
            "Waiting period (PHI): not stated in the bulletin", format_table_row_document(r)
        )

    def test_clodinafop_lists_only_the_bulletin_weed(self):
        self.assertEqual(
            self.row("wheat", "Clodinafop-propargyl 15% WP")["weed_species"], "Phalaris minor"
        )
