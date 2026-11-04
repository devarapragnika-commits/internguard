"""Checks for the combined text and URL score. Network lookups are mocked."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException

from backend.routes.analyze import AnalyzeTextBody, analyze_text
from backend.services import url_features
from backend.services.risk import TOTAL_CAP, score_message

FEE = (
    "You are selected for a Microsoft internship. "
    "Kindly pay the registration fee to confirm your place."
)
FEE_AND_LOOKALIKE = FEE + " Apply at http://microsoft.secure-login.tk/offer"
OFFICIAL = (
    "You are selected for a Microsoft internship. "
    "There is no registration fee. "
    "Details at https://careers.microsoft.com/jobs"
)
UNPAID = (
    "We are pleased to offer you an unpaid software internship. "
    "The stipend is Rs 15000 per month."
)
YOUNG_LINK = "Open https://jobs.example.com/start"


def _normalized(points: int) -> int:
    return int((points * 100) / TOTAL_CAP + 0.5)


class RiskScoreTests(unittest.TestCase):
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

    def test_no_link_leaves_url_risk_at_zero(self):
        result = score_message(UNPAID)
        self.assertEqual(result["slices"]["url_domain"]["points"], 0)
        self.assertEqual(result["slices"]["url_domain"]["cap"], 20)
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["band"], "low")
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["recommendation"], "Proceed with normal caution.")
        self.assertNotIn("url_check_unavailable", result["flags"])

    def test_fee_and_lookalike_include_both_kinds_of_reasons(self):
        result = score_message(FEE_AND_LOOKALIKE)
        reasons = " ".join(result["reasons"])
        self.assertIn("registration fee", reasons)
        self.assertIn("claimed company does not match link domain.", reasons)
        self.assertIn("suspicious top-level domain", reasons)
        self.assertIn("financial_request", result["flags"])
        self.assertIn("claimed_company_mismatch", result["flags"])
        self.assertEqual(result["slices"]["financial_request"]["points"], 25)
        self.assertEqual(result["slices"]["linguistic"]["points"], 4)
        self.assertEqual(result["slices"]["url_domain"]["points"], 13)
        self.assertEqual(result["slices"]["company_verification"]["points"], 5)
        self.assertIn("requires verification", reasons)
        self.assertNotIn("scam", reasons.lower())
        self.assertEqual(result["score"], _normalized(4 + 25 + 13 + 5))
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)
        self.assertEqual(
            result["recommendation"],
            "Do not pay. Verify the sender through the official company channel.",
        )

    def test_matching_official_domain_adds_no_url_points(self):
        result = score_message(OFFICIAL)
        self.assertEqual(result["slices"]["financial_request"]["points"], 0)
        self.assertEqual(result["slices"]["url_domain"]["points"], 0)
        self.assertNotIn("claimed_company_mismatch", result["flags"])
        self.assertNotIn("URL check was unavailable.", result["reasons"])
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["band"], "low")

    def test_url_lookup_failure_keeps_the_text_score(self):
        text = FEE + " Details at https://careers.microsoft.com/jobs"
        with patch("backend.services.risk.extract_url_features", side_effect=RuntimeError("down")):
            failed = score_message(text)
        self.assertEqual(failed["slices"]["financial_request"]["points"], 25)
        self.assertEqual(failed["slices"]["linguistic"]["points"], 4)
        self.assertEqual(failed["slices"]["url_domain"]["points"], 0)
        self.assertIn("URL check was unavailable.", failed["reasons"])
        self.assertIn("registration fee", " ".join(failed["reasons"]))
        self.assertEqual(failed["score"], _normalized(4 + 25))

    def test_unknown_age_and_redirects_are_not_scored_as_risky(self):
        with patch.object(url_features, "_lookup_whois", side_effect=RuntimeError("down")):
            with patch.object(url_features, "_lookup_redirects", side_effect=RuntimeError("down")):
                result = score_message(YOUNG_LINK)
        self.assertEqual(result["slices"]["url_domain"]["points"], 0)
        self.assertIn("URL check was unavailable.", result["reasons"])
        self.assertNotIn("Link domain is newly registered.", result["reasons"])
        self.assertNotIn("Link redirects more than once.", result["reasons"])
        self.assertEqual(result["recommendation"], "Verify the sender through the official company channel.")

    def test_known_young_domain_and_long_redirect_add_url_points(self):
        created = datetime.now() - timedelta(days=10)
        with patch.object(url_features, "_lookup_whois", return_value=created):
            with patch.object(
                url_features,
                "_lookup_redirects",
                side_effect=lambda url, timeout: {"length": 3, "destination": url},
            ):
                result = score_message(YOUNG_LINK)
        self.assertEqual(result["slices"]["url_domain"]["points"], 7)
        self.assertIn("Link domain is newly registered.", result["reasons"])
        self.assertIn("Link redirects more than once.", result["reasons"])
        self.assertNotIn("URL check was unavailable.", result["reasons"])

    def test_email_slices_stay_zero_and_company_list_can_score(self):
        result = score_message(FEE_AND_LOOKALIKE)
        self.assertEqual(result["slices"]["sender_authenticity"]["points"], 0)
        self.assertEqual(result["slices"]["attachment"]["points"], 0)
        self.assertEqual(result["slices"]["company_verification"]["points"], 5)
        self.assertEqual(result["slices"]["sender_authenticity"]["cap"], 15)
        self.assertEqual(result["slices"]["attachment"]["cap"], 10)
        self.assertEqual(result["slices"]["company_verification"]["cap"], 15)
        self.assertIn("Microsoft requires verification.", result["reasons"])

    def test_empty_text_does_not_crash(self):
        for text in ("", "   ", None, "hello", 123):
            result = score_message(text)
            self.assertGreaterEqual(result["score"], 0)
            self.assertLessEqual(result["score"], 100)
            self.assertIn(result["band"], ("low", "medium", "high"))

    def test_api_returns_one_score_and_rejects_empty_text(self):
        result = analyze_text(AnalyzeTextBody(text=UNPAID))
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["band"], "low")
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["slices"]["url_domain"]["points"], 0)

        with self.assertRaises(HTTPException) as caught:
            analyze_text(AnalyzeTextBody(text="   "))
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(caught.exception.detail, "Paste a message before analyzing.")
