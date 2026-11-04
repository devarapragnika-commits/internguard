"""Score Gmail list rows from metadata already on the page.

Subject, sender, and snippet are enough. The full body is never fetched.
Remote images are not loaded. There is no Gmail API call and no send or
modify scope.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser

from backend.services.mail import score_email

MAX_LIST_MESSAGES = 50

_SNIPPET_PREFIX = re.compile(r"^[\s.\-–—]+")
_SPACE = re.compile(r"\s+")
_VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}

DEMO_LIST_MESSAGES = [
    {
        "from_name": "Microsoft Careers",
        "from_address": "offers@gmail.com",
        "subject": "Microsoft internship — act now",
        "snippet": (
            "Kindly pay the registration fee to confirm your place. "
            "Keep this secret. Guaranteed selection. Send your OTP. "
            "Apply at http://microsoft.secure-login.tk/offer"
        ),
    },
    {
        "from_name": "Hiring Desk",
        "from_address": "desk@campus-jobs.example",
        "subject": "Microsoft onboarding — apply immediately",
        "snippet": "Microsoft internship. Apply immediately at http://microsoft.secure-login.tk/offer",
    },
    {
        "from_name": "Recruiting",
        "from_address": "jobs@careers.microsoft.com",
        "subject": "Internship next steps",
        "snippet": (
            "We are pleased to offer you an unpaid software internship. "
            "The stipend is Rs 15000 per month."
        ),
    },
]


def score_list_metadata(
    *,
    from_name: str = "",
    from_address: str = "",
    subject: str = "",
    snippet: str = "",
) -> dict:
    """Return the combined score for one list row. No mailbox is opened."""
    headers = list_headers(from_name=from_name, from_address=from_address, subject=subject)
    return score_email(headers=headers, snippet=snippet or "")


def score_list_messages(messages: list[dict]) -> dict:
    """Score many list rows from metadata only."""
    items = list(messages[:MAX_LIST_MESSAGES])
    if not items:
        return {"messages": []}

    def one(index: int, item: dict) -> tuple[int, dict]:
        scored = score_list_metadata(
            from_name=item.get("from_name") or "",
            from_address=item.get("from_address") or "",
            subject=item.get("subject") or "",
            snippet=item.get("snippet") or "",
        )
        return index, {
            "from_name": (item.get("from_name") or "").strip(),
            "from_address": (item.get("from_address") or "").strip().lower(),
            "subject": (item.get("subject") or "").strip() or "(no subject)",
            "snippet": _clean_snippet(item.get("snippet") or ""),
            "score": scored["score"],
            "band": scored["band"],
            "reasons": scored["reasons"],
            "flags": scored["flags"],
            "recommendation": scored["recommendation"],
            "slices": scored["slices"],
        }

    rows: list[dict | None] = [None] * len(items)
    workers = min(8, len(items))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, index, item) for index, item in enumerate(items)]
        for future in as_completed(futures):
            index, row = future.result()
            rows[index] = row
    return {"messages": [row for row in rows if row is not None]}


def list_headers(*, from_name: str = "", from_address: str = "", subject: str = "") -> str:
    """Build RFC 822 headers from list-view fields. There is no body."""
    name = (from_name or "").replace("\n", " ").replace("\r", " ").strip()
    address = (from_address or "").replace("\n", " ").replace("\r", " ").strip()
    title = (subject or "").replace("\n", " ").replace("\r", " ").strip()
    if name and address:
        from_line = f'From: "{name}" <{address}>'
    elif address:
        from_line = f"From: {address}"
    elif name:
        from_line = f"From: {name}"
    else:
        from_line = "From: "
    return f"{from_line}\r\nSubject: {title}\r\n"


def parse_gmail_list_html(html: str) -> list[dict]:
    """Read subject, sender, and snippet from Gmail list markup. No network."""
    parser = _GmailListParser()
    parser.feed(html or "")
    parser.close()
    if parser._row is not None:
        parser._finish_row()
    return parser.rows


class _GmailListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict] = []
        self._row: dict | None = None
        self._depth = 0
        self._capture: str | None = None
        self._cap_depth = 0
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = {key: (value or "") for key, value in attrs}
        classes = set((found.get("class") or "").split())
        if self._row is None and _is_row(tag, found, classes):
            self._row = {
                "from_name": "",
                "from_address": "",
                "subject": "",
                "snippet": "",
            }
            self._depth = 1
        elif self._row is not None:
            self._depth += 1
        if self._row is None:
            return
        email = found.get("email") or found.get("data-hovercard-id") or ""
        if "@" in email and not self._row["from_address"]:
            self._row["from_address"] = email.strip()
        name = found.get("name") or found.get("data-name") or ""
        if name and not self._row["from_name"]:
            self._row["from_name"] = name.strip()
        if self._capture:
            self._cap_depth += 1
        elif "bqe" in classes or "bog" in classes:
            self._start_capture("subject")
        elif "y2" in classes:
            self._start_capture("snippet")
        elif ("yP" in classes or "zF" in classes) and not self._row["from_name"]:
            self._start_capture("from_name")
        if tag in _VOID:
            self._leave_tag()

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID:
            return
        self._leave_tag()

    def _leave_tag(self) -> None:
        if self._row is None:
            return
        if self._capture:
            self._cap_depth -= 1
            if self._cap_depth <= 0:
                text = _clean_snippet("".join(self._buf))
                if text and not self._row[self._capture]:
                    self._row[self._capture] = text
                self._capture = None
                self._cap_depth = 0
                self._buf = []
        self._depth -= 1
        if self._depth <= 0:
            self._finish_row()

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buf.append(data)

    def _start_capture(self, field: str) -> None:
        if not self._row or self._row[field]:
            return
        self._capture = field
        self._cap_depth = 1
        self._buf = []

    def _finish_row(self) -> None:
        row = self._row
        self._row = None
        self._depth = 0
        self._capture = None
        self._cap_depth = 0
        self._buf = []
        if row and (row["subject"] or row["snippet"] or row["from_address"] or row["from_name"]):
            self.rows.append(row)


def _is_row(tag: str, attrs: dict[str, str], classes: set[str]) -> bool:
    if tag in {"tr", "div"} and "zA" in classes:
        return True
    if tag in {"div", "tr"} and attrs.get("role") == "listitem":
        return True
    return False


def _clean_snippet(text: str) -> str:
    cleaned = (text or "").replace("\xa0", " ").replace("\u200b", "")
    cleaned = _SPACE.sub(" ", cleaned).strip()
    return _SNIPPET_PREFIX.sub("", cleaned).strip()
