"""
tests/test_escalation_agent.py
The escalation agent (T1.7) with fake evidence sources, and the gate's rules for its verdicts.
"""

import unittest

import numpy as np
from PIL import Image

from src.agents.escalation_agent import EscalationAgent
from src.agents.evidence import Evidence
from src.workflow import VisionWorkflowRunner


class FakeSource:
    def __init__(self, name, verdict, confidence, cost):
        self.name, self.verdict, self.confidence, self.cost = name, verdict, confidence, cost
        self.calls = 0

    def __call__(self, image, box, crop):
        self.calls += 1
        return Evidence(self.name, self.verdict, self.confidence, self.cost, "fake")


IMAGE = Image.new("RGB", (100, 100), (120, 95, 65))
BOX = [10, 10, 40, 40]


class TestAgentDecisions(unittest.TestCase):
    def test_answer_is_capped_by_source_accuracy(self):
        agent = EscalationAgent(sources=[], weights={"a": 0.8})
        # Fully confident, but the source is right only 80% of the time.
        self.assertAlmostEqual(agent.p_weed([Evidence("a", "weed", 1.0, 0)]), 0.8)
        self.assertIsNone(agent.p_weed([Evidence("a", None, 0.0, 0)]))

    def test_agreeing_sources_multiply_disagreeing_cancel(self):
        agent = EscalationAgent(sources=[], weights={"clef_flash": 0.7, "groq_vlm": 0.8})
        clef, groq = Evidence("clef_flash", "weed", 0.95, 1), Evidence("groq_vlm", "weed", 0.95, 3)
        self.assertLess(agent.p_weed([groq]), 0.85)  # one source never decides
        self.assertGreaterEqual(agent.p_weed([clef, groq]), 0.85)  # two strongly agreeing do
        # At 0.9 confidence each, Clef + Groq give 0.847: just short, so the plant stays withheld.
        lukewarm = [Evidence("clef_flash", "weed", 0.9, 1), Evidence("groq_vlm", "weed", 0.9, 3)]
        self.assertLess(agent.p_weed(lukewarm), 0.85)
        self.assertAlmostEqual(agent.p_weed([groq, Evidence("groq_vlm", "crop", 0.95, 3)]), 0.5)

    def test_default_weights_need_two_sources(self):
        agent = EscalationAgent(sources=[])
        for source in ("row_rule", "clef_flash", "groq_vlm"):
            self.assertLess(agent.p_weed([Evidence(source, "weed", 1.0, 0)]), 0.85)

    def test_stops_once_decisive(self):
        cheap = FakeSource("cheap", "weed", 1.0, 1)
        expensive = FakeSource("expensive", "crop", 0.99, 3)
        agent = EscalationAgent(
            sources=[cheap, expensive], weights={"cheap": 0.95, "expensive": 0.8}
        )
        review = agent.review_plant(IMAGE, BOX, "cotton", budget=10)
        self.assertEqual(review.verdict, "weed")
        self.assertEqual(expensive.calls, 0)
        self.assertEqual(review.calls_used, 1)

    def test_budget_skips_sources_it_cannot_afford(self):
        cheap = FakeSource("cheap", "weed", 0.6, 1)
        expensive = FakeSource("expensive", "weed", 0.99, 3)
        review = EscalationAgent(sources=[cheap, expensive]).review_plant(
            IMAGE, BOX, "cotton", budget=2
        )
        self.assertEqual(expensive.calls, 0)
        self.assertEqual(review.verdict, "unsure")

    def test_disagreement_is_unsure(self):
        sources = [FakeSource("a", "weed", 0.9, 0), FakeSource("b", "crop", 0.9, 0)]
        review = EscalationAgent(sources=sources, weights={"a": 0.9, "b": 0.9}).review_plant(
            IMAGE, BOX, "beet", 5
        )
        self.assertEqual(review.verdict, "unsure")

    def test_budget_is_shared_across_plants_largest_first(self):
        source = FakeSource("s", "weed", 0.6, 2)
        agent = EscalationAgent(sources=[source], budget_per_image=3)
        candidates = [
            {"index": 0, "label": "weed", "box": [0, 0, 5, 5]},
            {"index": 1, "label": "weed", "box": [0, 0, 50, 50]},
        ]
        reviews = agent.review(IMAGE, candidates, "cotton")
        self.assertEqual(reviews[0].index, 1)  # larger plant reviewed first
        self.assertEqual(reviews[0].calls_used, 2)
        self.assertEqual(reviews[1].calls_used, 0)  # only 1 call unit left


