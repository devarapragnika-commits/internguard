"""Sender authenticity and attachment risk from a raw email.

The message is never rendered. Remote images are not loaded. Attachments
are not opened or executed. Only headers, a plain-text snippet, filenames,
and declared types are read.

Sender authenticity is capped at 15:

- SPF fail: 5
- DKIM fail: 5
- DMARC fail: 5
- A display name that claims a company on a free-mail address: 6
- From domain differs from Reply-To: 4

Attachment risk is capped at 10:

- A double extension such as pdf.exe: 6
- A dangerous extension: 5
- A macro-enabled Office file: 4
- Filename extension does not match the declared type: 4

If the headers cannot be read, sender points stay at 0 and the reason is
"Sender check was unavailable."
"""

from __future__ import annotations

import re
from email import policy
from email.message import Message
from email.parser import BytesParser
from email.utils import parseaddr
from typing import TypedDict
from urllib.parse import unquote

from backend.services.company_domain import registrable_domain

SENDER_CAP = 15
ATTACHMENT_CAP = 10
MAX_EMAIL_BYTES = 200_000
_UNAVAILABLE = "Sender check was unavailable."

_FREE_MAIL = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "ymail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
    "icloud.com",
    "me.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
    "gmx.com",
    "gmx.net",
    "zoho.com",
    "yandex.com",
    "mail.com",
    "rediffmail.com",
}

_DISPLAY_SKIP = {
    "careers",
    "career",
    "hr",
    "team",
    "internship",
    "internships",
    "intern",
    "recruiting",
    "recruitment",
    "recruiter",
    "official",
    "job",
    "jobs",
    "offer",
    "offers",
    "hiring",
    "noreply",
    "no-reply",
    "donotreply",
}

_DANGEROUS = {
    "exe",
    "scr",
    "bat",
    "cmd",
    "com",
    "pif",
    "vbs",
    "js",
    "jse",
    "jar",
    "msi",
    "ps1",
    "cpl",
    "hta",
    "wsf",
}

_MACRO = {"docm", "dotm", "xlsm", "xltm", "xlsb", "xlam", "pptm", "potm", "ppam"}

_TYPE_FOR_EXT = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "txt": "text/plain",
    "csv": "text/csv",
    "html": "text/html",
    "htm": "text/html",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "zip": "application/zip",
}

_GENERIC_TYPES = {"application/octet-stream", "binary/octet-stream"}

_HREF = re.compile(r"""href\s*=\s*["'](https?://[^"']+)["']""", re.IGNORECASE)
_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_AUTH_PAIR = re.compile(r"\b(spf|dkim|dmarc)\s*=\s*(pass|fail|neutral|none|temperror|permerror|softfail|bestguesspass)", re.IGNORECASE)
_RECEIVED_SPF = re.compile(r"^Received-SPF:\s*(\w+)", re.IGNORECASE | re.MULTILINE)


class AttachmentMeta(TypedDict):
    filename: str
    content_type: str


class SliceFlags(TypedDict):
    points: int
    reasons: list[str]
    flags: list[str]
    unavailable: bool


class ParsedEmail(TypedDict):
    subject: str
    snippet: str
    text: str
    from_name: str
    from_address: str
    reply_to_address: str
    auth: dict[str, str]
    attachments: list[AttachmentMeta]
    unavailable: bool


def score_email(
    raw: str | None = None,
    *,
    headers: str | None = None,
    snippet: str | None = None,
    attachments: list[AttachmentMeta] | None = None,
) -> dict:
    """Return the combined score for one email.

    ``raw`` is a full RFC 822 message. ``headers`` plus ``snippet`` and
    ``attachments`` can be used instead. The result is the same shape as
    ``score_message``.
    """
    from backend.services.risk import score_message

    parsed = parse_email(raw, headers=headers, snippet=snippet, attachments=attachments)
    sender = score_sender(parsed)
    attached = score_attachments(parsed["attachments"])
    return score_message(
        parsed["text"],
        sender=sender,
        attachments=attached,
        sender_address=parsed["from_address"],
    )


