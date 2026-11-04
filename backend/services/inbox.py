"""Sandbox inbox of fixture messages. No mailbox is opened.

Each row is scored from headers, a snippet, and attachment filenames.
There is no full body, no remote image, and no Gmail or IMAP fetch.
The badge is the same band ``score_message`` would return for that
metadata.
"""

from __future__ import annotations

from backend.services.mail import parse_email, score_email

FIXTURES: list[dict] = [
    {
        "id": "high-fee-double-extension",
        "unread": True,
        "headers": (
            'From: "Microsoft Careers" <offers@gmail.com>\r\n'
            "To: student@college.edu\r\n"
            "Reply-To: cash@yahoo.com\r\n"
            "Subject: Microsoft internship — act now\r\n"
            "Authentication-Results: mx.google.com; "
            "spf=fail smtp.mailfrom=gmail.com; "
            "dkim=fail header.i=@gmail.com; "
            "dmarc=fail header.from=gmail.com\r\n"
        ),
        "snippet": "Kindly pay the registration fee to confirm your place. Act now.",
        "attachments": [{"filename": "offer.pdf.exe", "content_type": "application/pdf"}],
    },
    {
        "id": "medium-auth-and-attachment",
        "unread": True,
        "headers": (
            "From: Hiring Desk <desk@campus-jobs.example>\r\n"
            "To: student@college.edu\r\n"
            "Reply-To: files@other-desk.example\r\n"
            "Subject: Onboarding form attached\r\n"
            "Authentication-Results: mx.google.com; "
            "spf=fail; dkim=fail; dmarc=fail\r\n"
        ),
        "snippet": "Please complete the attached onboarding form before Thursday.",
        "attachments": [{"filename": "offer.pdf.exe", "content_type": "application/pdf"}],
    },
    {
        "id": "low-unpaid-offer",
        "unread": True,
        "headers": (
            "From: Recruiting <jobs@careers.microsoft.com>\r\n"
            "To: student@college.edu\r\n"
            "Reply-To: jobs@microsoft.com\r\n"
            "Subject: Internship next steps\r\n"
            "Authentication-Results: mx.google.com; "
            "spf=pass; dkim=pass; dmarc=pass\r\n"
        ),
        "snippet": (
            "We are pleased to offer you an unpaid software internship. "
            "The stipend is Rs 15000 per month."
        ),
        "attachments": [],
    },
]


def list_inbox() -> dict:
    """Return fixture rows with a pre-open badge from the shared scorer."""
    return {"messages": [score_inbox_row(item) for item in FIXTURES]}


def score_inbox_row(item: dict) -> dict:
    """Score one fixture from metadata only. The body is never fetched."""
    headers = item.get("headers") or ""
    snippet = item.get("snippet") or ""
    attachments = item.get("attachments") or []
    parsed = parse_email(headers=headers, snippet=snippet, attachments=attachments)
    scored = score_email(headers=headers, snippet=snippet, attachments=attachments)
    return {
        "id": item["id"],
        "unread": bool(item.get("unread", True)),
        "from_name": parsed["from_name"],
        "from_address": parsed["from_address"],
        "subject": parsed["subject"] or "(no subject)",
        "snippet": parsed["snippet"],
        "attachments": [entry["filename"] for entry in parsed["attachments"] if entry.get("filename")],
        "score": scored["score"],
        "band": scored["band"],
        "reasons": scored["reasons"],
        "flags": scored["flags"],
        "recommendation": scored["recommendation"],
        "slices": scored["slices"],
    }
