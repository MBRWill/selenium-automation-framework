from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openai import OpenAI

from modules.ai.gemini_config import (
    GEMINI_OPENAI_ENDPOINT,
    load_gemini_config,
)


config = load_gemini_config()

if not config.configured:
    raise SystemExit(config.reason_code)


client = OpenAI(
    api_key=config.api_key,
    base_url=GEMINI_OPENAI_ENDPOINT,
    max_retries=0,
)


try:
    models = client.models.list()

    print("Available Gemini models:")
    for model in models.data:
        model_id = model.id.lower()

        if "gemini" in model_id and (
            "flash" in model_id
            or "pro" in model_id
        ):
            print(model.id)

except Exception as error:
    print("Failed to list Gemini models:")
    print(type(error).__name__)