def parse_email(
    raw: str | None = None,
    *,
    headers: str | None = None,
    snippet: str | None = None,
    attachments: list[AttachmentMeta] | None = None,
) -> ParsedEmail:
    """Read headers, a plain snippet, and attachment names. Nothing is executed."""
    extra = [_clean_attachment(item) for item in (attachments or [])]
    extra = [item for item in extra if item["filename"] or item["content_type"]]
    source = _as_text(raw)
    header_source = _as_text(headers)
    given_snippet = _as_text(snippet).strip()
    if not source and not header_source and not given_snippet and not extra:
        return _empty_parse(unavailable=False)
    try:
        message = _parse_message(source or header_source)
    except Exception:
        text = _join_text("", given_snippet, source)
        return {
            "subject": "",
            "snippet": given_snippet,
            "text": text,
            "from_name": "",
            "from_address": "",
            "reply_to_address": "",
            "auth": {},
            "attachments": extra,
            "unavailable": True,
        }
    subject = _header(message, "subject")
    from_name, from_address = _first_address(message, "from")
    _reply_name, reply_to = _first_address(message, "reply-to")
    body = given_snippet or _snippet(message)
    found = _attachments_from_message(message) if source else []
    names = {item["filename"] for item in found}
    for item in extra:
        if item["filename"] not in names:
            found.append(item)
    raw_for_links = source or body
    text = _join_text(subject, body, raw_for_links)
    return {
        "subject": subject,
        "snippet": body,
        "text": text,
        "from_name": from_name,
        "from_address": from_address,
        "reply_to_address": reply_to,
        "auth": _auth_results(message, header_source or source),
        "attachments": found,
        "unavailable": False,
    }


def score_sender(parsed: ParsedEmail) -> SliceFlags:
    """Return sender-authenticity points, capped at 15."""
    if parsed["unavailable"]:
        return {"points": 0, "reasons": [_UNAVAILABLE], "flags": ["sender_check_unavailable"], "unavailable": True}
    found: list[tuple[str, str]] = []
    auth = parsed["auth"]
    if auth.get("spf") == "fail":
        found.append(("spf_fail", "Sender failed the SPF check."))
    if auth.get("dkim") == "fail":
        found.append(("dkim_fail", "Sender failed the DKIM check."))
    if auth.get("dmarc") == "fail":
        found.append(("dmarc_fail", "Sender failed the DMARC check."))
    if _free_mail_posing_as_company(parsed["from_name"], parsed["from_address"]):
        found.append(
            (
                "free_mail_company",
                "Display name claims a company, but the address is a free mailbox.",
            )
        )
    if _reply_mismatch(parsed["from_address"], parsed["reply_to_address"]):
        found.append(("reply_to_mismatch", "From domain differs from the Reply-To domain."))
    weights = {
        "spf_fail": 5,
        "dkim_fail": 5,
        "dmarc_fail": 5,
        "free_mail_company": 6,
        "reply_to_mismatch": 4,
    }
    points = min(sum(weights[flag] for flag, _reason in found), SENDER_CAP)
    return {
        "points": points,
        "reasons": [reason for _flag, reason in found],
        "flags": [flag for flag, _reason in found],
        "unavailable": False,
    }


