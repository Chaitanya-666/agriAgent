"""
tests/test_farmer_summary.py
The farmer summary uses only pipeline facts; the model may reword them but never add advice.
"""

import unittest

from src.agronomy.farmer_summary import farmer_summary, template_summary, build_facts
from src.agronomy.provider_contract import LLMResponse


class FakeProvider:
    def __init__(self, text="", error=None):
        self.text, self.error, self.requests = text, error, []

    def generate(self, request):
        self.requests.append(request)
        return LLMResponse(
            provider="fake", model_name="fake", text_content=self.text, error=self.error
        )


SPRAYED = {
    "spray_map": {
        "weed_count": 2,
        "spray_allowed": True,
        "infestation_percentage": 3.1,
        "chemical_savings_percentage": 90.0,
        "withheld_masks": [{"label": "weed plant", "reason": "mixed"}],
        "escalation": [{"verdict": "weed"}, {"verdict": "unsure"}],
    }
}


class TestFarmerSummary(unittest.TestCase):
    def test_template_states_zones_and_withheld_plants(self):
        text = template_summary(build_facts(SPRAYED, "cotton", mock_mode=False))
        self.assertIn("2 weed patch(es)", text)
        self.assertIn("1 plant(s) were not sprayed", text)
        self.assertNotIn("test data", text)

    def test_unsure_count_comes_from_plant_rules_not_withheld_masks(self):
        # F4: 7 detector masks withheld by the gate (crop plants it protected), 0 unsure patches.
        base = {"weed_count": 2, "spray_allowed": True, "withheld_masks": [{}] * 7}
        quiet = {"spray_map": {**base, "plant_rules": {"weed": 2, "crop": 9, "unsure": 0}}}
        self.assertNotIn("not sprayed", farmer_summary(quiet, "sugar beet", False)["text"])
        unsure = {"spray_map": {**base, "plant_rules": {"weed": 2, "crop": 9, "unsure": 3}}}
        self.assertIn(
            "3 plant(s) were not sprayed", farmer_summary(unsure, "sugar beet", False)["text"]
        )

    def test_nothing_sprayed_says_so(self):
        state = {"spray_map": {"weed_count": 0, "spray_allowed": True, "withheld_masks": []}}
        self.assertIn(
            "nothing is marked", farmer_summary(state, "sugar beet", mock_mode=False)["text"]
        )

    def test_mock_never_calls_the_model(self):
        provider = FakeProvider("anything")
        out = farmer_summary(SPRAYED, "cotton", mock_mode=True, language="Hindi", provider=provider)
        self.assertEqual(out["source"], "template")
        self.assertIn("test data", out["text"])
        self.assertEqual(provider.requests, [])

    def test_model_rewording_is_used(self):
        out = farmer_summary(
            SPRAYED, "cotton", False, "Marathi", FakeProvider("दोन तण भाग फवारणीसाठी चिन्हांकित.")
        )
        self.assertEqual(out["source"], "model")

    def test_model_error_falls_back_to_template(self):
        out = farmer_summary(SPRAYED, "cotton", False, "Hindi", FakeProvider(error="429"))
        self.assertEqual(out["source"], "template")

    def test_invented_dose_is_rejected(self):
        out = farmer_summary(
            SPRAYED, "cotton", False, "English", FakeProvider("Spray 75 g/ha of glyphosate.")
        )
        self.assertEqual(out["source"], "template")


if __name__ == "__main__":
    unittest.main()
