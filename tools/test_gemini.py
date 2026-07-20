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
    response = client.chat.completions.create(
        model="gemini-3.5-flash",
        messages=[
            {
                "role": "system",
                "content": (
                    "You assist with job application questions. "
                    "Never invent qualifications or experience."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Answer this Spanish application question in one short sentence: "
                    "¿Por qué te interesa trabajar como Data Analyst?"
                ),
            },
        ],
    )

    print("Gemini response:")
    print(response.choices[0].message.content)

except Exception as error:
    print("Gemini API test failed:")
    print(type(error).__name__)
    print(error)