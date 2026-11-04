"""Load InternGuard settings from the project .env file."""

from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-astra"

_loaded_names: list[str] = []


def _clean(value: str | None) -> str:
    if not value:
        return ""
    return (
        value.strip()
        .strip('"')
        .strip("'")
        .replace(" ", "")
        .replace("\t", "")
        .replace("\x00", "")
    )


def _read_env_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff") or b"\x00" in raw[:120]:
        return raw.decode("utf-16")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    return raw.decode("utf-8")


def _load_env() -> None:
    global _loaded_names
    _loaded_names = []
    if not ENV_PATH.exists():
        return

    text = _read_env_text(ENV_PATH)
    for raw_line in text.splitlines():
        line = raw_line.strip().replace("\x00", "")
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip().lstrip("\ufeff").replace("\x00", "")
        value = _clean(value)
        if name:
            os.environ[name] = value
            _loaded_names.append(name)


_load_env()


def get_api_key() -> str:
    key = _clean(
        os.getenv("GPT_ASTRA_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if key:
        return key

    exists = ENV_PATH.exists()
    size = ENV_PATH.stat().st_size if exists else 0
    found = ", ".join(_loaded_names) if _loaded_names else "(none)"
    raise RuntimeError(
        "Could not load GPT_ASTRA_API_KEY.\n"
        f"  .env path: {ENV_PATH}\n"
        f"  exists: {exists}, size: {size} bytes\n"
        f"  variables found: {found}\n"
        "Put the key on one line with no spaces, save the file, then run python test_llm.py again."
    )


def get_base_url() -> str:
    return _clean(os.getenv("OPENROUTER_BASE_URL")) or DEFAULT_BASE_URL


def get_model() -> str:
    return os.getenv("GPT_ASTRA_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
)
CORS_ORIGIN_REGEX = r"chrome-extension://.*|http://(localhost|127\.0\.0\.1|\[::1\]):\d+"
DEFAULT_ANALYZE_RATE_LIMIT = 30
DEFAULT_ANALYZE_RATE_WINDOW = 60.0


def get_cors_origins() -> list[str]:
    """Return allowed browser origins. Comma-separated CORS_ORIGINS, or the Vite defaults."""
    raw = os.getenv("CORS_ORIGINS", "").strip().strip('"').strip("'")
    if not raw:
        return list(DEFAULT_CORS_ORIGINS)
    found: list[str] = []
    for item in raw.split(","):
        origin = item.strip()
        if origin and origin not in found:
            found.append(origin)
    return found or list(DEFAULT_CORS_ORIGINS)


def get_analyze_rate_limit() -> int:
    raw = os.getenv("ANALYZE_RATE_LIMIT", "").strip()
    if not raw:
        return DEFAULT_ANALYZE_RATE_LIMIT
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_ANALYZE_RATE_LIMIT


def get_analyze_rate_window() -> float:
    raw = os.getenv("ANALYZE_RATE_WINDOW", "").strip()
    if not raw:
        return DEFAULT_ANALYZE_RATE_WINDOW
    try:
        return max(1.0, float(raw))
    except ValueError:
        return DEFAULT_ANALYZE_RATE_WINDOW
