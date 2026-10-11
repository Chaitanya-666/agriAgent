"""
tests/test_providers.py
Unit tests for Unified Agronomy LLM / VLM Provider Interface.
Verifies:
1. LLMRequest and LLMResponse schema validation.
2. LocalQwenProvider (mock mode, structured output, error handling).
3. HostedGroqProvider (mock mode, rate limit / error fallback chaining).
4. VLM Critic valid model identifier and Pydantic parsing.
"""
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image

from src.agronomy.provider_contract import (
    BaseAgronomyProvider,
    LLMRequest,
    LLMResponse,
)
from src.agronomy.providers.hosted_groq import HostedGroqProvider
from src.agronomy.providers.local_qwen import (
    DEFAULT_MODEL as QWEN_DEFAULT_MODEL,
    LocalQwenProvider,
    extract_json,
    image_to_base64_url,
)
from src.agronomy.vlm_critic import (
    DEFAULT_MODEL as VLM_DEFAULT_MODEL,
    VLMCritic,
    VLMDiagnosis,
    parse_json,
)


class TestProviders(unittest.TestCase):
    """Provider contract and implementation tests."""

    def test_llm_request_schema(self):
        """Verify LLMRequest schema defaults and attributes."""
        req = LLMRequest(user_prompt="Diagnose weed in cotton field")
        self.assertEqual(req.user_prompt, "Diagnose weed in cotton field")
        self.assertEqual(req.system_prompt, "")
        self.assertEqual(req.temperature, 0.0)
        self.assertEqual(req.timeout_seconds, 30.0)
        self.assertIsNone(req.image)

    def test_llm_response_schema(self):
        """Verify LLMResponse schema validation and fields."""
        resp = LLMResponse(
            provider="test_provider",
            model_name="test_model",
            text_content='{"crop": "cotton"}',
            parsed_json={"crop": "cotton"},
            prompt_tokens=10,
            completion_tokens=5,
            latency_ms=12.5,
        )
        self.assertEqual(resp.provider, "test_provider")
        self.assertEqual(resp.model_name, "test_model")
        self.assertEqual(resp.parsed_json, {"crop": "cotton"})
        self.assertEqual(resp.latency_ms, 12.5)

    def test_local_qwen_provider_mock(self):
        """Verify LocalQwenProvider mock execution adheres to LLMResponse contract."""
        provider = LocalQwenProvider(mock_mode=True)
        req = LLMRequest(user_prompt="Identify weed in image", image=Image.new("RGB", (32, 32)))
        resp = provider.generate(req)

        self.assertEqual(resp.provider, "local_qwen")
        self.assertEqual(resp.model_name, QWEN_DEFAULT_MODEL)
        self.assertIsInstance(resp.parsed_json, dict)
        self.assertIn("crop", resp.parsed_json)
        self.assertIn("weed_or_disease", resp.parsed_json)
        self.assertGreater(resp.latency_ms, 0.0)

    def test_local_qwen_json_extraction(self):
        """Verify robust JSON extraction from text and markdown fences."""
        # 1. Plain JSON string
        self.assertEqual(extract_json('{"crop": "cotton"}'), {"crop": "cotton"})

        # 2. Markdown fenced code block
        fenced = "Here is the diagnosis:\n```json\n{\"crop\": \"cotton\", \"stage\": \"flowering\"}\n```\nHope this helps."
        parsed = extract_json(fenced)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.get("crop"), "cotton")
        self.assertEqual(parsed.get("stage"), "flowering")

        # 3. Leading and trailing explanatory text
        noisy = "Diagnostic analysis reveals: {\"crop\": \"wheat\", \"severity\": \"low\"} across the field."
        parsed_noisy = extract_json(noisy)
        self.assertIsNotNone(parsed_noisy)
        self.assertEqual(parsed_noisy.get("crop"), "wheat")

    def test_image_to_base64_url(self):
        """Verify image encoding to base64 data URL."""
        img = Image.new("RGB", (16, 16), color="green")
        url = image_to_base64_url(img)
        self.assertTrue(url.startswith("data:image/jpeg;base64,"))

        self.assertIsNone(image_to_base64_url(None))

    def test_hosted_groq_provider_mock(self):
        """Verify HostedGroqProvider mock execution adheres to LLMResponse contract."""
        provider = HostedGroqProvider(mock_mode=True)
        req = LLMRequest(user_prompt="Analyze herbicide dosage for cotton")
        resp = provider.generate(req)

        self.assertEqual(resp.provider, "hosted_groq")
        self.assertTrue(any(sub in resp.model_name.lower() for sub in ["qwen", "llama"]))
        self.assertIsInstance(resp.parsed_json, dict)
        self.assertIn("crop", resp.parsed_json)
        self.assertGreater(resp.latency_ms, 0.0)

    def test_hosted_groq_fallback_chaining_on_missing_key(self):
        """Verify fallback provider executes when primary Groq key is absent."""
        fallback = LocalQwenProvider(mock_mode=True)
        # Instantiate Groq provider with no key and not in mock mode
        groq_provider = HostedGroqProvider(api_key="", fallback_provider=fallback, mock_mode=False)

        req = LLMRequest(user_prompt="Diagnose field")
        resp = groq_provider.generate(req)

        # Response must come from the fallback provider
        self.assertEqual(resp.provider, "local_qwen")
        self.assertIsNotNone(resp.parsed_json)

    def test_hosted_groq_fallback_chaining_on_api_error(self):
        """Verify fallback provider executes when Groq endpoint raises an exception."""
        fallback = LocalQwenProvider(mock_mode=True)
        groq_provider = HostedGroqProvider(
            api_key="gsk_test_mock_key_12345",
            fallback_provider=fallback,
            mock_mode=False,
        )

        req = LLMRequest(user_prompt="Diagnose field")

        # Mock requests.post to simulate a network outage or 500 error
        with patch("requests.post", side_effect=ConnectionError("Groq endpoint unreachable")):
            resp = groq_provider.generate(req)

        self.assertEqual(resp.provider, "local_qwen")
        self.assertIsNotNone(resp.parsed_json)

    def test_vlm_critic_model_identifier(self):
        """Verify VLMCritic uses verified model identifier and valid Pydantic diagnosis."""
        self.assertIn("Qwen2.5", VLM_DEFAULT_MODEL)
        self.assertNotIn("Qwen3", VLM_DEFAULT_MODEL)

        critic = VLMCritic(mock_mode=True)
        diag = critic.diagnose(Image.new("RGB", (64, 64)))
        self.assertEqual(diag["crop"], "cotton")
        self.assertIn("Parthenium", diag["weed_or_disease"])

        # Pydantic validation
        validated = VLMDiagnosis.model_validate(diag)
        self.assertEqual(validated.crop, "cotton")
        self.assertEqual(validated.severity, "medium")

    def test_parse_json_pydantic_validation(self):
        """Verify parse_json produces validated schema output."""
        valid_json_text = '```json\n{"crop": "cotton", "weed_or_disease": "Amaranthus", "crop_stage": "seedling", "severity": "low", "explanation": "test"}\n```'
        out = parse_json(valid_json_text)
        self.assertEqual(out["crop"], "cotton")
        self.assertEqual(out["weed_or_disease"], "Amaranthus")
        self.assertEqual(out["severity"], "low")
        self.assertNotIn("parse_error", out)


if __name__ == "__main__":
    unittest.main()
