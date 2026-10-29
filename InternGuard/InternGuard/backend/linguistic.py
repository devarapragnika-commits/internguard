"""Named linguistic signals for a job or internship message.

Phrase and pattern checks only. This module does not call a language model.
"""

from __future__ import annotations

import re
from typing import TypedDict

LINGUISTIC_SIGNALS = (
    "urgency",
    "financial_pressure",
    "credential_request",
    "unrealistic_claims",
    "secrecy",
)

# Day and week rates at or above these amounts count as unrealistic pay.
# A normal stipend is usually quoted per month, so month and year are ignored.
_MIN_PAY = {
    "usd": {"day": 100, "week": 700},
    "inr": {"day": 3000, "week": 20000},
    "bare": {"day": 2000, "week": 10000},
}


class LinguisticFeature(TypedDict):
    value: int
    reason: str


_REASONS = {
    "urgency": "Uses urgency language: {shown}.",
    "financial_pressure": "Asks for a fee, deposit, or payment before joining: {shown}.",
    "credential_request": "Requests credentials or personal data: {shown}.",
    "unrealistic_claims": "Makes an unrealistic claim: {shown}.",
    "secrecy": "Asks to keep the offer secret: {shown}.",
}

# label None means "quote the text that matched".
_Rule = tuple[re.Pattern[str], str | None]

_RULES: dict[str, list[_Rule]] = {
    "urgency": [
        (re.compile(r"\bact now\b"), "act now"),
        (re.compile(r"\btoday only\b"), "today only"),
        (re.compile(r"\bimmediate joining\b"), "immediate joining"),
        (re.compile(r"\bimmediate joiner\b"), "immediate joiner"),
        (re.compile(r"\bjoin immediately\b"), "join immediately"),
        (re.compile(r"\bapply immediately\b"), "apply immediately"),
        (re.compile(r"\blimited time\b"), "limited time"),
        (re.compile(r"\blast chance\b"), "last chance"),
        (re.compile(r"\boffer expires\b"), "offer expires"),
        (re.compile(r"\bwithin 24 hours\b"), "within 24 hours"),
        (re.compile(r"\bwithin 48 hours\b"), "within 48 hours"),
        (re.compile(r"\bhurry\b"), "hurry"),
    ],
    "financial_pressure": [
        (re.compile(r"\bregistration fees?\b"), "registration fee"),
        (re.compile(r"\btraining fees?\b"), "training fee"),
        (re.compile(r"\bprocessing fees?\b"), "processing fee"),
        (re.compile(r"\bjoining fees?\b"), "joining fee"),
        (re.compile(r"\bapplication fees?\b"), "application fee"),
        (re.compile(r"\bsecurity deposits?\b"), "security deposit"),
        (re.compile(r"\brefundable deposits?\b"), "refundable deposit"),
        (re.compile(r"\b(?:upfront|advance) (?:fees?|payment|deposits?)\b"), None),
        (re.compile(r"\bpayment before joining\b"), "payment before joining"),
        (re.compile(r"\bpay(?:ment)? before joining\b"), "payment before joining"),
        (re.compile(r"\bpay (?:a |the )?(?:fees?|deposits?)\b"), None),
        (re.compile(r"\bfees?\b"), None),
        (re.compile(r"\bdeposits?\b"), None),
    ],
    "credential_request": [
        (re.compile(r"\bbank account(?: number| details)?\b"), "bank account"),
        (re.compile(r"\baccount number\b"), "account number"),
        (re.compile(r"\bifsc\b"), "IFSC code"),
        (re.compile(r"\bone[- ]time password\b"), "one-time password"),
        (re.compile(r"\botp\b"), "OTP"),
        (re.compile(r"\bpassword\b"), "password"),
        (re.compile(r"\baadhaar\b|\baadhar\b"), "Aadhaar"),
        (re.compile(r"\bpan (?:card|number)\b"), "PAN"),
        (re.compile(r"\bsocial security(?: number)?\b"), "social security number"),
        (re.compile(r"\bssn\b"), "SSN"),
        (re.compile(r"\bcvv\b"), "CVV"),
        (re.compile(r"\b(?:credit|debit) card\b"), None),
        (re.compile(r"\bupi (?:pin|id|number)\b"), None),
        (re.compile(r"\blogin (?:credentials|details|password)\b"), None),
        (re.compile(r"\bmother'?s maiden name\b"), "mother's maiden name"),
        (re.compile(r"\bkyc\b"), "KYC"),
    ],
    "unrealistic_claims": [
        (re.compile(r"\bguaranteed (?:selection|job|jobs|placement|offer|internship|income|salary)\b"), None),
        (re.compile(r"\b100 ?% (?:selection|guaranteed|placement)\b"), "100% selection"),
        (re.compile(r"\bno interview(?: required)?\b"), "no interview"),
        (re.compile(r"\bwithout (?:an |any )?interview\b"), "without an interview"),
        (re.compile(r"\bvery high (?:pay|salary|stipend|income)\b"), None),
    ],
    "secrecy": [
        (re.compile(r"\bdo not tell anyone\b"), "do not tell anyone"),
        (re.compile(r"\bdon'?t tell anyone\b"), "don't tell anyone"),
        (re.compile(r"\bkeep this private\b"), "keep this private"),
        (re.compile(r"\bkeep it private\b"), "keep it private"),
        (re.compile(r"\bkeep this (?:a )?secret\b"), "keep this secret"),
        (re.compile(r"\bdo not share this\b"), "do not share this"),
        (re.compile(r"\bdon'?t share this\b"), "don't share this"),
        (re.compile(r"\btell no one\b"), "tell no one"),
        (re.compile(r"\bbetween us only\b"), "between us only"),
    ],
}

