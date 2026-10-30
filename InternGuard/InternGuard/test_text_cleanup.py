"""Disguised spelling should match the plain message. Network lookups are mocked."""

import unittest
from datetime import datetime
from unittest.mock import patch

from backend.services import url_features
from backend.services.lookalike_domain import LOOKALIKE_REASON, detect_lookalike_domain
from backend.services.payment import detect_payment_request
from backend.services.risk import URL_CAP, score_message
from backend.services.text_cleanup import clean_for_matching

PLAIN = "Kindly pay the registration fee."
CYRILLIC_O = "\u043e"
CYRILLIC_E = "\u0435"
LOOKALIKE_HOST = f"micr{CYRILLIC_O}soft.com"


def _punycode_url() -> str:
    host = LOOKALIKE_HOST.encode("idna").decode("ascii")
    return f"https://{host}/careers"


class TextCleanupTests(unittest.TestCase):
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

    def test_cleanup_is_stable(self):
        cleaned = clean_for_matching("Kindly pay the r3gistration fee.")
        self.assertEqual(clean_for_matching(cleaned), cleaned)

    def test_disguised_fee_matches_plain_score(self):
        plain = score_message(PLAIN)
        disguised = (
            "Kindly pay the r3gistration fee.",
            "Kindly pay the regis\u200btration fee.",
            "Kindly pay the r e g i s t r a t i o n fee.",
            f"Kindly pay the r{CYRILLIC_E}gistration fee.",
        )
        for text in disguised:
            with self.subTest(text=text):
                result = score_message(text)
                self.assertEqual(result["score"], plain["score"])
                self.assertEqual(result["slices"]["financial_request"]["points"], 25)
                self.assertEqual(
                    result["slices"]["financial_request"]["points"],
                    plain["slices"]["financial_request"]["points"],
                )
                self.assertTrue(detect_payment_request(text)["flagged"])

    def test_normal_amounts_and_official_links_are_not_rewritten(self):
        samples = (
            "Rs 15000 per month",
            "2026",
            "B2B",
            "I am a student",
            "https://careers.microsoft.com/jobs",
        )
        for text in samples:
            cleaned = clean_for_matching(text)
            self.assertIn(text.split()[0], cleaned.replace("https://", "https://"))
        self.assertEqual(
            clean_for_matching("https://careers.microsoft.com/jobs"),
            "https://careers.microsoft.com/jobs",
        )
        self.assertEqual(clean_for_matching("Rs 15000 per month"), "Rs 15000 per month")
        self.assertEqual(clean_for_matching("2026"), "2026")
        self.assertEqual(clean_for_matching("B2B"), "B2B")
        self.assertEqual(clean_for_matching("I am a student"), "I am a student")

    def test_cyrillic_lookalike_domain_is_flagged(self):
        text = f"Microsoft internship. Apply at https://{LOOKALIKE_HOST}/careers"
        result = score_message(text)
        self.assertIn(LOOKALIKE_REASON, result["reasons"])
        self.assertIn("lookalike_domain", result["flags"])
        self.assertLessEqual(result["slices"]["url_domain"]["points"], URL_CAP)
        self.assertNotIn("claimed_company_mismatch", result["flags"])
        self.assertTrue(
            detect_lookalike_domain(text, url=f"https://{LOOKALIKE_HOST}/careers")["flagged"]
        )

    def test_punycode_lookalike_domain_is_flagged(self):
        url = _punycode_url()
        text = f"Microsoft internship. Apply at {url}"
        result = score_message(text)
        self.assertIn(LOOKALIKE_REASON, result["reasons"])
        self.assertIn("lookalike_domain", result["flags"])
        self.assertTrue(url.lower().startswith("https://xn--") or "xn--" in url)

    def test_official_microsoft_domain_is_not_a_lookalike(self):
        text = "Microsoft internship. Details at https://careers.microsoft.com/jobs"
        result = score_message(text)
        self.assertNotIn(LOOKALIKE_REASON, result["reasons"])
        self.assertNotIn("lookalike_domain", result["flags"])
        self.assertEqual(result["slices"]["url_domain"]["points"], 0)
        self.assertFalse(
            detect_lookalike_domain(text, url="https://careers.microsoft.com/jobs")["flagged"]
        )
