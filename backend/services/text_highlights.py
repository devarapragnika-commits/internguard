"""Mark phrases in pasted source that produced score_message reasons.

Screenshot OCR uses the same phrase list for word boxes. This module maps
those phrases to character spans in the original text or email.
"""

from __future__ import annotations

import re
from typing import TypedDict

_QUOTED = re.compile(r'"([^"]+)"')
_ASKS_FOR = re.compile(r"\bAsks for (?:a|an) (.+)\.$")
_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_URL_FLAGS = {
    "claimed_company_mismatch",
    "lookalike_domain",
    "suspicious_tld",
    "insecure_link",
    "extra_subdomains",
    "new_domain",
    "long_redirect",
    "virustotal",
}


class TextHighlight(TypedDict):
    start: int
    end: int
    phrase: str
    reason: str


def fired_phrases(result: dict, source: str) -> list[str]:
    """Return unique phrases taken from the scorer reasons and flagged URLs."""
    found: list[str] = []
    for phrase, _reason in _phrase_reasons(result, source):
        if phrase not in found:
            found.append(phrase)
    return found


def source_highlights(source: str, result: dict) -> list[TextHighlight]:
    """Return non-overlapping spans in ``source`` for fired phrases.

    Empty flags or an unpaid message with no reasons yield an empty list.
    """
    text = source or ""
    if not text or not (result.get("reasons") or result.get("flags")):
        return []
    spans: list[TextHighlight] = []
    occupied = [False] * len(text)
    for phrase, reason in _phrase_reasons(result, text):
        for start, end in _find_phrase(text, phrase):
            if any(occupied[start:end]):
                continue
            for index in range(start, end):
                occupied[index] = True
            spans.append(
                {
                    "start": start,
                    "end": end,
                    "phrase": text[start:end],
                    "reason": reason,
                }
            )
    spans.sort(key=lambda item: (item["start"], item["end"]))
    return spans


def with_text_highlights(source: str, result: dict) -> dict:
    scored = dict(result)
    scored["text_highlights"] = source_highlights(source, scored)
    return scored


def _phrase_reasons(result: dict, source: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    reasons = [str(item) for item in (result.get("reasons") or []) if item]
    for reason in reasons:
        for quote in _QUOTED.findall(reason):
            compact = " ".join(quote.split())
            if compact:
                items.append((compact, reason))
        asked = _ASKS_FOR.search(reason)
        if asked:
            compact = " ".join(asked.group(1).split())
            if compact:
                items.append((compact, reason))
    if _URL_FLAGS.intersection(result.get("flags") or []):
        url_reason = next(
            (
                reason
                for reason in reasons
                if any(
                    token in reason.lower()
                    for token in ("link", "domain", "lookalike", "url")
                )
            ),
            reasons[0] if reasons else "",
        )
        for match in _URL.finditer(source or ""):
            url = match.group(0).rstrip(".,);]")
            if url:
                items.append((url, url_reason))
    unique: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for phrase, reason in items:
        key = (phrase.lower(), reason)
        if key in seen:
            continue
        seen.add(key)
        unique.append((phrase, reason))
    return unique


def _find_phrase(source: str, phrase: str) -> list[tuple[int, int]]:
    needle = " ".join((phrase or "").split())
    if not needle:
        return []
    pattern = re.compile(re.escape(needle), re.IGNORECASE)
    return [(match.start(), match.end()) for match in pattern.finditer(source)]
