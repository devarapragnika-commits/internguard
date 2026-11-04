"""Read an offer-letter PDF and score it with the same rubric as pasted text.

Text and http(s) link URIs are taken from the file on the server. JavaScript
in the PDF is not executed. Remote images are not fetched. The extracted
text is passed to ``score_message``.
"""

from __future__ import annotations

import io
import re
from typing import Iterable

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from backend.services.risk import score_message

MAX_PDF_BYTES = 5_000_000
MAX_PAGES = 8
EXCERPT_LENGTH = 240

_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


class PdfError(Exception):
    """The PDF could not be scored. The message is safe to show in the UI."""


def score_pdf(data: bytes) -> dict:
    """Return the combined risk score for one PDF.

    The result has the same score fields as ``score_message``, plus a short
    excerpt of the extracted text. An unreadable file raises ``PdfError``.
    """
    if not data:
        raise PdfError("Choose a PDF before analyzing.")
    if not _looks_like_pdf(data):
        raise PdfError("Upload a PDF file.")
    if len(data) > MAX_PDF_BYTES:
        raise PdfError("That PDF is too large.")
    try:
        text, links = extract_pdf_content(data)
    except PdfError:
        raise
    except Exception as exc:
        raise PdfError("Could not read text from this PDF.") from exc
    combined = _combine(text, links)
    if not combined:
        raise PdfError("No text was found in this PDF.")
    scored = dict(score_message(combined))
    scored["text"] = _excerpt(text or combined)
    return scored


def extract_pdf_content(data: bytes) -> tuple[str, list[str]]:
    """Return visible text and URI links without running PDF JavaScript."""
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
    except PdfReadError as exc:
        raise PdfError("Could not read text from this PDF.") from exc
    pages = list(reader.pages)[:MAX_PAGES]
    chunks: list[str] = []
    links: list[str] = []
    for page in pages:
        extracted = page.extract_text() or ""
        if extracted.strip():
            chunks.append(extracted)
        links.extend(_page_uris(page))
        links.extend(_URL.findall(extracted))
    return "\n".join(chunks).strip(), _unique(links)


def _looks_like_pdf(data: bytes) -> bool:
    head = data.lstrip()[:8]
    return head.startswith(b"%PDF-")


def _page_uris(page) -> list[str]:
    found: list[str] = []
    annots = page.get("/Annots")
    if annots is None:
        return found
    try:
        items = list(annots)
    except TypeError:
        return found
    for annot in items:
        try:
            obj = annot.get_object()
        except Exception:
            continue
        action = obj.get("/A") if obj else None
        if action is None:
            continue
        try:
            action = action.get_object()
        except Exception:
            pass
        if not action or action.get("/S") != "/URI":
            continue
        uri = action.get("/URI")
        if uri:
            found.append(str(uri))
    return found


def _combine(text: str, links: Iterable[str]) -> str:
    parts = [text.strip()] if text.strip() else []
    for link in links:
        if link and link not in (text or ""):
            parts.append(link)
    return "\n".join(parts).strip()


def _unique(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return seen


def _excerpt(text: str) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) <= EXCERPT_LENGTH:
        return flat
    return f"{flat[: EXCERPT_LENGTH - 1]}…"