def score_attachments(items: list[AttachmentMeta]) -> SliceFlags:
    """Return attachment-risk points, capped at 10. Files are not opened."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in items:
        name = item.get("filename") or ""
        declared = (item.get("content_type") or "").split(";", 1)[0].strip().lower()
        extensions = _extensions(name)
        last = extensions[-1] if extensions else ""
        if len(extensions) >= 2 and last in _DANGEROUS:
            key = "double_extension"
            if key not in seen:
                found.append((key, "Attachment uses a double extension such as pdf.exe."))
                seen.add(key)
        if last in _DANGEROUS:
            key = "dangerous_extension"
            if key not in seen:
                found.append((key, "Attachment has a dangerous file extension."))
                seen.add(key)
        if last in _MACRO:
            key = "macro_office"
            if key not in seen:
                found.append((key, "Attachment is a macro-enabled Office file."))
                seen.add(key)
        if _type_mismatch(last, declared):
            key = "type_mismatch"
            if key not in seen:
                found.append((key, "Attachment extension does not match the declared type."))
                seen.add(key)
    weights = {
        "double_extension": 6,
        "dangerous_extension": 5,
        "macro_office": 4,
        "type_mismatch": 4,
    }
    points = min(sum(weights[flag] for flag, _reason in found), ATTACHMENT_CAP)
    return {
        "points": points,
        "reasons": [reason for _flag, reason in found],
        "flags": [flag for flag, _reason in found],
        "unavailable": False,
    }


def _as_text(value: str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _parse_message(source: str) -> Message:
    data = source.encode("utf-8", errors="replace")
    return BytesParser(policy=policy.default).parsebytes(data)


def _header(message: Message, name: str) -> str:
    value = message.get(name)
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("\r", " ").strip()


def _first_address(message: Message, name: str) -> tuple[str, str]:
    header = _header(message, name)
    if not header:
        return "", ""
    display, address = parseaddr(header)
    return display.strip().strip('"'), address.strip().lower()


def _auth_results(message: Message, raw: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for value in message.get_all("authentication-results") or []:
        for kind, result in _AUTH_PAIR.findall(str(value)):
            found[kind.lower()] = result.lower()
    match = _RECEIVED_SPF.search(raw)
    if match and "spf" not in found:
        found["spf"] = match.group(1).lower()
    return found


def _snippet(message: Message) -> str:
    if not message.is_multipart():
        return _decode_body(message)
    plain = ""
    html = ""
    for part in message.walk():
        if part.get_content_maintype() == "multipart":
            continue
        disposition = str(part.get("content-disposition") or "").lower()
        if "attachment" in disposition:
            continue
        content_type = (part.get_content_type() or "").lower()
        body = _decode_body(part)
        if content_type == "text/plain" and not plain:
            plain = body
        elif content_type == "text/html" and not html:
            html = body
    return plain or _strip_html(html)


def _decode_body(part: Message) -> str:
    try:
        payload = part.get_payload(decode=True)
    except Exception:
        payload = None
    if isinstance(payload, bytes):
        charset = part.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace")
    else:
        value = part.get_payload()
        text = value if isinstance(value, str) else ""
    return text.replace("\x00", "")


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = _TAG.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _attachments_from_message(message: Message) -> list[AttachmentMeta]:
    found: list[AttachmentMeta] = []
    if not message.is_multipart() and not message.get_filename():
        return found
    for part in message.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename() or ""
        disposition = str(part.get("content-disposition") or "").lower()
        content_type = (part.get_content_type() or "").lower()
        is_body = content_type in {"text/plain", "text/html"} and "attachment" not in disposition
        if not filename and is_body:
            continue
        if not filename and "attachment" not in disposition:
            continue
        found.append({"filename": unquote(filename), "content_type": content_type})
    return found


def _clean_attachment(item) -> AttachmentMeta:
    if not isinstance(item, dict):
        return {"filename": _as_text(item), "content_type": ""}
    return {
        "filename": _as_text(item.get("filename")).strip(),
        "content_type": _as_text(item.get("content_type")).strip(),
    }


def _join_text(subject: str, snippet: str, raw: str) -> str:
    links: list[str] = []
    for match in list(_HREF.finditer(raw)) + list(_URL.finditer(raw)):
        url = match.group(1) if match.lastindex else match.group(0)
        url = url.rstrip(".,);]")
        if url not in links:
            links.append(url)
    parts = [part for part in (subject.strip(), snippet.strip(), " ".join(links)) if part]
    return "\n".join(parts)


def _free_mail_posing_as_company(display: str, address: str) -> bool:
    domain = registrable_domain(address)
    if domain not in _FREE_MAIL:
        return False
    local = address.split("@", 1)[0]
    words = re.findall(r"[A-Za-z][A-Za-z0-9&'.-]*", display)
    kept = []
    for word in words:
        token = re.sub(r"[^a-z0-9]+", "", word.lower())
        if len(token) < 4 or token in _DISPLAY_SKIP or token == local.lower():
            continue
        kept.append(token)
    return bool(kept)


def _reply_mismatch(from_address: str, reply_to: str) -> bool:
    if not from_address or not reply_to:
        return False
    left = registrable_domain(from_address)
    right = registrable_domain(reply_to)
    return bool(left and right and left != right)


def _extensions(filename: str) -> list[str]:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].lstrip(".")
    if not name or "." not in name:
        return []
    return [part.lower() for part in name.split(".")[1:] if part]


def _type_mismatch(extension: str, declared: str) -> bool:
    if not extension or not declared:
        return False
    declared = declared.split(";", 1)[0].strip().lower()
    if declared in _GENERIC_TYPES:
        return False
    expected = _TYPE_FOR_EXT.get(extension)
    if expected and declared == expected:
        return False
    for ext, mime in _TYPE_FOR_EXT.items():
        if declared == mime:
            return ext != extension
    if expected:
        return True
    return False


def _empty_parse(*, unavailable: bool) -> ParsedEmail:
    return {
        "subject": "",
        "snippet": "",
        "text": "",
        "from_name": "",
        "from_address": "",
        "reply_to_address": "",
        "auth": {},
        "attachments": [],
        "unavailable": unavailable,
    }
