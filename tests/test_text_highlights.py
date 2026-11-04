"""Phrases that fired in score_message are marked in the original paste."""

import unittest
from datetime import datetime
from unittest.mock import patch

from backend.routes.analyze import AnalyzeEmailBody, AnalyzeTextBody, analyze_email, analyze_text
from backend.services import url_features
from backend.services.risk import score_message
from backend.services.text_highlights import source_highlights

FEE_AND_LOOKALIKE = (
    "You are selected for a Microsoft internship. "
    "Kindly pay the registration fee to confirm your place. "
    "Apply at http://microsoft.secure-login.tk/offer"
)
UNPAID = (
    "We are pleased to offer you an unpaid software internship. "
    "The stipend is Rs 15000 per month."
)


class TextHighlightTests(unittest.TestCase):
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

    def test_fee_and_lookalike_marks_the_phrase_and_the_link(self):
        scored = score_message(FEE_AND_LOOKALIKE)
        result = analyze_text(AnalyzeTextBody(text=FEE_AND_LOOKALIKE))
        self.assertEqual(result["flags"], scored["flags"])
        self.assertEqual(result["reasons"], scored["reasons"])
        marked = " ".join(item["phrase"] for item in result["text_highlights"])
        self.assertIn("registration fee", marked.lower())
        self.assertIn("microsoft.secure-login.tk", marked)
        for item in result["text_highlights"]:
            self.assertEqual(FEE_AND_LOOKALIKE[item["start"] : item["end"]], item["phrase"])
            self.assertIn(item["reason"], result["reasons"])

    def test_unpaid_offer_has_no_highlights(self):
        result = analyze_text(AnalyzeTextBody(text=UNPAID))
        self.assertEqual(result["flags"], [])
        self.assertEqual(result["text_highlights"], [])
        self.assertEqual(source_highlights(UNPAID, result), [])

    def test_email_source_is_highlighted_the_same_way(self):
        raw = "From: hr@gmail.com\nSubject: Offer\n\n" + FEE_AND_LOOKALIKE + "\n"
        result = analyze_email(AnalyzeEmailBody(raw=raw))
        marked = " ".join(item["phrase"] for item in result["text_highlights"])
        self.assertIn("registration fee", marked.lower())
        self.assertIn("microsoft.secure-login.tk", marked)
