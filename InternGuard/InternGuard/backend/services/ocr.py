"""Read a screenshot and score it with the same rubric as pasted text.

Tesseract runs on the server. This module does not call a language model.
The cleaned text is passed to ``score_message``.

Cleanup is local and conservative:

- A word split across a line break, such as ``regis-`` then ``tration``, is joined.
- A digit or bar sitting between letters is treated as the usual OCR swap
  (0 to o, 1 to l, 5 to s, | to l).
- Single letters with spaces between them are joined.
- Spaces inside an http(s) link are removed so the URL checks can see it.

Word boxes from Tesseract are kept so the page can mark the phrases that fired.
"""

from __future__ import annotations

import os
import re
import shutil
from io import BytesIO
from typing import TypedDict

from backend.services.risk import score_message

MAX_IMAGE_BYTES = 5_000_000

_CONFUSABLES = {"0": "o", "1": "l", "5": "s", "|": "l"}
_HYPHEN_BREAK = re.compile(r"([A-Za-z])-\s*[\r\n]+\s*([A-Za-z])")
_SPACED_LETTERS = re.compile(r"(?:[A-Za-z0-9|]\s+){3,}[A-Za-z0-9|]\b")
_URL_START = re.compile(r"https?\s*:\s*/\s*/", re.IGNORECASE)
_QUOTED = re.compile(r'"([^"]+)"')
_ASKS_FOR = re.compile(r"\bAsks for (?:a|an) (.+)\.$")
_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_URL_FLAGS = {
    "claimed_company_mismatch",
    "suspicious_tld",
    "insecure_link",
    "extra_subdomains",
    "new_domain",
    "long_redirect",
    "virustotal",
}
_WINDOWS_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class OcrError(Exception):
    """The image could not be scored. The message is safe to show in the UI."""


class OcrWord(TypedDict):
    text: str
    x: int
    y: int
    width: int
    height: int


class OcrPage(TypedDict):
    text: str
    width: int
    height: int
    words: list[OcrWord]


def score_screenshot(data: bytes, reader=None) -> dict:
    """Return the combined risk score for one image.

    The result has the same score fields as ``score_message``, plus the cleaned
    text, the image size, and highlight boxes. An unreadable image raises
    ``OcrError`` and does not invent a score.
    """
    if not data:
        raise OcrError("Choose an image before analyzing.")
    read = reader or read_image
    try:
        page = read(data)
    except OcrError:
        raise
    except Exception as exc:
        raise OcrError("Could not read text from this image.") from exc
    cleaned = clean_ocr_text(page.get("text", ""))
    if not cleaned:
        raise OcrError("No text was found in this image.")
    scored = dict(score_message(cleaned))
    scored["text"] = cleaned
    scored["image_width"] = int(page.get("width") or 0)
    scored["image_height"] = int(page.get("height") or 0)
    scored["highlights"] = highlight_words(page.get("words") or [], _phrases(scored, cleaned))
    return scored


