"""
tests/test_farmer_summary.py
The farmer summary uses only pipeline facts; the model may reword them but never add advice.
"""

import unittest

from src.agronomy.farmer_summary import LABEL_NOTE, build_facts, farmer_summary, template_summary
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


WRONG_CROP = {
    "spray_map": {"weed_count": 3, "spray_allowed": True, "crop_examples": 0, "plant_rules": {}}
}
PRESCRIBED = {
    **SPRAYED,
    "prescription_report": {
        "status": "ok",
        "active_ingredient": "Pyrithiobac-sodium",
        "dosage_ai_g_per_ha": 75,
        "target_weed": "Amaranthus",
    },
}


class TestFarmerSummary(unittest.TestCase):
    def test_wrong_crop_warning_in_template(self):
        # F27: MT-03 (beet photo, crop set to cotton) gave a summary silent about the warning.
        text = farmer_summary(WRONG_CROP, "cotton", False)["text"]
        self.assertIn("no plant in this photo was recognised as cotton", text)

    def test_wrong_crop_warning_survives_model_rewording(self):
        out = farmer_summary(WRONG_CROP, "cotton", False, "Hindi", FakeProvider("तीन खरपतवार।"))
        self.assertEqual(out["source"], "model")
        self.assertIn("कपास के रूप में नहीं पहचाना गया", out["text"])

    def test_no_wrong_crop_warning_when_crop_found(self):
        state = {"spray_map": {**WRONG_CROP["spray_map"], "crop_examples": 4}}
        self.assertNotIn("recognised", farmer_summary(state, "cotton", False)["text"])

    def test_label_caveat_added_after_model_text(self):
        # F29: MT-09 Hindi summary turned the ICAR dose into an instruction, without the label line.
        out = farmer_summary(
            PRESCRIBED, "cotton", False, "Hindi", FakeProvider("पाइरिथायोबैक 75 ग्राम डालें।")
        )
        self.assertTrue(out["text"].endswith(LABEL_NOTE["Hindi"]))
        prompt = FakeProvider("x")
        farmer_summary(PRESCRIBED, "cotton", False, "Marathi", prompt)
        self.assertIn("never as an instruction", prompt.requests[0].user_prompt)

    def test_english_template_has_label_caveat(self):
        text = farmer_summary(PRESCRIBED, "cotton", False)["text"]
        self.assertIn("Pyrithiobac-sodium at 75 g a.i./ha", text)
        self.assertIn("read the product label", text)

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

    def test_hindi_prompt_names_the_crop_correctly(self):
        provider = FakeProvider("ठीक")
        farmer_summary(SPRAYED, "sugar beet", False, "Hindi", provider)
        self.assertIn("sugar beet = चुकंदर", provider.requests[0].user_prompt)

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
