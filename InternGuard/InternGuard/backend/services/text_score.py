"""Explainable text risk score for a pasted job or internship message.

Later channels add URL, sender, attachment, and company points in this module.
Those slices are zero until then, and they are not part of the text denominator.
"""

from __future__ import annotations

from backend.linguistic import extract_linguistic_features

LINGUISTIC_SIGNALS = (
    "urgency",
    "credential_request",
    "unrealistic_claims",
    "secrecy",
)
LINGUISTIC_POINTS_PER_SIGNAL = 5
LINGUISTIC_CAP = 25
FINANCIAL_POINTS = 25
FINANCIAL_CAP = 25
URL_CAP = 20
SENDER_CAP = 15
ATTACHMENT_CAP = 10
COMPANY_CAP = 15

# Text-only phase. Add a slice cap here when that channel starts awarding points.
TEXT_DENOMINATOR = LINGUISTIC_CAP + FINANCIAL_CAP


def score_text(text: str) -> dict[str, object]:
    features = extract_linguistic_features(text)
    linguistic = min(
        LINGUISTIC_CAP,
        sum(LINGUISTIC_POINTS_PER_SIGNAL for name in LINGUISTIC_SIGNALS if features[name]["value"]),
    )
    financial = FINANCIAL_POINTS if features["financial_pressure"]["value"] else 0
    slices = {
        "linguistic": linguistic,
        "financial": financial,
        "url": 0,
        "sender": 0,
        "attachment": 0,
        "company": 0,
    }
    raw = linguistic + financial
    score = round(raw / TEXT_DENOMINATOR * 100)
    reasons = [
        features[name]["reason"]
        for name in ("financial_pressure", *LINGUISTIC_SIGNALS)
        if features[name]["value"] and features[name]["reason"]
    ]
    return {
        "score": score,
        "band": _band(score),
        "reasons": reasons,
        "recommendation": _recommendation(score, financial > 0),
        "slices": slices,
    }


def _band(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _recommendation(score: int, asks_for_payment: bool) -> str:
    if asks_for_payment or score >= 70:
        return "Do not pay or share personal details. Verify the sender through the official company channel."
    if score >= 40:
        return "Verify the sender through the official company channel before you continue."
    return "No strong scam signals were found. Still verify the offer through the official company channel."
