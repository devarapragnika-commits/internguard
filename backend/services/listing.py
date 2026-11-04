"""Read visible job-listing or message text from a page the user already opened.

The listing is not stored. There is no login scrape and no job-board API call.
The extracted string is what ``POST /analyze/text`` sends to ``score_message``.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

MAX_LISTING_CHARS = 15_000
MIN_BLOCK_CHARS = 40

SCAM_LISTING_TITLE = "Microsoft internship — act now"
SCAM_LISTING_BODY = (
    "You are selected for a Microsoft internship.\n"
    "Kindly pay the registration fee to confirm your place.\n"
    "Apply at http://microsoft.secure-login.tk/offer"
)
LEGIT_LISTING_TITLE = "Software engineering intern"
LEGIT_LISTING_BODY = (
    "We are pleased to offer you an unpaid software internship.\n"
    "The stipend is Rs 15000 per month."
)

_SPACE = re.compile(r"\s+")
_SKIP = {"script", "style", "noscript", "svg"}
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
_IDS = {
    "job-details": "job-details",
    "jobDescriptionText": "jobDescriptionText",
}
_CLASSES = {
    "jobs-description__content": "jobs-description__content",
    "jobs-box__html-content": "jobs-box__html-content",
    "jobsearch-JobComponent-description": "jobsearch-JobComponent-description",
    "jobsearch-jobDescriptionText": "jobDescriptionText",
    "msg-s-event-listitem__body": "message",
    "msg-s-event-listitem__message-bubble": "message",
}
_PRIORITY = (
    "job-details",
    "jobs-description__content",
    "jobs-box__html-content",
    "jobDescriptionText",
    "jobsearch-JobComponent-description",
    "message",
    "main",
)


def extract_listing_text(html: str) -> str:
    """Return visible listing or message text from markup already on the page."""
    parser = _ListingParser()
    parser.feed(html or "")
    parser.close()
    return _clip(_merge_title(parser.title, parser.best_body()))


def listing_text_for_score(*, title: str, body: str) -> str:
    """Build the same string the extension POSTs to /analyze/text."""
    return _clip(_merge_title(title, body))


class _ListingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.blocks: dict[str, list[str]] = {key: [] for key in _PRIORITY}
        self._skip = 0
        self._title_depth = 0
        self._title_buf: list[str] = []
        self._captures: list[tuple[str, int, list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        found = {key: (value or "") for key, value in attrs}
        classes = (found.get("class") or "").split()
        if tag == "h1" and not self.title and self._title_depth == 0:
            self._title_depth = 1
            self._title_buf = []
        elif self._title_depth:
            self._title_depth += 1
        key = _block_key(tag, found, classes)
        if key:
            self._captures.append((key, 1, []))
        elif self._captures:
            name, depth, buf = self._captures[-1]
            self._captures[-1] = (name, depth + 1, buf)
        if tag in _VOID:
            self._leave()

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID:
            return
        if tag in _SKIP:
            if self._skip:
                self._skip -= 1
            return
        if self._skip:
            return
        self._leave()

    def _leave(self) -> None:
        if self._captures:
            key, depth, buf = self._captures[-1]
            if depth > 1:
                self._captures[-1] = (key, depth - 1, buf)
            else:
                self._finish_capture()
        if self._title_depth:
            self._title_depth -= 1
            if self._title_depth <= 0:
                self._finish_title()

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._captures:
            self._captures[-1][2].append(data)
        if self._title_depth:
            self._title_buf.append(data)

    def _finish_capture(self) -> None:
        if not self._captures:
            return
        key, _depth, buf = self._captures.pop()
        text = _clean_text("".join(buf))
        if text:
            self.blocks[key].append(text)

    def _finish_title(self) -> None:
        if not self.title:
            self.title = _clean_text("".join(self._title_buf))
        self._title_depth = 0
        self._title_buf = []

    def best_body(self) -> str:
        for key in _PRIORITY:
            parts = [part for part in self.blocks[key] if part]
            if not parts:
                continue
            if key == "message":
                text = "\n\n".join(parts)
            else:
                text = parts[0]
            if len(text) >= MIN_BLOCK_CHARS or key == "message" and text:
                return text
        return ""


def _block_key(tag: str, attrs: dict[str, str], classes: list[str]) -> str | None:
    ident = attrs.get("id") or ""
    if ident in _IDS:
        return _IDS[ident]
    for name in classes:
        if name in _CLASSES:
            return _CLASSES[name]
    if tag == "main" or attrs.get("role") == "main":
        return "main"
    return None


def _merge_title(title: str, body: str) -> str:
    heading = _clean_text(title)
    text = _clean_text(body)
    if heading and text:
        if text.lower().startswith(heading.lower()):
            return text
        return f"{heading}\n\n{text}"
    return text or heading


def _clean_text(text: str) -> str:
    lines = [_SPACE.sub(" ", line).strip() for line in (text or "").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _clip(text: str) -> str:
    return (text or "")[:MAX_LISTING_CHARS].strip()
