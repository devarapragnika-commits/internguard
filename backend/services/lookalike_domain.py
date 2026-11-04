"""Flag a link whose host only matches a company after lookalike mapping."""

from __future__ import annotations

import re
import unicodedata
from typing import TypedDict
from urllib.parse import urlparse

from backend.services.company_domain import compare_claimed_company, registrable_domain
from backend.services.company_list import load_verified_companies
from backend.services.text_cleanup import clean_for_matching, map_lookalikes

LOOKALIKE_FLAG = "lookalike_domain"
LOOKALIKE_REASON = "Link domain uses lookalike characters."
LOOKALIKE_POINTS = 6

_SCRIPTS = {"LATIN", "CYRILLIC", "GREEK"}


class LookalikeResult(TypedDict):
    flagged: bool
    flag: str
    reason: str
    domain: str


def detect_lookalike_domain(text: str | None, url: str | None = None) -> LookalikeResult:
    """Return a URL-slice flag when the host is a lookalike of a named company.

    Punycode ``xn--`` labels are decoded first. A mixed-script label is not
    enough on its own. The host is flagged only if it matches a claimed or
    listed company after lookalike letters are mapped, and not before.
    """
    empty: LookalikeResult = {"flagged": False, "flag": "", "reason": "", "domain": ""}
    host = _hostname(url)
    if not host:
        return empty
    decoded = _decode_host(host)
    mapped = map_lookalikes(decoded)
    domain = registrable_domain(decoded) or registrable_domain(mapped)
    names = _company_names(text)
    if not names:
        return empty
    if _name_matches(decoded, names, map_letters=False):
        return empty
    if _name_matches(mapped, names, map_letters=False) or (
        _mixes_scripts(decoded) and _name_matches(mapped, names, map_letters=True)
    ):
        return {
            "flagged": True,
            "flag": LOOKALIKE_FLAG,
            "reason": LOOKALIKE_REASON,
            "domain": domain,
        }
    return empty


def _company_names(text: str | None) -> list[str]:
    cleaned = clean_for_matching(text)
    names: list[str] = []
    claimed = compare_claimed_company(cleaned).get("claimed_company") or ""
    if claimed:
        names.append(claimed)
    wording = cleaned.lower()
    for row in load_verified_companies():
        needles = [row["company"], *row["aliases"]]
        for needle in needles:
            if needle and _contains(wording, needle.lower()):
                names.extend(needles)
                break
    unique: list[str] = []
    for name in names:
        if name and name not in unique:
            unique.append(name)
    return unique


def _contains(text: str, needle: str) -> bool:
    return re.search(rf"\b{re.escape(needle)}\b", text, re.IGNORECASE) is not None


def _name_matches(host: str, names: list[str], *, map_letters: bool) -> bool:
    compact_host = _compact(host, map_letters=map_letters)
    labels = [_compact(part, map_letters=map_letters) for part in host.split(".") if part]
    for name in names:
        compact_name = _compact(name, map_letters=True)
        if len(compact_name) < 4:
            continue
        if compact_name and compact_name in compact_host:
            return True
        if compact_name in labels:
            return True
    return False


def _compact(value: str, *, map_letters: bool) -> str:
    text = map_lookalikes(value) if map_letters else value
    return "".join(char.lower() for char in text if char.isalnum())


def _hostname(url: str | None) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"//{raw}")
    return (parsed.hostname or "").rstrip(".").lower()


def _decode_host(host: str) -> str:
    try:
        return host.encode("ascii").decode("idna")
    except (UnicodeError, UnicodeDecodeError):
        return host


def _mixes_scripts(host: str) -> bool:
    seen: set[str] = set()
    for char in host:
        if not char.isalpha():
            continue
        try:
            script = unicodedata.name(char).split()[0]
        except ValueError:
            continue
        if script in _SCRIPTS:
            seen.add(script)
        if len(seen) > 1:
            return True
    return False
