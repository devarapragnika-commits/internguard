"""Compare a named employer with the verified domain list.

The list is backend/data/verified_companies.csv. Edit that file to add an
employer. This module does not call a company API.

A company on the list is compared with the link domain, or the sender domain
when the message has no link. A domain that is not on that company's list
adds company-verification points and a reason that says the company requires
verification. The reason does not call the offer a scam.

A domain on the list adds no points. A company that is not on the list is
not a list failure. The fuzzy name check still runs for that message.
A listed company with no link and no sender is not a list failure either.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import TypedDict

from backend.services.company_domain import compare_claimed_company, registrable_domain
from backend.services.text_cleanup import clean_for_matching

VERIFICATION_POINTS = 5
VERIFICATION_CAP = 15

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "verified_companies.csv"
_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_MAX_URLS = 5
_cache: dict[str, tuple[int, list["VerifiedCompany"]]] = {}


class VerifiedCompany(TypedDict):
    company: str
    aliases: list[str]
    domains: list[str]


class VerifiedCompanyCheck(TypedDict):
    listed: bool
    domain_allowed: bool
    points: int
    flag: str
    reason: str
    company: str
    domain: str


def load_verified_companies(path: Path | None = None) -> list[VerifiedCompany]:
    """Read the CSV. Extra aliases or domains in one cell are separated by semicolons."""
    file = _DEFAULT_PATH if path is None else Path(path)
    stamp = file.stat().st_mtime_ns
    key = str(file.resolve())
    cached = _cache.get(key)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    rows = _read_companies(file)
    _cache[key] = (stamp, rows)
    return rows


def check_verified_company(
    text: str | None,
    url: str | None = None,
    sender: str | None = None,
    path: Path | None = None,
) -> VerifiedCompanyCheck:
    """Return the company-verification result for one message.

    ``domain_allowed`` is true only when the named company is on the list and
    every compared domain is one of its domains. Callers use that to skip the
    fuzzy mismatch for an official domain such as tcs.com.
    """
    row = _matching_company(_wording(text), load_verified_companies(path))
    if row is None:
        return _result(False, False, 0, "", "", "")
    domains = _domains(text, url, sender)
    if not domains:
        return _result(True, False, 0, "", row["company"], "")
    blocked = [domain for domain in domains if domain not in row["domains"]]
    if blocked:
        return _result(
            True,
            False,
            min(VERIFICATION_POINTS, VERIFICATION_CAP),
            "company_requires_verification",
            row["company"],
            blocked[0],
        )
    return _result(True, True, 0, "", row["company"], domains[0])


def _read_companies(path: Path) -> list[VerifiedCompany]:
    companies: list[VerifiedCompany] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            company = (raw.get("company") or "").strip()
            if not company:
                continue
            aliases = _split(raw.get("aliases") or "")
            domains: list[str] = []
            for value in _split(raw.get("domains") or ""):
                domain = registrable_domain(value)
                if domain and domain not in domains:
                    domains.append(domain)
            if not domains:
                continue
            companies.append({"company": company, "aliases": aliases, "domains": domains})
    return companies


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def _matching_company(wording: str, companies: list[VerifiedCompany]) -> VerifiedCompany | None:
    best: tuple[int, VerifiedCompany] | None = None
    for company in companies:
        for needle in [company["company"], *company["aliases"]]:
            if not needle or not _contains(wording, needle):
                continue
            if best is None or len(needle) > best[0]:
                best = (len(needle), company)
    if best is None:
        return None
    return best[1]


def _contains(text: str, needle: str) -> bool:
    return re.search(rf"\b{re.escape(needle)}\b", text, re.IGNORECASE) is not None


def _wording(text: str | None) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    without_links = _URL.sub(" ", text)
    return clean_for_matching(_EMAIL.sub(" ", without_links))


def _domains(text: str | None, url: str | None, sender: str | None) -> list[str]:
    if url and str(url).strip():
        domain = compare_claimed_company(text, url=url)["domain"]
        return [domain] if domain else []
    found: list[str] = []
    raw = text if isinstance(text, str) else "" if text is None else str(text)
    for match in _URL.finditer(raw):
        link = match.group(0).rstrip(".,);]")
        domain = compare_claimed_company(raw, url=link)["domain"]
        if domain and domain not in found:
            found.append(domain)
        if len(found) == _MAX_URLS:
            break
    if found:
        return found
    domain = compare_claimed_company(text, sender=sender)["domain"]
    return [domain] if domain else []


def _result(
    listed: bool,
    domain_allowed: bool,
    points: int,
    flag: str,
    company: str,
    domain: str,
) -> VerifiedCompanyCheck:
    reason = f"{company} requires verification." if flag else ""
    return {
        "listed": listed,
        "domain_allowed": domain_allowed,
        "points": points,
        "flag": flag,
        "reason": reason,
        "company": company,
        "domain": domain,
    }
