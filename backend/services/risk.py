"""One 0–100 risk score for a pasted message and the links inside it.

The roadmap slices and caps are:

- Linguistic / text risk: 4 points for each fired signal, at most 20, cap 25
- Financial request risk: 25 when the payment detector flags, cap 25
- URL / domain risk: the signals below, cap 20
- Sender authenticity: SPF, DKIM, DMARC, free-mail company display names, and Reply-To mismatch, cap 15
- Attachment risk: dangerous and double extensions, macro Office files, and type mismatch, cap 10
- Company verification: 5 when a listed company's domain is not on its list, cap 15

Claimed-company mismatch stays in the URL slice. When the verified list
confirms the domain, that fuzzy mismatch is not added.

The raw points are divided by 110, the sum of the caps, then multiplied by
100. Bands are low (0–19), medium (20–49), and high (50–100).

A message with no link leaves URL risk at 0. A failed or unknown URL lookup
does not drop the text score. That result adds the reason "URL check was
unavailable." Unknown domain age, redirects, and VirusTotal are not scored
as risky. VirusTotal left off because no key is set is not a failure.
"""

from __future__ import annotations

import re
from typing import TypedDict

from backend.linguistic import LINGUISTIC_SIGNALS, extract_linguistic_features
from backend.services.company_domain import compare_claimed_company
from backend.services.company_list import check_verified_company
from backend.services.lookalike_domain import LOOKALIKE_POINTS, detect_lookalike_domain
from backend.services.mail import SliceFlags
from backend.services.payment import detect_payment_request
from backend.services.text_cleanup import clean_for_matching
from backend.services.url_features import extract_url_features

TOTAL_CAP = 110
LINGUISTIC_POINT = 4
LINGUISTIC_MAX = 20
LINGUISTIC_CAP = 25
FINANCIAL_CAP = 25
URL_CAP = 20
SENDER_CAP = 15
ATTACHMENT_CAP = 10
COMPANY_VERIFICATION_CAP = 15

NEW_DOMAIN_DAYS = 90
LONG_REDIRECT_LENGTH = 2
EXTRA_SUBDOMAIN_COUNT = 2
MAX_URLS = 5
URL_TIMEOUT = 5.0

MEDIUM_AT = 20
HIGH_AT = 50

_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_UNAVAILABLE = "URL check was unavailable."
_PAY = "Do not pay. Verify the sender through the official company channel."
_PAY_AND_ATTACH = (
    "Do not pay. Do not open attachments. "
    "Verify the sender through the official company channel."
)
_ATTACH = "Do not open attachments. Verify the sender through the official company channel."
_VERIFY = "Verify the sender through the official company channel."
_PROCEED = "Proceed with normal caution."


class SliceScore(TypedDict):
    points: int
    cap: int


class RiskScore(TypedDict):
    score: int
    band: str
    reasons: list[str]
    flags: list[str]
    recommendation: str
    slices: dict[str, SliceScore]


def score_message(
    text: str | None,
    *,
    sender: SliceFlags | None = None,
    attachments: SliceFlags | None = None,
    sender_address: str | None = None,
) -> RiskScore:
    """Return one score, one band, and one list of reasons.

    ``score`` is 0–100. ``slices`` keeps the capped points before that
    normalization. Empty text returns a zero score and does not raise.
    Pasted text leaves sender and attachment points at 0. Email analysis
    passes those slices in.
    """
    raw = _as_text(text)
    matching = clean_for_matching(raw)
    linguistic_points, linguistic_reasons, linguistic_flags = _linguistic(matching)
    payment = detect_payment_request(matching)
    financial_points = payment["financial_request_risk"]
    url_points, url_reasons, url_flags = _url_risk(raw, matching)
    sender_slice = sender or _empty_slice()
    attachment_slice = attachments or _empty_slice()
    sender_points = min(sender_slice["points"], SENDER_CAP)
    attachment_points = min(attachment_slice["points"], ATTACHMENT_CAP)

    reasons = list(linguistic_reasons)
    flags = list(linguistic_flags)
    if payment["flagged"]:
        reasons.append(payment["reason"])
        flags.append(payment["flag"])
    reasons.extend(url_reasons)
    flags.extend(url_flags)
    verified = check_verified_company(matching, sender=sender_address)
    company_points = min(verified["points"], COMPANY_VERIFICATION_CAP)
    if verified["reason"]:
        reasons.append(verified["reason"])
        flags.append(verified["flag"])
    reasons.extend(sender_slice["reasons"])
    flags.extend(sender_slice["flags"])
    reasons.extend(attachment_slice["reasons"])
    flags.extend(attachment_slice["flags"])

    raw_points = (
        linguistic_points
        + financial_points
        + url_points
        + sender_points
        + attachment_points
        + company_points
    )
    score = _normalize(raw_points)
    return {
        "score": score,
        "band": _band(score),
        "reasons": reasons,
        "flags": flags,
        "recommendation": _recommendation(financial_points, attachment_points, flags),
        "slices": {
            "linguistic": {"points": linguistic_points, "cap": LINGUISTIC_CAP},
            "financial_request": {"points": financial_points, "cap": FINANCIAL_CAP},
            "url_domain": {"points": url_points, "cap": URL_CAP},
            "sender_authenticity": {"points": sender_points, "cap": SENDER_CAP},
            "attachment": {"points": attachment_points, "cap": ATTACHMENT_CAP},
            "company_verification": {"points": company_points, "cap": COMPANY_VERIFICATION_CAP},
        },
    }