class FixedAgent:
    """Stands in for EscalationAgent inside the workflow."""

    decide_at = 0.85

    def __init__(self, verdict=None, error=None):
        self.verdict, self.error, self.seen = verdict, error, []

    def review(self, image, candidates, crop):
        self.seen = candidates
        if self.error:
            raise self.error
        out = []
        for c in candidates:
            review = EscalationAgent(sources=[]).review_plant(image, c["box"], crop, 0)
            review.index, review.label = c["index"], c["label"]
            review.verdict, review.p_weed = self.verdict, 0.9 if self.verdict == "weed" else 0.1
            out.append(review)
        return out


def mask(label, score, iou=0.95):
    pixels = np.zeros((100, 100), dtype=bool)
    pixels[20:30, 20:30] = True
    box = {"x1": 20.0, "y1": 20.0, "x2": 30.0, "y2": 30.0, "label": label, "score": score}
    return {"label": label, "mask_array": pixels, "predicted_iou": iou, "box": box}


class TestGateWithAgent(unittest.TestCase):
    def run_gate(self, agent, masks, prompt="weed . cotton plant ."):
        runner = VisionWorkflowRunner(mock_mode=True, escalation_agent=agent)
        state = {
            "image": IMAGE,
            "masks": masks,
            "text_prompt": prompt,
            "field_metadata": {"crop": "cotton"},
        }
        return runner.spray_map_node(state)

    def test_without_agent_low_confidence_weed_is_withheld(self):
        out = self.run_gate(None, [mask("weed", 0.5)])
        self.assertEqual(out["spray_map"]["weed_count"], 0)
        self.assertEqual(out["spray_map"]["escalation"], [])

    def test_agent_weed_verdict_is_sprayed(self):
        out = self.run_gate(FixedAgent("weed"), [mask("weed", 0.5)])
        self.assertEqual(out["spray_map"]["weed_count"], 1)
        zone = out["artifacts"]["spray_map"].payload["approved_spray_zones"][0]
        self.assertEqual(zone["approved_by"], "escalation_agent")

    def test_agent_crop_verdict_is_not_sprayed(self):
        out = self.run_gate(FixedAgent("crop"), [mask("weed plant", 0.6)])
        self.assertEqual(out["spray_map"]["weed_count"], 0)
        self.assertEqual(out["spray_map"]["escalation"][0]["verdict"], "crop")

    def test_agent_error_means_nothing_is_sprayed(self):
        out = self.run_gate(FixedAgent(error=RuntimeError("network down")), [mask("weed", 0.5)])
        self.assertEqual(out["spray_map"]["weed_count"], 0)

    def test_poor_mask_is_not_sprayed_even_if_agent_says_weed(self):
        agent = FixedAgent("weed")
        out = self.run_gate(agent, [mask("weed", 0.5, iou=0.79)])
        self.assertEqual(out["spray_map"]["weed_count"], 0)

    def test_explicit_crop_label_is_never_escalated(self):
        agent = FixedAgent("weed")
        out = self.run_gate(agent, [mask("cotton plant", 0.6)])
        self.assertEqual(agent.seen, [])
        self.assertEqual(out["spray_map"]["weed_count"], 0)


if __name__ == "__main__":
    unittest.main()
