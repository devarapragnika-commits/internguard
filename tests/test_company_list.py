"""Checks for the verified company domain list. No network lookups."""

import unittest
from datetime import datetime
from unittest.mock import patch

from backend.services import url_features
from backend.services.company_list import check_verified_company, load_verified_companies
from backend.services.risk import score_message

TCS_ALIAS = "TCS internship. Apply at https://www.tcs.com/careers"
TCS_FULL = "Tata Consultancy Services internship. Details at https://careers.tcs.com/jobs"
TCS_BAD = "Tata Consultancy Services internship. Apply at https://secure-login.tk/offer"
UNKNOWN = "Brightpath Studios internship. Apply at https://secure-login.tk/apply"


class CompanyListTests(unittest.TestCase):
    def test_repo_csv_lists_tcs(self):
        rows = load_verified_companies()
        tcs = next(row for row in rows if row["company"] == "Tata Consultancy Services")
        self.assertIn("tcs", [alias.lower() for alias in tcs["aliases"]])
        self.assertEqual(tcs["domains"], ["tcs.com"])

    def test_listed_match_adds_no_points(self):
        for text in (TCS_ALIAS, TCS_FULL):
            result = check_verified_company(text)
            self.assertTrue(result["listed"], text)
            self.assertTrue(result["domain_allowed"], text)
            self.assertEqual(result["points"], 0, text)
            self.assertEqual(result["reason"], "", text)
            self.assertEqual(result["domain"], "tcs.com", text)

    def test_listed_mismatch_requires_verification(self):
        result = check_verified_company(TCS_BAD)
        self.assertTrue(result["listed"])
        self.assertFalse(result["domain_allowed"])
        self.assertEqual(result["points"], 5)
        self.assertEqual(result["flag"], "company_requires_verification")
        self.assertEqual(result["reason"], "Tata Consultancy Services requires verification.")
        self.assertNotIn("scam", result["reason"].lower())
        self.assertEqual(result["domain"], "secure-login.tk")

    def test_unlisted_company_is_not_a_list_failure(self):
        result = check_verified_company(UNKNOWN)
        self.assertFalse(result["listed"])
        self.assertEqual(result["points"], 0)
        self.assertEqual(result["reason"], "")
        self.assertEqual(result["flag"], "")

    def test_listed_company_without_a_domain_is_not_a_failure(self):
        result = check_verified_company("Tata Consultancy Services internship")
        self.assertTrue(result["listed"])
        self.assertEqual(result["points"], 0)
        self.assertEqual(result["reason"], "")

    def test_sender_on_the_list_adds_no_points(self):
        match = check_verified_company("TCS internship", sender="hr@tcs.com")
        mismatch = check_verified_company("TCS internship", sender="hr@secure-login.tk")
        self.assertTrue(match["domain_allowed"])
        self.assertEqual(match["points"], 0)
        self.assertEqual(match["domain"], "tcs.com")
        self.assertEqual(mismatch["points"], 5)
        self.assertIn("requires verification", mismatch["reason"])
        self.assertNotIn("scam", mismatch["reason"].lower())

    def test_official_tcs_domain_does_not_raise_the_fuzzy_mismatch(self):
        with patch.object(url_features, "_lookup_whois", return_value=datetime(2018, 1, 15)):
            with patch.object(
                url_features,
                "_lookup_redirects",
                side_effect=lambda url, timeout: {"length": 0, "destination": url},
            ):
                result = score_message(TCS_FULL)
        self.assertEqual(result["slices"]["company_verification"]["points"], 0)
        self.assertNotIn("claimed_company_mismatch", result["flags"])
        self.assertNotIn("requires verification", " ".join(result["reasons"]))

    def test_unlisted_company_still_uses_the_fuzzy_check(self):
        with patch.object(url_features, "_lookup_whois", return_value=datetime(2018, 1, 15)):
            with patch.object(
                url_features,
                "_lookup_redirects",
                side_effect=lambda url, timeout: {"length": 0, "destination": url},
            ):
                result = score_message(UNKNOWN)
        self.assertEqual(result["slices"]["company_verification"]["points"], 0)
        joined = " ".join(result["reasons"]).lower()
        self.assertNotIn("requires verification", joined)
        self.assertIn("claimed_company_mismatch", result["flags"])
        self.assertIn("claimed company does not match link domain.", result["reasons"])
