import unittest

from modules.ai.gemini_config import (
    DEFAULT_GEMINI_MODEL,
    GeminiConfig,
    load_gemini_config,
)


class GeminiConfigTests(unittest.TestCase):
    def test_missing_key_is_not_configured(self):
        config = load_gemini_config({})

        self.assertEqual(config, GeminiConfig(
            configured=False,
            api_key=None,
            model=DEFAULT_GEMINI_MODEL,
            reason_code="gemini_api_key_missing",
        ))

    def test_blank_key_is_not_configured(self):
        config = load_gemini_config({"GEMINI_API_KEY": "   "})

        self.assertFalse(config.configured)
        self.assertIsNone(config.api_key)
        self.assertEqual(config.reason_code, "gemini_api_key_missing")

    def test_present_key_is_configured_and_redacted(self):
        secret = "unit-test-secret"
        config = load_gemini_config({"GEMINI_API_KEY": secret})

        self.assertTrue(config.configured)
        self.assertEqual(config.api_key, secret)
        self.assertNotIn(secret, repr(config))
        self.assertNotIn(secret, str(config))
        self.assertNotIn(secret, repr(config.diagnostics()))
        self.assertIn("<redacted>", repr(config))

    def test_missing_or_blank_model_uses_default(self):
        missing = load_gemini_config({"GEMINI_API_KEY": "unit-test-key"})
        blank = load_gemini_config({
            "GEMINI_API_KEY": "unit-test-key",
            "GEMINI_MODEL": "  ",
        })

        self.assertEqual(missing.model, DEFAULT_GEMINI_MODEL)
        self.assertEqual(blank.model, DEFAULT_GEMINI_MODEL)

    def test_explicit_model_overrides_default(self):
        config = load_gemini_config({
            "GEMINI_API_KEY": "unit-test-key",
            "GEMINI_MODEL": "test-model",
        })

        self.assertEqual(config.model, "test-model")


if __name__ == "__main__":
    unittest.main()
