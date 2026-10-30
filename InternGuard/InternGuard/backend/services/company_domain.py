"""Compare a claimed company name with a link or sender domain.

String comparison only. This module does not use a verified-company list.

The claimed organization is the first name found by these rules, in order:

1. The words after "at", "join", "from", or "with".
2. The words immediately before "internship", "internships", "careers",
   "hiring", "jobs", "job", or "offer".

Up to four words are kept. Generic words on either end are removed.

False friends that are ignored, so they never create a mismatch:

- Names shorter than 4 letters after normalization, such as hp, ey, ge, ai,
  hr, it, and ibm. Short strings fuzzy-match unrelated domains.
- Generic words such as company, team, careers, hiring, internship, jobs,
  offer, software, engineering, student, college, and university.

The name is compared with the registrable domain label (microsoft.com becomes
microsoft) using difflib.SequenceMatcher. Spaces, punctuation, and legal
suffixes (inc, ltd, llc, limited, pvt, corp) are removed first. A score of at
least 0.92, or an equal normalized string, is a match and is not flagged.
A lower score is a mismatch.

Abbreviations are not expanded here. "Tata Consultancy Services" does not
match tcs.com in this module. The verified company list does that check.

The link is the url argument when one is passed, otherwise the first http(s)
URL in the text. When there is no URL, the sender address is used.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import TypedDict
from urllib.parse import urlparse

import tldextract

_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=())
_MATCH_RATIO = 0.92
_MIN_NAME_LENGTH = 4

_FALSE_FRIENDS = {
    "internship",
    "internships",
    "intern",
    "interns",
    "company",
    "companies",
    "team",
    "teams",
    "hiring",
    "careers",
    "career",
    "jobs",
    "job",
    "offer",
    "offers",
    "hr",
    "recruitment",
    "recruiter",
    "limited",
    "private",
    "pvt",
    "ltd",
    "llc",
    "inc",
    "corp",
    "corporation",
    "the",
    "and",
    "for",
    "from",
    "with",
    "your",
    "our",
    "this",
    "that",
    "please",
    "apply",
    "welcome",
    "congratulations",
    "selected",
    "opportunity",
    "position",
    "role",
    "student",
    "college",
    "university",
    "india",
    "online",
    "work",
    "home",
    "remote",
    "urgent",
    "immediate",
    "joining",
    "join",
    "official",
    "global",
    "international",
    "software",
    "engineering",
    "developer",
    "developers",
    "data",
    "science",
    "analyst",
    "manager",
    "summer",
    "program",
    "paid",
    "unpaid",
    "today",
    "now",
    "only",
    "here",
    "there",
    "http",
    "https",
    "www",
    "url",
    "link",
    "details",
}

_LEGAL_SUFFIXES = {"inc", "ltd", "llc", "limited", "pvt", "private", "corp", "corporation", "co"}

_NAME = r"[A-Za-z0-9][A-Za-z0-9&'.-]*(?:\s+[A-Za-z0-9][A-Za-z0-9&'.-]*){0,3}"
_AFTER_PREPOSITION = re.compile(rf"\b(?:at|join|from|with)\s+({_NAME})", re.IGNORECASE)
_BEFORE_ROLE = re.compile(
    rf"\b({_NAME})\s+(?:internships?|careers|hiring|jobs|job|offers?)\b",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_EMAIL = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")


class CompanyDomainResult(TypedDict):
    flagged: bool
    flag: str
    reason: str
    claimed_company: str
    domain: str
    source: str


def registrable_domain(value: str | None) -> str:
    """Return the registrable domain, such as careers.tcs.com to tcs.com."""
    return _registrable_domain(_as_text(value).strip())


def compare_claimed_company(
    text: str | None,
    url: str | None = None,
    sender: str | None = None,
) -> CompanyDomainResult:
    """Return a mismatch flag for a claimed company and a link or sender domain.

    ``flagged`` is false when the names match, when the text names no company,
    or when there is no domain to compare. No company name does not raise.
    """
    raw = _as_text(text)
    company = _extract_company(raw)
    domain, source = _comparison_domain(raw, url, sender)
    if not company or not domain:
        return _clean(company, domain, source)
    label = _domain_label(domain)
    if _matches(company, label):
        return _clean(company, domain, source)
    if source == "sender":
        reason = "claimed company does not match sender domain."
    else:
        reason = "claimed company does not match link domain."
    return {
        "flagged": True,
        "flag": "claimed_company_mismatch",
        "reason": reason,
        "claimed_company": company,
        "domain": domain,
        "source": source,
    }


def _as_text(text: str | None) -> str:
    if text is None:
        return ""
    if isinstance(text, str):
        return text
    return str(text)


def _clean(company: str, domain: str, source: str) -> CompanyDomainResult:
    return {
        "flagged": False,
        "flag": "",
        "reason": "",
        "claimed_company": company,
        "domain": domain,
        "source": source if company and domain else "",
    }


def _extract_company(text: str) -> str:
    if not text.strip():
        return ""
    for pattern in (_AFTER_PREPOSITION, _BEFORE_ROLE):
        for match in pattern.finditer(text):
            company = _trim_name(match.group(1))
            if company and len(_normalize(company)) >= _MIN_NAME_LENGTH:
                return company
    return ""


def _trim_name(phrase: str) -> str:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9&'.-]*", phrase)
    while words and _is_false_friend(words[0]):
        words.pop(0)
    while words and _is_false_friend(words[-1]):
        words.pop()
    return " ".join(words)


def _is_false_friend(word: str) -> bool:
    normalized = _normalize(word)
    return len(normalized) < _MIN_NAME_LENGTH or normalized in _FALSE_FRIENDS


def _normalize(value: str) -> str:
    parts = re.findall(r"[a-z0-9]+", value.lower())
    kept = [part for part in parts if part not in _LEGAL_SUFFIXES]
    return "".join(kept)


def _matches(company: str, label: str) -> bool:
    left = _normalize(company)
    right = _normalize(label)
    if len(left) < _MIN_NAME_LENGTH or len(right) < _MIN_NAME_LENGTH:
        return False
    if left == right:
        return True
    return SequenceMatcher(None, left, right).ratio() >= _MATCH_RATIO


def _comparison_domain(text: str, url: str | None, sender: str | None) -> tuple[str, str]:
    for candidate in (_as_text(url).strip(), _first_url(text)):
        domain = _registrable_domain(candidate)
        if domain:
            return domain, "url"
    domain = _sender_domain(_as_text(sender))
    if domain:
        return domain, "sender"
    return "", ""


def _first_url(text: str) -> str:
    match = _URL.search(text)
    if not match:
        return ""
    return match.group(0).rstrip(".,);]")


def _sender_domain(sender: str) -> str:
    if not sender.strip():
        return ""
    email = _EMAIL.search(sender)
    host = email.group(2) if email else sender.strip()
    return _registrable_domain(host)


def _registrable_domain(value: str) -> str:
    if not value:
        return ""
    host = value.strip()
    parsed = urlparse(host if "://" in host else f"//{host}")
    hostname = parsed.hostname or ""
    if not hostname:
        return ""
    extracted = _EXTRACTOR(hostname)
    registered = extracted.top_domain_under_public_suffix or ""
    try:
        return registered.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError:
        return ""


def _domain_label(domain: str) -> str:
    extracted = _EXTRACTOR(domain)
    return extracted.domain or ""
