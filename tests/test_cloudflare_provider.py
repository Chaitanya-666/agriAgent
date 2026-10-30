"""Cloudflare reasoning provider, the provider switch, and photo shrinking (30 Oct 2026)."""

import base64
import io
import os
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from src.agronomy.provider_contract import LLMRequest
from src.agronomy.providers import (
    HostedCloudflareProvider,
    HostedGroqProvider,
    reasoning_provider,
)
from src.agronomy.providers.local_qwen import MAX_IMAGE_SIDE, image_to_base64_url


class TestProviderSwitch(unittest.TestCase):
    def test_cloudflare_is_the_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("REASONING_PROVIDER", None)
            self.assertIsInstance(reasoning_provider(), HostedCloudflareProvider)

    def test_groq_can_be_switched_back_on(self):
        with patch.dict(os.environ, {"REASONING_PROVIDER": "groq"}):
            self.assertIsInstance(reasoning_provider(), HostedGroqProvider)

    def test_mock_mode_uses_the_canned_reply(self):
        provider = reasoning_provider(mock_mode=True)
        self.assertIsInstance(provider, HostedGroqProvider)
        self.assertTrue(provider.mock_mode)

    def test_unknown_provider_is_refused(self):
        with patch.dict(os.environ, {"REASONING_PROVIDER": "openai"}):
            with self.assertRaises(ValueError):
                reasoning_provider()


class TestHostedCloudflareProvider(unittest.TestCase):
    def test_missing_keys_give_an_error_not_an_exception(self):
        resp = HostedCloudflareProvider(account_id="", api_token="").generate(
            LLMRequest(user_prompt="hi")
        )
        self.assertIn("CLOUDFLARE_ACCOUNT_ID", resp.error)
        self.assertEqual(resp.text_content, "")

    @patch("src.agronomy.providers.hosted_cloudflare.requests.post")
    def test_request_turns_thinking_off_and_parses_json(self, post):
        post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "choices": [{"message": {"content": '{"answer": "weed", "confidence": 0.8}'}}],
                "usage": {"prompt_tokens": 250, "completion_tokens": 12},
            },
        )
        provider = HostedCloudflareProvider(account_id="acc", api_token="tok")
        resp = provider.generate(
            LLMRequest(user_prompt="Reply as JSON", image=Image.new("RGB", (64, 64)))
        )
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "@cf/qwen/qwen3.8-27b")
        self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})
        self.assertNotIn("reasoning_effort", payload)  # Cloudflare rejects Groq's "none"
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertIn("/accounts/acc/ai/v1/chat/completions", post.call_args.args[0])
        self.assertEqual(resp.parsed_json, {"answer": "weed", "confidence": 0.8})
        self.assertIsNone(resp.error)

    @patch("src.agronomy.providers.hosted_cloudflare.requests.post", side_effect=OSError("offline"))
    def test_network_failure_is_reported(self, _post):
        resp = HostedCloudflareProvider(account_id="a", api_token="t").generate(
            LLMRequest(user_prompt="x")
        )
        self.assertIn("offline", resp.error)


class TestPhotoShrinking(unittest.TestCase):
    def decoded_size(self, image):
        url = image_to_base64_url(image)
        return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).size

    def test_large_photo_is_shrunk_keeping_its_shape(self):
        self.assertEqual(self.decoded_size(Image.new("RGB", (4032, 3024))), (MAX_IMAGE_SIDE, 576))

    def test_small_photo_is_left_alone(self):
        self.assertEqual(self.decoded_size(Image.new("RGB", (512, 512))), (512, 512))

    def test_original_image_is_not_modified(self):
        photo = Image.new("RGB", (2000, 1000))
        image_to_base64_url(photo)
        self.assertEqual(photo.size, (2000, 1000))


if __name__ == "__main__":
    unittest.main()
