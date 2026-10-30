"""Checks for claimed-company versus domain comparison. No network lookups."""

import unittest

from backend.services.company_domain import compare_claimed_company


class CompanyDomainTests(unittest.TestCase):
    def test_lookalike_domain_is_flagged_with_a_reason(self):
        text = "Microsoft internship. Apply here: http://microsoft.secure-login.tk/offer"
        result = compare_claimed_company(text)
        self.assertTrue(result["flagged"])
        self.assertEqual(result["flag"], "claimed_company_mismatch")
        self.assertEqual(result["reason"], "claimed company does not match link domain.")
        self.assertEqual(result["claimed_company"], "Microsoft")
        self.assertEqual(result["domain"], "secure-login.tk")
        self.assertEqual(result["source"], "url")

    def test_typosquat_domain_is_flagged(self):
        result = compare_claimed_company(
            "Microsoft internship",
            url="https://micros0ft.com/careers",
        )
        self.assertTrue(result["flagged"])
        self.assertEqual(result["domain"], "micros0ft.com")
        self.assertIn("does not match link domain", result["reason"])

    def test_matching_domain_is_not_flagged(self):
        result = compare_claimed_company(
            "Microsoft internship. Details at https://careers.microsoft.com/jobs"
        )
        self.assertFalse(result["flagged"])
        self.assertEqual(result["flag"], "")
        self.assertEqual(result["reason"], "")
        self.assertEqual(result["claimed_company"], "Microsoft")
        self.assertEqual(result["domain"], "microsoft.com")

    def test_spaced_company_name_matches_domain(self):
        result = compare_claimed_company(
            "Goldman Sachs internship",
            url="https://www.goldmansachs.com/careers",
        )
        self.assertFalse(result["flagged"])
        self.assertEqual(result["claimed_company"], "Goldman Sachs")
        self.assertEqual(result["domain"], "goldmansachs.com")

    def test_missing_company_does_not_raise_or_invent_a_mismatch(self):
        samples = (
            "",
            "   ",
            None,
            "Please apply today. The link is https://evil.example/jobs",
            "HP internship at https://evil.example/apply",
            "software engineering internship https://jobs.example/apply",
        )
        for text in samples:
            result = compare_claimed_company(text)
            self.assertFalse(result["flagged"], text)
            self.assertEqual(result["reason"], "", text)
            self.assertEqual(result["claimed_company"], "", text)

    def test_company_without_a_domain_is_not_a_mismatch(self):
        result = compare_claimed_company("Microsoft internship")
        self.assertFalse(result["flagged"])
        self.assertEqual(result["claimed_company"], "Microsoft")
        self.assertEqual(result["domain"], "")

    def test_sender_domain_is_used_when_there_is_no_link(self):
        match = compare_claimed_company("Microsoft internship", sender="hr@microsoft.com")
        mismatch = compare_claimed_company(
            "Microsoft internship",
            sender="jobs@secure-login.tk",
        )
        self.assertFalse(match["flagged"])
        self.assertEqual(match["source"], "sender")
        self.assertEqual(match["domain"], "microsoft.com")
        self.assertTrue(mismatch["flagged"])
        self.assertEqual(mismatch["reason"], "claimed company does not match sender domain.")
        self.assertEqual(mismatch["domain"], "secure-login.tk")

    def test_explicit_url_is_compared_instead_of_a_link_in_the_text(self):
        result = compare_claimed_company(
            "Microsoft internship. See https://careers.microsoft.com",
            url="http://microsoft.secure-login.tk/offer",
        )
        self.assertTrue(result["flagged"])
        self.assertEqual(result["domain"], "secure-login.tk")

    def test_same_text_is_stable(self):
        text = "Join Microsoft. http://jobs.example/apply"
        self.assertEqual(compare_claimed_company(text), compare_claimed_company(text))

    def test_lowercase_company_is_still_read(self):
        result = compare_claimed_company(
            "infosys internship",
            url="https://www.infosys.com",
        )
        self.assertFalse(result["flagged"])
        self.assertEqual(result["claimed_company"], "infosys")
        self.assertEqual(result["domain"], "infosys.com")


if __name__ == "__main__":
    unittest.main()