def clean_ocr_text(text: str | None) -> str:
    """Return OCR text with broken words, odd spaces, and spaced links repaired."""
    raw = text if isinstance(text, str) else "" if text is None else str(text)
    raw = raw.replace("\u2019", "'").replace("\u2018", "'")
    raw = _HYPHEN_BREAK.sub(r"\1\2", raw)
    raw = raw.replace("\r", "\n").replace("\n", " ")
    raw = _swap_between_letters(raw)
    raw = _SPACED_LETTERS.sub(_join_spaced_letters, raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    raw = _repair_urls(raw)
    return _swap_between_letters(raw).strip()


def read_image(data: bytes) -> OcrPage:
    """Read one image with Tesseract.

    A file Pillow cannot open raises ``OcrError`` with "Upload an image file."
    A missing Tesseract install raises ``OcrError`` and does not return a score.
    """
    if not data:
        raise OcrError("Choose an image before analyzing.")
    try:
        from PIL import Image
    except ImportError as exc:
        raise OcrError("Could not read text from this image.") from exc
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except Exception as exc:
        raise OcrError("Upload an image file.") from exc
    width, height = image.size
    rgb = image.convert("RGB")
    try:
        import pytesseract
    except ImportError as exc:
        raise OcrError("Tesseract is not installed, so this image could not be read.") from exc
    command = _tesseract_command()
    if command:
        pytesseract.pytesseract.tesseract_cmd = command
    try:
        raw_text = pytesseract.image_to_string(rgb)
        table = pytesseract.image_to_data(rgb, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrError("Tesseract is not installed, so this image could not be read.") from exc
    except Exception as exc:
        raise OcrError("Could not read text from this image.") from exc
    words: list[OcrWord] = []
    for index, word in enumerate(table.get("text", [])):
        shown = str(word).strip()
        if not shown:
            continue
        words.append(
            {
                "text": shown,
                "x": int(table["left"][index]),
                "y": int(table["top"][index]),
                "width": int(table["width"][index]),
                "height": int(table["height"][index]),
            }
        )
    return {"text": raw_text or "", "width": width, "height": height, "words": words}


def highlight_words(words: list[OcrWord], phrases: list[str]) -> list[OcrWord]:
    """Return the word boxes whose text matches a fired phrase or link."""
    tokens = [_match_token(word.get("text", "")) for word in words]
    chosen: set[int] = set()
    for phrase in phrases:
        if phrase.lower().startswith("http"):
            _mark_url(tokens, phrase, chosen)
            continue
        parts = [part for part in (_match_token(part) for part in phrase.split()) if part]
        if not parts:
            continue
        width = len(parts)
        for start in range(0, len(tokens) - width + 1):
            if tokens[start : start + width] == parts:
                chosen.update(range(start, start + width))
    return [words[index] for index in sorted(chosen)]


def _phrases(result: dict, cleaned: str) -> list[str]:
    found: list[str] = []
    for reason in result.get("reasons", []):
        found.extend(_QUOTED.findall(reason))
        asked = _ASKS_FOR.search(reason)
        if asked:
            found.append(asked.group(1))
    if _URL_FLAGS.intersection(result.get("flags", [])):
        found.extend(match.group(0).rstrip(".,);]") for match in _URL.finditer(cleaned))
    unique: list[str] = []
    for phrase in found:
        compact = " ".join(phrase.split())
        if compact and compact not in unique:
            unique.append(compact)
    return unique


def _swap_between_letters(text: str) -> str:
    chars = list(text)
    for index, char in enumerate(chars):
        replacement = _CONFUSABLES.get(char)
        if replacement is None:
            continue
        previous = chars[index - 1] if index else ""
        nxt = chars[index + 1] if index + 1 < len(chars) else ""
        if previous.isalpha() and nxt.isalpha():
            chars[index] = replacement
    return "".join(chars)


def _join_spaced_letters(match: re.Match[str]) -> str:
    pieces = match.group(0).split()
    if not pieces or any(len(piece) != 1 for piece in pieces):
        return match.group(0)
    return "".join(_CONFUSABLES.get(piece, piece) for piece in pieces)


def _repair_urls(text: str) -> str:
    pieces: list[str] = []
    cursor = 0
    for match in _URL_START.finditer(text):
        pieces.append(text[cursor : match.start()])
        url = re.sub(r"\s+", "", match.group(0))
        index = match.end()
        while index < len(text):
            char = text[index]
            if char.isspace():
                look = index + 1
                while look < len(text) and text[look].isspace():
                    look += 1
                if look >= len(text):
                    break
                if (url[-1].isalnum() or url[-1] in "._/-?&=%#:+") and (
                    text[look].isalnum() or text[look] in "._/-?&=%#:+"
                ):
                    index = look
                    continue
                break
            if char.isalnum() or char in "._/-?&=%#:+":
                url += char
                index += 1
                continue
            break
        pieces.append(url.rstrip(".,);]"))
        cursor = index
    pieces.append(text[cursor:])
    return "".join(pieces)


def _match_token(text: str) -> str:
    swapped = _swap_between_letters(text.lower())
    return re.sub(r"[^a-z0-9:/._~?#&=%+-]+", "", swapped)


def _mark_url(tokens: list[str], phrase: str, chosen: set[int]) -> None:
    target = _match_token(phrase)
    if not target:
        return
    for start, token in enumerate(tokens):
        if token == target:
            chosen.add(start)
    for start in range(len(tokens)):
        joined = ""
        for end in range(start, min(len(tokens), start + 12)):
            joined += tokens[end]
            if joined == target:
                chosen.update(range(start, end + 1))
                return
            if not target.startswith(joined):
                break


def _tesseract_command() -> str:
    configured = os.environ.get("TESSERACT_CMD", "").strip()
    if configured:
        return configured
    found = shutil.which("tesseract")
    if found:
        return found
    if os.path.isfile(_WINDOWS_TESSERACT):
        return _WINDOWS_TESSERACT
    return ""