_NEGATION_BEFORE = re.compile(
    r"\b(?:no|not|without|never|zero)\b(?:\s+\w+){0,3}\s*$"
)

_HIGH_PAY_WITH_CURRENCY = re.compile(
    r"(?P<cur>\$|₹|\busd\b|\brs\.?|\binr\b)\s*"
    r"(?P<amount>\d[\d,]*(?:\.\d+)?)"
    r"(?:\s*(?P<mult>k|lakh|lakhs))?"
    r"(?:\s*(?:per|a)\s+|\s*/\s*)"
    r"(?P<period>day|week)\b"
)

_HIGH_PAY_BARE = re.compile(
    r"\b(?P<amount>\d[\d,]*(?:\.\d+)?)"
    r"(?:\s*(?P<mult>k|lakh|lakhs))?"
    r"(?:\s*(?:per|a)\s+|\s*/\s*)"
    r"(?P<period>day|week)\b"
)


def extract_linguistic_features(text: str | None) -> dict[str, LinguisticFeature]:
    """Return urgency, financial pressure, credential requests, unrealistic claims, and secrecy.

    ``value`` is 1 when that signal fired and 0 when it did not. ``reason`` is a
    short sentence for the UI, or an empty string when the value is 0. Every
    signal is always present, including when none of them fire.
    """
    prepared = _prepare(_as_text(text))
    features: dict[str, LinguisticFeature] = {}
    for name in LINGUISTIC_SIGNALS:
        spans = _rule_spans(prepared, _RULES[name])
        if name == "unrealistic_claims":
            spans.extend(_high_pay_spans(prepared))
        quotes = _unique_quotes(spans)
        features[name] = {
            "value": 1 if quotes else 0,
            "reason": _reason(name, quotes),
        }
    return features


def _as_text(text: str | None) -> str:
    if text is None:
        return ""
    if isinstance(text, str):
        return text
    return str(text)


def _prepare(text: str) -> str:
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.lower()
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    text = re.sub(r"[^a-z0-9$%₹'./]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 48) : start]
    return _NEGATION_BEFORE.search(prefix) is not None


def _rule_spans(text: str, rules: list[_Rule]) -> list[tuple[int, int, str]]:
    if not text:
        return []
    spans: list[tuple[int, int, str]] = []
    for pattern, label in rules:
        for match in pattern.finditer(text):
            if _negated(text, match.start()):
                continue
            quote = label or " ".join(match.group(0).split())
            spans.append((match.start(), match.end(), quote))
    return spans


def _unique_quotes(spans: list[tuple[int, int, str]]) -> list[str]:
    visible: list[tuple[int, str]] = []
    for start, end, quote in spans:
        covered = any(
            other_start <= start
            and other_end >= end
            and (other_end - other_start) > (end - start)
            for other_start, other_end, _other_quote in spans
        )
        if not covered:
            visible.append((start, quote))
    visible.sort(key=lambda item: (item[0], item[1]))
    quotes: list[str] = []
    for _start, quote in visible:
        if quote not in quotes:
            quotes.append(quote)
    return quotes


def _high_pay_spans(text: str) -> list[tuple[int, int, str]]:
    if not text:
        return []
    spans: list[tuple[int, int, str]] = []
    for pattern in (_HIGH_PAY_WITH_CURRENCY, _HIGH_PAY_BARE):
        for match in pattern.finditer(text):
            if _negated(text, match.start()):
                continue
            if not _amount_is_high(match):
                continue
            quote = " ".join(match.group(0).split())
            spans.append((match.start(), match.end(), quote))
    return spans


def _amount_is_high(match: re.Match[str]) -> bool:
    amount = float(match.group("amount").replace(",", ""))
    unit = (match.group("mult") or "").lower()
    if unit == "k":
        amount *= 1000
    elif unit in {"lakh", "lakhs"}:
        return True
    kind = _currency_kind(match.groupdict().get("cur"))
    period = match.group("period")
    return amount >= _MIN_PAY[kind][period]


def _currency_kind(currency: str | None) -> str:
    if not currency:
        return "bare"
    token = currency.lower().strip(".")
    if token in {"$", "usd"}:
        return "usd"
    return "inr"


def _reason(name: str, quotes: list[str]) -> str:
    if not quotes:
        return ""
    shown = ", ".join(f'"{quote}"' for quote in quotes[:3])
    return _REASONS[name].format(shown=shown)
