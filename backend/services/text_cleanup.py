"""Shared cleanup so disguised spelling still matches phrase checks.

The original message stays as written for anything shown to the user.
This cleaned form is only for matching. Screenshot OCR calls the same
function after its line-break and spaced-URL repairs.
"""

from __future__ import annotations

import re
import unicodedata

_INVISIBLE = frozenset(
    {
        "\u200b",
        "\u200c",
        "\u200d",
        "\u2060",
        "\ufeff",
        "\u00ad",
        "\u180e",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)

# Common Cyrillic and Greek letters that look like Latin.
_LOOKALIKES = str.maketrans(
    {
        "а": "a",
        "А": "A",
        "е": "e",
        "Е": "E",
        "о": "o",
        "О": "O",
        "р": "p",
        "Р": "P",
        "с": "c",
        "С": "C",
        "х": "x",
        "Х": "X",
        "у": "y",
        "У": "Y",
        "і": "i",
        "І": "I",
        "ѕ": "s",
        "Ѕ": "S",
        "ԁ": "d",
        "ј": "j",
        "һ": "h",
        "ѵ": "v",
        "Ѵ": "V",
        "ο": "o",
        "Ο": "O",
        "α": "a",
        "Α": "A",
        "ε": "e",
        "Ε": "E",
        "ρ": "p",
        "Ρ": "P",
        "ν": "v",
        "κ": "k",
        "Κ": "K",
        "τ": "t",
        "Τ": "T",
        "χ": "x",
        "Χ": "X",
        "ι": "i",
        "Ι": "I",
        "μ": "m",
    }
)

_DIGIT_SWAP = {"0": "o", "1": "l", "3": "e", "5": "s"}
_SPACED_LETTERS = re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z0-9]\s+){3,}[A-Za-z0-9]\b")
_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PLACE = "\x00HOLD{0}\x00"


def clean_for_matching(text: str | None) -> str:
    """Return text with disguises removed so phrase checks can see them.

    URLs and email addresses are left as written. Digit swaps run only when
    a letter sits on both sides of 0, 1, 3, or 5.
    """
    raw = _as_text(text)
    raw = unicodedata.normalize("NFKC", raw)
    raw = "".join(char for char in raw if char not in _INVISIBLE)
    raw, held = _hold_links(raw)
    raw = map_lookalikes(raw)
    raw = swap_digits_between_letters(raw)
    raw = _SPACED_LETTERS.sub(_join_spaced_letters, raw)
    raw = _put_links(raw, held)
    again = unicodedata.normalize("NFKC", raw)
    again = "".join(char for char in again if char not in _INVISIBLE)
    again, held2 = _hold_links(again)
    again = map_lookalikes(again)
    again = swap_digits_between_letters(again)
    again = _SPACED_LETTERS.sub(_join_spaced_letters, again)
    return _put_links(again, held2)


def map_lookalikes(text: str) -> str:
    """Map common Cyrillic and Greek lookalikes to Latin letters."""
    return text.translate(_LOOKALIKES)


def swap_digits_between_letters(text: str, extra: dict[str, str] | None = None) -> str:
    """Replace 0, 1, 3, and 5 only when they sit between two letters."""
    table = dict(_DIGIT_SWAP)
    if extra:
        table.update(extra)
    chars = list(text)
    for index, char in enumerate(chars):
        replacement = table.get(char)
        if replacement is None:
            continue
        previous = chars[index - 1] if index else ""
        nxt = chars[index + 1] if index + 1 < len(chars) else ""
        if previous.isalpha() and nxt.isalpha():
            chars[index] = replacement
    return "".join(chars)


def _as_text(text: str | None) -> str:
    if text is None:
        return ""
    if isinstance(text, str):
        return text
    return str(text)


def _hold_links(text: str) -> tuple[str, list[str]]:
    held: list[str] = []

    def stash(match: re.Match[str]) -> str:
        held.append(match.group(0))
        return _PLACE.format(len(held) - 1)

    text = _URL.sub(stash, text)
    text = _EMAIL.sub(stash, text)
    return text, held


def _put_links(text: str, held: list[str]) -> str:
    for index, value in enumerate(held):
        text = text.replace(_PLACE.format(index), value)
    return text


def _join_spaced_letters(match: re.Match[str]) -> str:
    pieces = match.group(0).split()
    if len(pieces) < 3 or any(len(piece) != 1 for piece in pieces):
        return match.group(0)
    return "".join(pieces)
