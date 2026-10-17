"""
tests/test_agronomy.py
Agronomy unit tests: KnowledgeStore, prescription generation, VLM critic parsing, and System-2 node.
Runs unconditionally without skipping when ChromaDB is not installed.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.agronomy.knowledge_store import InMemoryKnowledgeStore, KnowledgeStore
from src.agronomy.prescription import get_herbicide_prescription
from src.agronomy.prescription_schema import ChemicalPrescription
from src.agronomy.system2_node import System2Reasoner
from src.agronomy.vlm_critic import parse_json
from src.state import ArtifactType

try:
    import chromadb
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

FIX = Path(__file__).parent / "fixtures"


class TestAgronomy(unittest.TestCase):
    """Agronomy unit test suite running pure logic and storage tests unconditionally."""

    def setUp(self):
        # Unconditional setup: uses KnowledgeStore when ChromaDB is installed,
        # otherwise uses InMemoryKnowledgeStore with identical contract.
        if HAS_CHROMADB:
            self.tmp = tempfile.mkdtemp()
            self.store = KnowledgeStore(db_dir=self.tmp, embedding="hash")
            self.store.ingest(FIX, authority="ICAR")
        else:
            self.tmp = None
            self.store = InMemoryKnowledgeStore()
            self.store.ingest(FIX, authority="ICAR")

    def tearDown(self):
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ingest_and_query(self):
        """Verify querying indexed documents returns expected text and source metadata."""
        hits = self.store.query("Testweed alpha cotton herbicide", k=4)
        self.assertTrue(hits, "Query must return at least one matching document")
        self.assertIn("ExampleChem-X", hits[0]["text"])
        self.assertEqual(hits[0]["source"], "agronomy_test_doc.txt")

    def test_prescription_keys(self):
        """Verify generated prescription contains ok status, evidence citations, and disclaimer."""
        r = get_herbicide_prescription("Testweed alpha", "vegetative", store=self.store)
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["evidence"])
        self.assertIn("disclaimer", r)

    def test_cotton_evidence_never_used_for_another_crop(self):
        """Issue #11: wheat, rice and sugar beet all received the cotton herbicide."""
        store = InMemoryKnowledgeStore()
        store.ingest()  # the built-in ICAR table: cotton, wheat, rice, beet root, banned rows
        cotton = get_herbicide_prescription("Trianthema", "vegetative", crop="cotton", store=store)
        self.assertEqual(cotton["crop"], "cotton")
        for crop in ("wheat", "rice", "sugar beet"):
            with self.subTest(crop=crop):
                r = get_herbicide_prescription("Trianthema", "vegetative", crop=crop, store=store)
                self.assertNotEqual(r.get("active_ingredient"), cotton.get("active_ingredient"))
                for citation in r["evidence"]:
                    self.assertNotIn("cotton", citation["text"].lower())

    def test_empty_store_does_not_invent(self):
        """Verify querying an empty knowledge store yields safe no_knowledge_found status."""
        if HAS_CHROMADB:
            empty = KnowledgeStore(db_dir=tempfile.mkdtemp(), embedding="hash")
        else:
            empty = InMemoryKnowledgeStore(documents=[])
        r = get_herbicide_prescription("Parthenium", "vegetative", store=empty)
        self.assertEqual(r["status"], "no_knowledge_found")
        self.assertEqual(r["evidence"], [])

    def test_parse_json(self):
        """Verify JSON parsing and extraction from text with surrounding noise."""
        self.assertEqual(parse_json('xx {"crop": "cotton"} yy')["crop"], "cotton")
        self.assertTrue(parse_json("no json")["parse_error"])

    def test_system2_node_mock(self):
        """Verify System2Reasoner node generates prescription report artifact."""
        s2 = System2Reasoner(store=self.store, mock_mode=True)
        out = s2.system2_node({
            "image": Image.new("RGB", (64, 64)),
            "artifacts": {},
            "field_metadata": {"crop": "cotton"},
        })
        self.assertIn("prescription_report", out)
        self.assertEqual(out["artifacts"]["prescription_report"].type, ArtifactType.PRESCRIPTION_REPORT)

    def test_table_aware_metadata_extraction(self):
        """Verify table-aware ingestion indexes rich statutory metadata fields."""
        from src.agronomy.knowledge_store import KB_DIR
        store = InMemoryKnowledgeStore()
        store.ingest(KB_DIR)
        hits = store.query("Pyrithiobac-sodium cotton", k=4)
        self.assertTrue(hits)
        top = hits[0]
        self.assertIn("crop", top)
        self.assertIn("chemical", top)
        self.assertIn("active_ingredient", top)
        self.assertIn("dosage_ai_g_per_ha", top)
        self.assertIn("authority", top)
        self.assertEqual(top["authority"], "ICAR")

    def test_distance_threshold_filtering(self):
        """Verify distance threshold in query() filters out low-similarity hits."""
        hits = self.store.query("alien interstellar spacecraft engine", distance_threshold=0.2)
        self.assertEqual(hits, [], "Hits above distance threshold must be filtered out, returning []")

    def test_prescription_schema_validation(self):
        """Verify Pydantic model validation of ChemicalPrescription."""
        r = get_herbicide_prescription("Testweed alpha", "vegetative", store=self.store)
        presc = ChemicalPrescription.model_validate(r)
        self.assertEqual(presc.status, "ok")
        self.assertEqual(presc.crop, "cotton")


if __name__ == "__main__":
    unittest.main()
