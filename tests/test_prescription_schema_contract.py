"""Coverage-driven tests for src/agronomy/prescription_schema.py (Lab 5). IDs: CT-P-xx.

The report showed 54%: the pipeline only ever built prescriptions and read a few keys, so
the dictionary-style access (`p["weed"]`, `p["evidence"] = [...]`, `"x" in p`, `p.get`)
and the citation text sync were never run. Those are the paths older callers depend on.
"""

import unittest

from pydantic import ValidationError

from src.agronomy.prescription_schema import ChemicalPrescription, CitationRecord

CITATION = {"source": "CIBRC major uses", "page": 12, "authority": "CIBRC", "text_snippet": "Pendimethalin 30 EC"}


def prescription(**overrides):
    data = {
        "status": "ok",
        "crop": "cotton",
        "target_weed": "Trianthema portulacastrum",
        "active_ingredient": "Pendimethalin",
        "dosage_ai_g_per_ha": 1000.0,
        "toxicity_band": "YELLOW",
        "citations": [CITATION],
        "disclaimer": "Advisory only.",
    }
    data.update(overrides)
    return ChemicalPrescription(**data)


class CitationTests(unittest.TestCase):
    def test_text_only_fills_snippet(self):  # CT-P-01
        c = CitationRecord(source="s", page=1, authority="ICAR", text="from text")
        self.assertEqual((c.text, c.text_snippet), ("from text", "from text"))

    def test_snippet_only_fills_text(self):  # CT-P-02
        c = CitationRecord(**CITATION)
        self.assertEqual(c.text, "Pendimethalin 30 EC")

    def test_both_given_are_kept_as_is(self):  # CT-P-03
        c = CitationRecord(source="s", page=1, authority="ICAR", text="long", text_snippet="short")
        self.assertEqual((c.text, c.text_snippet), ("long", "short"))

    def test_neither_given_is_refused(self):  # CT-P-04
        with self.assertRaises(ValidationError):
            CitationRecord(source="s", page=1, authority="ICAR")

    def test_existing_record_passes_through(self):  # CT-P-05
        c = CitationRecord(**CITATION)
        self.assertEqual(CitationRecord.model_validate(c), c)

    def test_validator_leaves_non_dict_input_alone(self):  # CT-P-14
        # Pydantic skips the validator for an existing record (CT-P-05), so the "not a dict"
        # branch only runs when the validator is called directly.
        marker = object()
        self.assertIs(CitationRecord.sync_text_fields(marker), marker)


class ContractTests(unittest.TestCase):
    def test_only_known_status_and_toxicity_values(self):  # CT-P-06
        for field, value in (("status", "approved"), ("toxicity_band", "PURPLE")):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    prescription(**{field: value})
        for band in ("RED", "YELLOW", "BLUE", "GREEN", None):
            self.assertEqual(prescription(toxicity_band=band).toxicity_band, band)

    def test_required_fields(self):  # CT-P-07
        with self.assertRaises(ValidationError):
            ChemicalPrescription(status="ok", crop="cotton", target_weed="x")  # no disclaimer


class DictAccessTests(unittest.TestCase):
    def setUp(self):
        self.p = prescription(regional_note="Kharif only")  # extra fields are allowed

    def test_aliases_fields_and_extras(self):  # CT-P-08
        self.assertEqual(self.p["weed"], "Trianthema portulacastrum")
        self.assertEqual(self.p["crop"], "cotton")
        self.assertEqual(self.p["regional_note"], "Kharif only")
        self.assertEqual(
            self.p["evidence"],
            [{"text": "Pendimethalin 30 EC", "source": "CIBRC major uses", "page": 12, "authority": "CIBRC"}],
        )
        with self.assertRaises(KeyError):
            self.p["no_such_key"]

    def test_get_returns_default_for_missing(self):  # CT-P-09
        self.assertEqual(self.p.get("dosage_ai_g_per_ha"), 1000.0)
        self.assertEqual(self.p.get("no_such_key", "n/a"), "n/a")
        self.assertIsNone(self.p.get("no_such_key"))

    def test_contains(self):  # CT-P-10
        for key in ("weed", "evidence", "crop", "regional_note"):
            self.assertIn(key, self.p)
        self.assertNotIn("no_such_key", self.p)
        self.assertNotIn("other_extra", prescription())

    def test_setting_fields_aliases_and_extras(self):  # CT-P-11
        self.p["dosage_ai_g_per_ha"] = 750.0
        self.p["weed"] = "Cyperus rotundus"
        self.p["evidence"] = [
            {"source": "ICAR", "page": 3, "authority": "ICAR", "text": "spot spray"},
            CitationRecord(**CITATION),
        ]
        self.p["batch_id"] = "B-7"
        self.assertEqual(self.p.dosage_ai_g_per_ha, 750.0)
        self.assertEqual(self.p.target_weed, "Cyperus rotundus")
        self.assertEqual([c.page for c in self.p.citations], [3, 12])
        self.assertEqual(self.p["batch_id"], "B-7")

    def test_setting_an_extra_when_none_exist_yet(self):  # CT-P-12
        p = prescription()
        p.__pydantic_extra__ = None  # state an instance can be left in after copying
        p["first_extra"] = 1
        self.assertEqual(p["first_extra"], 1)

    def test_extras_are_found_by_hasattr_first(self):  # CT-P-15
        # Coverage finding: in __getitem__ the branch `if extra and item in extra: return
        # extra[item]` cannot run under pydantic v2, because extras are also attributes, so
        # the `hasattr` check above it already returns them. Documented, not changed.
        self.assertTrue(hasattr(self.p, "regional_note"))

    def test_to_dict_has_old_and_new_keys(self):  # CT-P-13
        d = self.p.to_dict()
        self.assertEqual(d["weed"], d["target_weed"])
        self.assertEqual(d["evidence"][0]["page"], 12)
        self.assertEqual(d["citations"][0]["source"], "CIBRC major uses")
        self.assertEqual(d["regional_note"], "Kharif only")


if __name__ == "__main__":
    unittest.main()
