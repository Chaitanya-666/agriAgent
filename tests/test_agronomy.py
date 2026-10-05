import shutil, tempfile, unittest
from pathlib import Path

from PIL import Image

from src.agronomy.knowledge_store import KnowledgeStore
from src.agronomy.prescription import get_herbicide_prescription
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
    def setUp(self):
        if not HAS_CHROMADB:
            self.skipTest("chromadb is required for KnowledgeStore tests")
        self.tmp = tempfile.mkdtemp()
        self.store = KnowledgeStore(db_dir=self.tmp, embedding="hash")
        self.store.ingest(FIX, authority="ICAR")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ingest_and_query(self):
        hits = self.store.query("Testweed alpha cotton herbicide")
        self.assertTrue(hits)
        self.assertIn("ExampleChem-X", hits[0]["text"])
        self.assertEqual(hits[0]["source"], "agronomy_test_doc.txt")

    def test_prescription_keys(self):
        r = get_herbicide_prescription("Testweed alpha", "vegetative", store=self.store)
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["evidence"])
        self.assertIn("disclaimer", r)

    def test_empty_store_does_not_invent(self):
        empty = KnowledgeStore(db_dir=tempfile.mkdtemp(), embedding="hash")
        r = get_herbicide_prescription("Parthenium", "vegetative", store=empty)
        self.assertEqual(r["status"], "no_knowledge_found")
        self.assertEqual(r["evidence"], [])

    def test_parse_json(self):
        self.assertEqual(parse_json('xx {"crop": "cotton"} yy')["crop"], "cotton")
        self.assertTrue(parse_json("no json")["parse_error"])

    def test_system2_node_mock(self):
        s2 = System2Reasoner(store=self.store, mock_mode=True)
        out = s2.system2_node({"image": Image.new("RGB", (64, 64)), "artifacts": {}, "field_metadata": {"crop": "cotton"}})
        self.assertIn("prescription_report", out)
        self.assertEqual(out["artifacts"]["prescription_report"].type, ArtifactType.PRESCRIPTION_REPORT)


if __name__ == "__main__":
    unittest.main()
