"""Smoke-test that the .env OpenRouter key can call GPT Astra."""

from backend.config import get_model
from backend.llm import chat


def main() -> None:
    response = chat(
        messages=[
            {
                "role": "system",
                "content": "You are InternGuard. Reply with one short sentence.",
            },
            {
                "role": "user",
                "content": "Confirm you are ready to analyze internship messages for scam risk.",
            },
        ],
        max_tokens=40,
    )
    text = response.choices[0].message.content
    print(f"Model: {get_model()}")
    print(f"Reply: {text}")
    print("Connection OK")


if __name__ == "__main__":
    main()
