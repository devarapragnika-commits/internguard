"""OpenAI-compatible client pointed at OpenRouter for GPT Astra."""

from openai import OpenAI

from backend.config import get_api_key, get_base_url, get_model


def get_client() -> OpenAI:
    return OpenAI(
        base_url=get_base_url(),
        api_key=get_api_key(),
        default_headers={
            "HTTP-Referer": "https://internguard.local",
            "X-OpenRouter-Title": "InternGuard",
        },
    )


def chat(messages: list[dict], model: str | None = None, **kwargs):
    client = get_client()
    return client.chat.completions.create(
        model=model or get_model(),
        messages=messages,
        **kwargs,
    )
