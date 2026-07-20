import os
from openai import OpenAI


api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not set")


client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
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
    print(error)