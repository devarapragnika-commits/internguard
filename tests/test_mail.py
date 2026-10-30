"""Checks for sender authenticity and attachment risk. No mailbox is opened."""

import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi import HTTPException

from backend.routes.analyze import AnalyzeEmailBody, analyze_email
from backend.services import url_features
from backend.services.mail import parse_email, score_attachments, score_email, score_sender
from backend.services.risk import TOTAL_CAP, score_message

FEE_SNIPPET = "Kindly pay the registration fee to confirm your place."
LINK = "http://microsoft.secure-login.tk/offer"

SCAM_RAW = f"""From: "Microsoft Careers" <offers@gmail.com>
To: student@college.edu
Reply-To: cash@yahoo.com
Subject: You are selected for a Microsoft internship
Authentication-Results: mx.google.com;
    spf=fail smtp.mailfrom=gmail.com;
    dkim=fail header.i=@gmail.com;
    dmarc=fail header.from=gmail.com
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="BOUND"

--BOUND
Content-Type: text/plain; charset="utf-8"

{FEE_SNIPPET}
Apply at {LINK}

--BOUND
Content-Type: application/pdf
Content-Disposition: attachment; filename="offer.pdf.exe"

not-executed
--BOUND--
"""

CLEAN_RAW = """From: Recruiting <jobs@careers.microsoft.com>
To: student@college.edu
Reply-To: jobs@microsoft.com
Subject: Internship next steps
Authentication-Results: mx.google.com; spf=pass; dkim=pass; dmarc=pass
Content-Type: text/plain; charset="utf-8"

We are pleased to offer you an unpaid software internship.
The stipend is Rs 15000 per month.
"""


def _normalized(points: int) -> int:
    return int((points * 100) / TOTAL_CAP + 0.5)


