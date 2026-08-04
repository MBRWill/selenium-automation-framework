# Gemini developer configuration

Gemini runtime configuration is read only from environment variables:

- `GEMINI_API_KEY` is required.
- `GEMINI_MODEL` is optional and defaults to `gemini-3.5-flash-lite`.

Export the variables in the same shell that starts Python. This repository does
not automatically load `.env` files.

```bash
export GEMINI_API_KEY='your-key'
export GEMINI_MODEL='gemini-3.5-flash-lite'
.venv/bin/python tools/test_gemini.py
```

The smoke test makes one minimal, non-personal provider request. It reports
configuration status, model, provider initialization, and a request result
category. It does not print the key or the provider response.

To confirm the variables exist without displaying the secret value:

```bash
.venv/bin/python -c 'import os; print("GEMINI_API_KEY set:", bool(os.getenv("GEMINI_API_KEY", "").strip()))'
.venv/bin/python -c 'import os; print("GEMINI_MODEL set:", bool(os.getenv("GEMINI_MODEL", "").strip()))'
```

After testing, remove both variables from the current shell:

```bash
unset GEMINI_API_KEY GEMINI_MODEL
```

The smoke test verifies only basic Gemini provider connectivity. It does not
open a browser or verify LinkedIn, Easy Apply, form answering, Review, or
Submit behavior.
