"""Coverage-driven tests for src/agents/evidence.py (Lab 5). IDs: CT-E-xx.

The coverage report showed this module at 33%: only the row rule ran in other tests, and
the two model-backed sources (Cloudflare Clef Flash over HTTP, Qwen through a provider)
never ran because they need the network. Here the network is replaced by test doubles:
`requests.post` is patched and the provider is a small fake, so every branch runs offline.

Safety rule checked throughout: a source that cannot give a clear answer returns verdict
None (no opinion). It must never turn a failure into "crop" or "weed".
"""

import base64
import io
import os
import unittest
from unittest import mock

import numpy as np
import requests
from PIL import Image

from src.agents import evidence
from src.agents.evidence import ClefEvidence, QwenVlmEvidence, RowRuleEvidence, cut_patch, data_url
from src.agronomy.provider_contract import BaseAgronomyProvider, LLMResponse

SOIL = (125, 98, 68)
GREEN = (60, 180, 50)


def field_with_rows(vertical=True, size=(640, 480), pitch=160, width=30):
    """Brown soil with green crop rows every `pitch` px."""
    w, h = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[:] = SOIL
    for c in range(pitch // 2, (w if vertical else h), pitch):
        if vertical:
            arr[:, c - width // 2 : c + width // 2] = GREEN
        else:
            arr[c - width // 2 : c + width // 2, :] = GREEN
    return Image.fromarray(arr)


class CutPatchTests(unittest.TestCase):
    def setUp(self):
        self.image = Image.new("RGB", (640, 480), SOIL)

    def test_long_side_is_scaled_to_384(self):  # CT-E-01
        patch = cut_patch(self.image, [200, 150, 300, 230])
        self.assertEqual(max(patch.size), 384)

    def test_small_box_gets_at_least_64_px_of_context(self):  # CT-E-02
        # A 10 px box would give a 10 px crop; the margin rule widens it to 64 px first.
        x1, y1, x2, y2 = 300, 200, 310, 210
        mx = max(0.15 * (x2 - x1), (64 - (x2 - x1)) / 2)
        self.assertEqual(mx, 27.0)
        patch = cut_patch(self.image, [x1, y1, x2, y2], long_side=64)
        self.assertEqual(patch.size, (64, 64))

    def test_box_at_the_corner_is_clamped_to_the_image(self):  # CT-E-03
        patch = cut_patch(self.image, [0, 0, 40, 40], long_side=100)
        self.assertEqual(patch.size, (100, 100))  # square crop, no negative coordinates

    def test_data_url_is_a_jpeg(self):  # CT-E-04
        url = data_url(Image.new("RGBA", (50, 40), (10, 200, 10, 128)))
        prefix = "data:image/jpeg;base64,"
        self.assertTrue(url.startswith(prefix))
        img = Image.open(io.BytesIO(base64.b64decode(url[len(prefix):])))
        self.assertEqual((img.format, img.size), ("JPEG", (50, 40)))


class RowRuleTests(unittest.TestCase):
    rule = RowRuleEvidence()

    def test_plant_on_a_vertical_row_is_crop(self):  # CT-E-05
        e = self.rule(field_with_rows(vertical=True), [60, 100, 100, 140], "cotton")  # centre x=80
        self.assertEqual((e.verdict, e.confidence, e.cost), ("crop", 0.6, 0))
        self.assertIn("vertical rows", e.detail)
        self.assertIn("on the row", e.detail)

    def test_plant_between_rows_is_weed(self):  # CT-E-06
        e = self.rule(field_with_rows(vertical=True), [140, 100, 180, 140], "cotton")  # centre x=160
        self.assertEqual(e.verdict, "weed")
        self.assertIn("off the row", e.detail)

    def test_horizontal_rows_are_detected(self):  # CT-E-07
        e = self.rule(field_with_rows(vertical=False), [300, 60, 340, 100], "wheat")  # centre y=80
        self.assertEqual(e.verdict, "crop")
        self.assertIn("horizontal rows", e.detail)

    def test_no_rows_means_no_opinion(self):  # CT-E-08
        for image in (Image.new("RGB", (320, 240), SOIL), Image.new("RGB", (320, 240), GREEN)):
            with self.subTest(colour=image.getpixel((0, 0))):
                e = self.rule(image, [100, 100, 140, 140], "cotton")
                self.assertIsNone(e.verdict)
                self.assertEqual(e.confidence, 0.0)
                self.assertIn("no clear rows", e.detail)

    def test_box_outside_the_photo_is_clamped(self):  # CT-E-09
        e = self.rule(field_with_rows(vertical=True), [5000, 10, 5040, 50], "cotton")
        self.assertIn(e.verdict, ("crop", "weed"))  # no IndexError


def clef_reply(status=200, answers=None, text=""):
    resp = mock.Mock()
    resp.status_code = status
    resp.text = text
    resp.json.return_value = {"result": {"answers": answers or {}}}
    return resp


@mock.patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "acct123", "CLOUDFLARE_API_TOKEN": "tok456"})
class ClefTests(unittest.TestCase):
    image = Image.new("RGB", (320, 240), SOIL)
    box = [100, 100, 160, 160]

    def test_missing_credentials_cost_nothing_and_give_no_opinion(self):  # CT-E-10
        with mock.patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "", "CLOUDFLARE_API_TOKEN": ""}):
            with mock.patch.object(evidence.requests, "post") as post:
                e = ClefEvidence()(self.image, self.box, "cotton")
        post.assert_not_called()
        self.assertEqual((e.verdict, e.cost), (None, 0))

    def test_clear_answer_is_used(self):  # CT-E-11
        answers = {"plant": {"choice": "weed", "probabilities": {"weed": 0.83, "crop": 0.17}}}
        with mock.patch.object(evidence.requests, "post", return_value=clef_reply(answers=answers)) as post:
            e = ClefEvidence(timeout=12)(self.image, self.box, "cotton")
        self.assertEqual((e.verdict, e.confidence, e.cost), ("weed", 0.83, 1))
        self.assertEqual(e.extra["raw"]["choice"], "weed")
        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs
        self.assertIn("/accounts/acct123/ai/run/", url)
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer tok456"})
        self.assertEqual(kwargs["timeout"], 12)
        self.assertTrue(kwargs["json"]["images"][0].startswith("data:image/jpeg;base64,"))
        self.assertIn("cotton", kwargs["json"]["questions"]["plant"]["instructions"])

    def test_missing_probability_defaults_to_half(self):  # CT-E-12
        answers = {"plant": {"choice": "crop"}}
        with mock.patch.object(evidence.requests, "post", return_value=clef_reply(answers=answers)):
            e = ClefEvidence()(self.image, self.box, "cotton")
        self.assertEqual((e.verdict, e.confidence), ("crop", 0.5))

    def test_unexpected_choice_gives_no_opinion(self):  # CT-E-13
        for answers in ({"plant": {"choice": "maybe"}}, {}):
            with self.subTest(answers=answers):
                with mock.patch.object(evidence.requests, "post", return_value=clef_reply(answers=answers)):
                    e = ClefEvidence()(self.image, self.box, "cotton")
                self.assertIsNone(e.verdict)
                self.assertIn("unexpected answer", e.detail)

    def test_http_error_gives_no_opinion(self):  # CT-E-14
        with mock.patch.object(evidence.requests, "post", return_value=clef_reply(503, text="busy" * 100)):
            e = ClefEvidence()(self.image, self.box, "cotton")
        self.assertIsNone(e.verdict)
        self.assertTrue(e.detail.startswith("HTTP 503"))
        self.assertLessEqual(len(e.detail), len("HTTP 503: ") + 200)  # body is cut to 200 chars

    def test_network_failure_gives_no_opinion(self):  # CT-E-15
        with mock.patch.object(evidence.requests, "post", side_effect=requests.Timeout("slow")):
            e = ClefEvidence()(self.image, self.box, "cotton")
        self.assertEqual((e.verdict, e.cost), (None, 1))
        self.assertIn("request failed", e.detail)


