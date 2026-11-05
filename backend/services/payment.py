"""Payment and fee-request detector.

Phrase checks only. This module does not visit payment pages or call a bank.
It scores the financial-request slice of the rubric on its own: 25 points when
a payment demand is present, and 0 when it is not. The cap is 25.

A negated phrase such as "no registration fee" does not count.
"""

from __future__ import annotations

import re
from typing import TypedDict

from backend.services.text_cleanup import clean_for_matching

FINANCIAL_REQUEST_CAP = 25

_Rule = tuple[re.Pattern[str], str]

# Longer phrases are listed before the shorter ones they contain.
_RULES: list[_Rule] = [
    (re.compile(r"\bregistration fees?\b"), "registration fee"),
    (re.compile(r"\btraining fees?\b"), "training fee"),
    (re.compile(r"\bprocessing fees?\b"), "processing fee"),
    (re.compile(r"\bjoining fees?\b"), "joining fee"),
    (re.compile(r"\bapplication fees?\b"), "application fee"),
    (re.compile(r"\bcourse fees?\b"), "course fee"),
    (
        re.compile(
            r"\bpay(?:ment)?\b(?:\s+\w+){0,6}\s+to (?:receive|get|unlock) (?:the |your )?offer letter\b"
        ),
        "payment to receive the offer letter",
    ),
    (
        re.compile(
            r"\bpay(?:ment)?\b(?:\s+\w+){0,6}\s+(?:for|to get) (?:the |your )?offer letter\b"
        ),
        "payment to receive the offer letter",
    ),
    (
        re.compile(
            r"\bpay(?:ment)?\b(?:\s+\w+){0,8}\s+to (?:release|unlock|receive|get) (?:the |your )?laptop\b"
        ),
        "payment to release the laptop",
    ),
    (re.compile(r"\blaptop release fees?\b"), "payment to release the laptop"),
    (re.compile(r"\b(?:upfront|advance) (?:fees?|payments?|deposits?)\b"), "upfront deposit"),
    (re.compile(r"\bsecurity deposits?\b"), "security deposit"),
    (re.compile(r"\brefundable deposits?\b"), "refundable deposit"),
    (re.compile(r"\bdeposits? (?:required|to confirm|before joining)\b"), "upfront deposit"),
    (re.compile(r"\bpay (?:a |the )?(?:fees?|deposits?)\b"), "fee"),
    (re.compile(r"\bgift cards?\b"), "gift card"),
    (re.compile(r"\bgoogle play (?:gift )?cards?\b"), "gift card"),
    (re.compile(r"\bitunes (?:gift )?cards?\b"), "gift card"),
    (re.compile(r"\bbitcoin\b|\bbtc\b"), "bitcoin payment"),
    (re.compile(r"\bethereum\b|\beth\b"), "ethereum payment"),
    (re.compile(r"\busdt\b"), "USDT payment"),
    (re.compile(r"\bcrypto(?:currency)?\b"), "crypto payment"),
    (re.compile(r"\bfees?\s+(?:bhejo|bhejna|bharo|bharni|do|dena)\b"), "fee"),
    (re.compile(r"रजिस्ट्रेशन\s*फीस"), "registration fee"),
    (re.compile(r"पंजीकरण\s*शुल्क"), "registration fee"),
    (re.compile(r"ज्वाइनिंग\s*फीस"), "joining fee"),
    (re.compile(r"जॉइनिंग\s*फीस"), "joining fee"),
    (re.compile(r"ट्रेनिंग\s*फीस"), "training fee"),
    (re.compile(r"प्रोसेसिंग\s*फीस"), "processing fee"),
    (re.compile(r"आवेदन\s*शुल्क"), "application fee"),
    (re.compile(r"सुरक्षा\s*जमा"), "security deposit"),
    (re.compile(r"फीस"), "fee"),
    (re.compile(r"शुल्क"), "fee"),
]

_NEGATION_BEFORE = re.compile(
    r"(?:(?:\b(?:no|not|without|never|zero|nahi+|nahin|bina)\b)|नहीं|बिना)(?:\s+\w+){0,3}\s*$"
)
_NEGATION_AFTER = re.compile(r"^\s*(?:(?:nahi+|nahin)\b|नहीं)")


class PaymentResult(TypedDict):
    flagged: bool
    flag: str
    reason: str
    requests: list[str]
    financial_request_risk: int
    financial_request_cap: int


def detect_payment_request(text: str | None) -> PaymentResult:
    """Return the financial-request flag and its 25-point score.

    ``financial_request_risk`` is 25 when fee language is present and 0 when
    it is not. ``financial_request_cap`` is always 25.
    """
    prepared = _prepare(_as_text(text))
    requests = _matching_requests(prepared)
    if not requests:
        return {
            "flagged": False,
            "flag": "",
            "reason": "",
            "requests": [],
            "financial_request_risk": 0,
            "financial_request_cap": FINANCIAL_REQUEST_CAP,
        }
    return {
        "flagged": True,
        "flag": "financial_request",
        "reason": _reason(requests),
        "requests": requests,
        "financial_request_risk": FINANCIAL_REQUEST_CAP,
        "financial_request_cap": FINANCIAL_REQUEST_CAP,
    }


def _as_text(text: str | None) -> str:
    if text is None:
        return ""
    if isinstance(text, str):
        return text
    return str(text)


def _prepare(text: str) -> str:
    text = clean_for_matching(text)
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.lower()
    text = re.sub(r"[^a-z0-9$%₹'./\u0900-\u0963\u0966-\u097f]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _negated(text: str, start: int, end: int | None = None) -> bool:
    prefix = text[max(0, start - 48) : start]
    if _NEGATION_BEFORE.search(prefix):
        return True
    suffix = text[(end if end is not None else start) : (end if end is not None else start) + 32]
    return _NEGATION_AFTER.search(suffix) is not None


def _matching_requests(text: str) -> list[str]:
    if not text:
        return []
    spans: list[tuple[int, int, str]] = []
    for pattern, label in _RULES:
        for match in pattern.finditer(text):
            if _negated(text, match.start(), match.end()):
                continue
            spans.append((match.start(), match.end(), label))
    visible: list[tuple[int, str]] = []
    for start, end, label in spans:
        covered = any(
            other_start <= start
            and other_end >= end
            and (other_end - other_start) > (end - start)
            for other_start, other_end, _label in spans
        )
        if not covered:
            visible.append((start, label))
    visible.sort(key=lambda item: (item[0], item[1]))
    requests: list[str] = []
    for _start, label in visible:
        if label not in requests:
            requests.append(label)
    return requests


def _reason(requests: list[str]) -> str:
    phrases = [f"{_article(kind)} {kind}" for kind in requests[:3]]
    if len(phrases) == 1:
        return f"Asks for {phrases[0]}."
    if len(phrases) == 2:
        return f"Asks for {phrases[0]} and {phrases[1]}."
    return f"Asks for {', '.join(phrases)}."


def _article(kind: str) -> str:
    return "an" if kind[:1].lower() in "aeiou" else "a"