def _as_text(text: str | None) -> str:
    if text is None:
        return ""
    if isinstance(text, str):
        return text
    return str(text)


def _linguistic(text: str) -> tuple[int, list[str], list[str]]:
    features = extract_linguistic_features(text)
    points = 0
    reasons: list[str] = []
    flags: list[str] = []
    for name in LINGUISTIC_SIGNALS:
        feature = features[name]
        if feature["value"] != 1:
            continue
        points += LINGUISTIC_POINT
        reasons.append(feature["reason"])
        flags.append(name)
    return min(points, LINGUISTIC_MAX), reasons, flags


def _url_risk(text: str, matching: str | None = None) -> tuple[int, list[str], list[str]]:
    urls = _extract_urls(text)
    wording = matching if matching is not None else text
    best_points = 0
    best_reasons: list[str] = []
    best_flags: list[str] = []
    unavailable = False
    for url in urls:
        points, reasons, flags, failed = _one_url(wording, url)
        if failed:
            unavailable = True
        if points > best_points:
            best_points = points
            best_reasons = reasons
            best_flags = flags
    if unavailable:
        best_reasons = [*best_reasons, _UNAVAILABLE]
        best_flags = [*best_flags, "url_check_unavailable"]
    return best_points, best_reasons, best_flags


def _one_url(text: str, url: str) -> tuple[int, list[str], list[str], bool]:
    failed = False
    try:
        features = extract_url_features(url, timeout=URL_TIMEOUT)
    except Exception:
        features = None
        failed = True
    try:
        company = compare_claimed_company(text, url=url)
    except Exception:
        company = None
        failed = True

    found: list[tuple[str, str]] = []
    verified = check_verified_company(text, url=url)
    lookalike = detect_lookalike_domain(text, url=url)
    if lookalike["flagged"]:
        found.append((lookalike["flag"], lookalike["reason"]))
    elif company and company["flagged"] and not verified["domain_allowed"]:
        found.append((company["flag"], company["reason"]))
    if features is None:
        points = min(_url_points(found), URL_CAP)
        return (
            points,
            [reason for _flag, reason in found],
            [flag for flag, _reason in found],
            True,
        )

    if features["suspicious_tld"]["value"]:
        found.append(("suspicious_tld", "Link uses a suspicious top-level domain."))
    if not features["https"]["value"]:
        found.append(("insecure_link", "Link does not use HTTPS."))
    if features["subdomain_count"]["value"] >= EXTRA_SUBDOMAIN_COUNT:
        found.append(("extra_subdomains", "Link has extra subdomains."))

    age = features["domain_age"]
    redirects = features["redirects"]
    virustotal = features["virustotal"]
    if age["status"] == "unknown" or redirects["status"] == "unknown":
        failed = True
    if age["status"] == "ok" and age["days"] is not None and age["days"] < NEW_DOMAIN_DAYS:
        found.append(("new_domain", "Link domain is newly registered."))
    if (
        redirects["status"] == "ok"
        and redirects["length"] is not None
        and redirects["length"] >= LONG_REDIRECT_LENGTH
    ):
        found.append(("long_redirect", "Link redirects more than once."))
    if virustotal["status"] == "unknown":
        failed = True
    malicious = virustotal["malicious"] or 0
    suspicious = virustotal["suspicious"] or 0
    if virustotal["status"] == "ok" and (malicious > 0 or suspicious > 0):
        found.append(("virustotal", "Link domain is flagged by VirusTotal."))

    points = min(_url_points(found), URL_CAP)
    return (
        points,
        [reason for _flag, reason in found],
        [flag for flag, _reason in found],
        failed,
    )


def _url_points(found: list[tuple[str, str]]) -> int:
    weights = {
        "claimed_company_mismatch": 6,
        "lookalike_domain": LOOKALIKE_POINTS,
        "suspicious_tld": 5,
        "new_domain": 4,
        "virustotal": 4,
        "extra_subdomains": 3,
        "long_redirect": 3,
        "insecure_link": 2,
    }
    return sum(weights[flag] for flag, _reason in found if flag in weights)


def _extract_urls(text: str) -> list[str]:
    found: list[str] = []
    for match in _URL.finditer(text):
        url = match.group(0).rstrip(".,);]")
        if url not in found:
            found.append(url)
        if len(found) == MAX_URLS:
            break
    return found


def _normalize(points: int) -> int:
    if points <= 0:
        return 0
    score = int((points * 100) / TOTAL_CAP + 0.5)
    return min(score, 100)


def _band(score: int) -> str:
    if score >= HIGH_AT:
        return "high"
    if score >= MEDIUM_AT:
        return "medium"
    return "low"


def _empty_slice() -> SliceFlags:
    return {"points": 0, "reasons": [], "flags": [], "unavailable": False}


def _recommendation(financial_points: int, attachment_points: int, flags: list[str]) -> str:
    if financial_points > 0 and attachment_points > 0:
        return _PAY_AND_ATTACH
    if attachment_points > 0:
        return _ATTACH
    if financial_points > 0:
        return _PAY
    if flags:
        return _VERIFY
    return _PROCEED