class FakeProvider(BaseAgronomyProvider):
    """Returns the queued responses in order and records every request."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return self.responses.pop(0)


def reply(parsed=None, error=None, text="{}"):
    return LLMResponse(provider="fake", model_name="qwen-test", text_content=text,
                       parsed_json=parsed, error=error)


class QwenTests(unittest.TestCase):
    image = Image.new("RGB", (320, 240), SOIL)
    box = [100, 100, 160, 160]

    def ask(self, *responses, max_retries=4):
        provider = FakeProvider(*responses)
        with mock.patch.object(evidence.time, "sleep") as sleep:
            e = QwenVlmEvidence(provider=provider, max_retries=max_retries)(self.image, self.box, "wheat")
        return e, provider, sleep

    def test_clear_answer(self):  # CT-E-16
        e, provider, _ = self.ask(reply({"answer": "Crop", "confidence": 0.9}, text='{"answer":"crop"}'))
        self.assertEqual((e.verdict, e.confidence, e.cost), ("crop", 0.9, 3))
        request = provider.requests[0]
        self.assertIn("wheat", request.user_prompt)
        self.assertEqual(max(request.image.size), 384)  # the patch, not the whole photo

    def test_confidence_is_clamped_or_defaulted(self):  # CT-E-17
        cases = ((1.7, 1.0), (-0.2, 0.0), ("high", 0.7), (None, 0.7))
        for raw, expected in cases:
            with self.subTest(raw=raw):
                e, _, _ = self.ask(reply({"answer": "weed", "confidence": raw}))
                self.assertEqual((e.verdict, e.confidence), ("weed", expected))
        e, _, _ = self.ask(reply({"answer": "weed"}))  # key missing entirely
        self.assertEqual(e.confidence, 0.7)

    def test_unparsed_reply_gives_no_opinion(self):  # CT-E-18
        for parsed in ({"answer": "tree"}, None):
            with self.subTest(parsed=parsed):
                e, _, _ = self.ask(reply(parsed, text="I think it is a tree"))
                self.assertIsNone(e.verdict)
                self.assertIn("unparsed reply", e.detail)

    def test_provider_error_gives_no_opinion_without_retry(self):  # CT-E-19
        e, provider, sleep = self.ask(reply(error="HTTP 500 upstream"))
        self.assertIsNone(e.verdict)
        self.assertEqual(e.detail, "error: HTTP 500 upstream")
        self.assertEqual(len(provider.requests), 1)
        sleep.assert_not_called()

    def test_rate_limit_is_retried_with_growing_waits(self):  # CT-E-20
        e, provider, sleep = self.ask(
            reply(error="429 Too Many Requests"),
            reply(error="429 Too Many Requests"),
            reply({"answer": "weed", "confidence": 0.8}),
        )
        self.assertEqual(e.verdict, "weed")
        self.assertEqual(len(provider.requests), 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [15, 30])

    def test_rate_limit_after_last_retry_gives_no_opinion(self):  # CT-E-21
        e, provider, sleep = self.ask(reply(error="429 slow down"), reply(error="429 slow down"),
                                      max_retries=1)
        self.assertIsNone(e.verdict)
        self.assertEqual(e.detail, "error: 429 slow down")
        self.assertEqual((len(provider.requests), sleep.call_count), (2, 1))

    def test_final_rate_limited_line_needs_a_negative_retry_count(self):  # CT-E-22
        # Coverage finding: the closing `return ... "rate limited"` is reached only when the
        # loop never runs (max_retries < 0). With max_retries >= 0 the last attempt always
        # returns through the `if resp.error` branch. Documented, not changed (core code).
        e, provider, _ = self.ask(max_retries=-1)
        self.assertEqual((e.verdict, e.detail, len(provider.requests)), (None, "rate limited", 0))


if __name__ == "__main__":
    unittest.main()
