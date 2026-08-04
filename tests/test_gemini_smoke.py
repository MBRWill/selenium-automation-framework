from __future__ import annotations

from dataclasses import dataclass
import inspect
import unittest

from modules.ai import gemini_config
from modules.ai import gemini_unknown_question
from tools import test_gemini


@dataclass
class RecordedRequest:
    kwargs: dict | None = None


class FakeCompletions:
    def __init__(self, request: RecordedRequest, error: Exception | None = None):
        self.request = request
        self.error = error

    def create(self, **kwargs):
        self.request.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return object()


class FakeClient:
    def __init__(self, request: RecordedRequest, error: Exception | None = None):
        self.chat = type("Chat", (), {})()
        self.chat.completions = FakeCompletions(request, error)


def configured(secret="unit-test-secret", model="unit-test-model"):
    return gemini_config.GeminiConfig(
        configured=True,
        api_key=secret,
        model=model,
        reason_code="gemini_configured",
    )


class GeminiSmokeTests(unittest.TestCase):
    def test_runtime_and_smoke_import_the_same_loader(self):
        self.assertIs(
            gemini_unknown_question.load_gemini_config,
            gemini_config.load_gemini_config,
        )
        self.assertIs(
            test_gemini.load_gemini_config,
            gemini_config.load_gemini_config,
        )

    def test_missing_key_smoke_makes_no_provider_request(self):
        calls = []
        output = []

        def forbidden_factory(**kwargs):
            calls.append(kwargs)
            raise AssertionError("provider construction must be skipped")

        exit_code = test_gemini.run_smoke_test(
            gemini_config.load_gemini_config({}),
            client_factory=forbidden_factory,
            output=output.append,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls, [])
        self.assertIn("configured=false", output)
        self.assertIn("provider_initialization=skipped", output)
        self.assertIn("request_result=not_run", output)
        self.assertIn("request_category=gemini_api_key_missing", output)

    def test_provider_uses_resolved_config_and_model(self):
        config = configured()
        constructor_calls = []
        request = RecordedRequest()
        output = []

        def factory(**kwargs):
            constructor_calls.append(kwargs)
            return FakeClient(request)

        exit_code = test_gemini.run_smoke_test(
            config,
            client_factory=factory,
            output=output.append,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(constructor_calls, [{
            "api_key": config.api_key,
            "base_url": gemini_config.GEMINI_OPENAI_ENDPOINT,
            "max_retries": 0,
        }])
        self.assertEqual(request.kwargs["model"], config.model)
        self.assertEqual(request.kwargs["messages"], [{
            "role": "user",
            "content": "Reply with exactly the word OK.",
        }])
        self.assertIn("request_result=success", output)

    def test_request_exception_output_does_not_expose_key(self):
        secret = "unit-test-secret-that-must-not-appear"
        request = RecordedRequest()
        output = []

        exit_code = test_gemini.run_smoke_test(
            configured(secret=secret),
            client_factory=lambda **_kwargs: FakeClient(
                request, RuntimeError(f"provider detail included {secret}")
            ),
            output=output.append,
        )

        self.assertEqual(exit_code, 1)
        self.assertNotIn(secret, "\n".join(output))
        self.assertIn("request_result=failure", output)
        self.assertIn("request_category=provider_request_error", output)

    def test_provider_initialization_exception_output_does_not_expose_key(self):
        secret = "unit-test-constructor-secret"
        output = []

        def failing_factory(**_kwargs):
            raise RuntimeError(f"provider detail included {secret}")

        exit_code = test_gemini.run_smoke_test(
            configured(secret=secret),
            client_factory=failing_factory,
            output=output.append,
        )

        self.assertEqual(exit_code, 1)
        self.assertNotIn(secret, "\n".join(output))
        self.assertIn("provider_initialization=failed", output)
        self.assertIn("request_category=provider_initialization_error", output)

    def test_smoke_tool_has_no_browser_or_selenium_dependency(self):
        source = inspect.getsource(test_gemini).casefold()

        self.assertNotIn("selenium", source)
        self.assertNotIn("webdriver", source)
        self.assertNotIn("runaibot", source)


if __name__ == "__main__":
    unittest.main()