class MailScoreTests(unittest.TestCase):
    def setUp(self):
        self.whois_patch = patch.object(
            url_features,
            "_lookup_whois",
            return_value=datetime(2018, 1, 15),
        )
        self.redirect_patch = patch.object(
            url_features,
            "_lookup_redirects",
            side_effect=lambda url, timeout: {"length": 0, "destination": url},
        )
        self.whois_patch.start()
        self.redirect_patch.start()
        self.addCleanup(self.whois_patch.stop)
        self.addCleanup(self.redirect_patch.stop)

    def test_fee_failed_dkim_and_pdf_exe_include_all_three_kinds(self):
        result = score_email(SCAM_RAW)
        reasons = " ".join(result["reasons"])
        self.assertIn("registration fee", reasons)
        self.assertIn("Sender failed the DKIM check.", result["reasons"])
        self.assertIn("Attachment uses a double extension such as pdf.exe.", result["reasons"])
        self.assertIn("financial_request", result["flags"])
        self.assertIn("dkim_fail", result["flags"])
        self.assertIn("double_extension", result["flags"])
        self.assertEqual(result["slices"]["sender_authenticity"]["cap"], 15)
        self.assertEqual(result["slices"]["attachment"]["cap"], 10)
        self.assertGreater(result["slices"]["sender_authenticity"]["points"], 0)
        self.assertGreater(result["slices"]["attachment"]["points"], 0)
        self.assertEqual(result["slices"]["financial_request"]["points"], 25)
        self.assertLessEqual(result["slices"]["sender_authenticity"]["points"], 15)
        self.assertLessEqual(result["slices"]["attachment"]["points"], 10)
        self.assertIn("Do not open attachments.", result["recommendation"])
        self.assertIn("Do not pay.", result["recommendation"])
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)

    def test_passing_auth_and_no_attachment_leave_those_slices_at_zero(self):
        result = score_email(CLEAN_RAW)
        self.assertEqual(result["slices"]["sender_authenticity"]["points"], 0)
        self.assertEqual(result["slices"]["attachment"]["points"], 0)
        self.assertEqual(result["slices"]["financial_request"]["points"], 0)
        self.assertNotIn("dkim_fail", result["flags"])
        self.assertNotIn("Sender check was unavailable.", result["reasons"])
        self.assertEqual(result["recommendation"], "Proceed with normal caution.")

    def test_headers_and_attachment_metadata_are_enough(self):
        result = score_email(
            headers=(
                "From: Microsoft HR <hr@gmail.com>\n"
                "Authentication-Results: mx; dkim=fail; spf=pass; dmarc=pass\n"
            ),
            snippet=FEE_SNIPPET,
            attachments=[{"filename": "offer.pdf.exe", "content_type": "application/pdf"}],
        )
        self.assertEqual(result["slices"]["financial_request"]["points"], 25)
        self.assertIn("dkim_fail", result["flags"])
        self.assertIn("free_mail_company", result["flags"])
        self.assertIn("double_extension", result["flags"])
        self.assertIn("type_mismatch", result["flags"])

    def test_header_parse_failure_keeps_the_text_score(self):
        with patch("backend.services.mail._parse_message", side_effect=RuntimeError("bad headers")):
            result = score_email(headers="not-a-header", snippet=FEE_SNIPPET)
        self.assertEqual(result["slices"]["financial_request"]["points"], 25)
        self.assertEqual(result["slices"]["sender_authenticity"]["points"], 0)
        self.assertIn("Sender check was unavailable.", result["reasons"])
        self.assertIn("registration fee", " ".join(result["reasons"]))
        self.assertEqual(result["score"], _normalized(4 + 25))

    def test_pasted_text_still_leaves_email_slices_at_zero(self):
        result = score_message("Kindly pay the registration fee.")
        self.assertEqual(result["slices"]["sender_authenticity"]["points"], 0)
        self.assertEqual(result["slices"]["attachment"]["points"], 0)
        self.assertEqual(result["slices"]["sender_authenticity"]["cap"], 15)
        self.assertEqual(result["slices"]["attachment"]["cap"], 10)

    def test_route_returns_one_score_and_rejects_empty_input(self):
        result = analyze_email(AnalyzeEmailBody(raw=CLEAN_RAW))
        self.assertIn("score", result)
        self.assertIn("band", result)
        self.assertIn("reasons", result)
        self.assertEqual(result["slices"]["sender_authenticity"]["cap"], 15)
        self.assertEqual(result["slices"]["attachment"]["cap"], 10)

        with self.assertRaises(HTTPException) as caught:
            analyze_email(AnalyzeEmailBody())
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(caught.exception.detail, "Paste an email before analyzing.")

    def test_does_not_execute_or_render(self):
        import inspect

        source = inspect.getsource(__import__("backend.services.mail", fromlist=["mail"]))
        self.assertNotIn("webbrowser", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("os.system", source)
        parsed = parse_email(SCAM_RAW)
        self.assertEqual(parsed["attachments"][0]["filename"], "offer.pdf.exe")
        self.assertNotIn("not-executed", parsed["snippet"])


class SenderAndAttachmentUnitTests(unittest.TestCase):
    def test_reply_to_mismatch_and_free_mail_display_name(self):
        parsed = parse_email(
            headers=(
                'From: "Google Careers" <hr.microsoft@gmail.com>\n'
                "Reply-To: other@yahoo.com\n"
                "Authentication-Results: mx; spf=pass; dkim=pass; dmarc=pass\n"
            ),
            snippet="Hello",
        )
        sender = score_sender(parsed)
        self.assertIn("free_mail_company", sender["flags"])
        self.assertIn("reply_to_mismatch", sender["flags"])
        self.assertLessEqual(sender["points"], 15)

    def test_ordinary_gmail_display_name_is_not_a_company_claim(self):
        parsed = parse_email(
            headers="From: Anika <anika@gmail.com>\nAuthentication-Results: mx; spf=pass; dkim=pass; dmarc=pass\n",
            snippet="Hello",
        )
        sender = score_sender(parsed)
        self.assertEqual(sender["points"], 0)

    def test_macro_and_type_mismatch_without_opening_the_file(self):
        result = score_attachments(
            [{"filename": "invoice.xlsm", "content_type": "application/pdf"}]
        )
        self.assertIn("macro_office", result["flags"])
        self.assertIn("type_mismatch", result["flags"])
        self.assertLessEqual(result["points"], 10)
        self.assertNotIn("double_extension", result["flags"])
