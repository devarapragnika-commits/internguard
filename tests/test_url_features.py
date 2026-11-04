"""Checks for the URL feature extractor. Network lookups are mocked."""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from backend.services import url_features
from backend.services.url_features import extract_url_features

NORMAL = "https://www.example.com/jobs/intern"
SUSPICIOUS = "http://paypal.com.secure-login.tk/offer"


class UrlFeatureTests(unittest.TestCase):
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

    def test_normal_and_suspicious_urls_differ(self):
        normal = extract_url_features(NORMAL)
        suspicious = extract_url_features(SUSPICIOUS)

        self.assertTrue(normal["https"]["value"])
        self.assertFalse(normal["suspicious_tld"]["value"])
        self.assertEqual(normal["suspicious_tld"]["tld"], "com")
        self.assertEqual(normal["subdomain_count"]["value"], 1)

        self.assertFalse(suspicious["https"]["value"])
        self.assertTrue(suspicious["suspicious_tld"]["value"])
        self.assertEqual(suspicious["suspicious_tld"]["tld"], "tk")
        self.assertGreater(suspicious["subdomain_count"]["value"], 1)
        self.assertNotEqual(normal, suspicious)

    def test_same_url_is_stable_for_local_features(self):
        first = extract_url_features(NORMAL)
        second = extract_url_features(NORMAL)
        self.assertEqual(first, second)

    def test_empty_and_invalid_urls_do_not_crash(self):
        for url in ("", "   ", None, "not a url", "javascript:alert(1)", 123):
            features = extract_url_features(url)
            self.assertIn(features["https"]["value"], (True, False))
            self.assertIn(features["domain_age"]["status"], ("ok", "unknown"))
            self.assertIn(features["redirects"]["status"], ("ok", "unknown"))

    def test_whois_timeout_is_unknown(self):
        def slow(domain, timeout):
            import time

            time.sleep(1)
            return datetime(2020, 1, 1)

        with patch.object(url_features, "_lookup_whois", slow):
            features = extract_url_features(NORMAL, timeout=0.1)
        self.assertEqual(features["domain_age"]["status"], "unknown")
        self.assertEqual(features["domain_age"]["error"], "timed out")
        self.assertIsNone(features["domain_age"]["days"])
        self.assertTrue(features["https"]["value"])

    def test_whois_exception_is_unknown(self):
        with patch.object(url_features, "_lookup_whois", side_effect=RuntimeError("down")):
            features = extract_url_features(NORMAL)
        self.assertEqual(features["domain_age"]["status"], "unknown")
        self.assertEqual(features["domain_age"]["error"], "lookup failed")

    def test_missing_creation_date_is_unknown(self):
        with patch.object(url_features, "_lookup_whois", return_value=None):
            features = extract_url_features(NORMAL)
        self.assertEqual(features["domain_age"]["error"], "creation date missing")

    def test_earliest_whois_date_is_used(self):
        dates = [datetime(2024, 1, 1), datetime(2019, 5, 2)]
        with patch.object(url_features, "_lookup_whois", return_value=dates):
            features = extract_url_features(NORMAL)
        self.assertEqual(features["domain_age"]["status"], "ok")
        self.assertEqual(features["domain_age"]["created"], "2019-05-02")
        self.assertGreater(features["domain_age"]["days"], 0)

    def test_redirect_timeout_is_unknown(self):
        def slow(url, timeout):
            import time

            time.sleep(1)
            return {"length": 1, "destination": url}

        with patch.object(url_features, "_lookup_redirects", slow):
            features = extract_url_features(NORMAL, timeout=0.1)
        self.assertEqual(features["redirects"]["status"], "unknown")
        self.assertEqual(features["redirects"]["error"], "timed out")
        self.assertIsNone(features["redirects"]["length"])
        self.assertIsNone(features["redirects"]["destination"])

    def test_redirect_chain_is_reported(self):
        def chain(url, timeout):
            return {"length": 2, "destination": "https://example.com/final"}

        with patch.object(url_features, "_lookup_redirects", chain):
            features = extract_url_features(SUSPICIOUS)
        self.assertEqual(features["redirects"]["status"], "ok")
        self.assertEqual(features["redirects"]["length"], 2)
        self.assertEqual(features["redirects"]["destination"], "https://example.com/final")

    def test_redirect_lookup_stops_after_five(self):
        def hop(url, timeout):
            return 302, "https://cdn.example/next"

        self.redirect_patch.stop()
        try:
            with patch.object(url_features, "_request_hop", hop):
                with patch.object(url_features, "_ensure_public_http_url", lambda url: None):
                    found = url_features._lookup_redirects("https://example.com/start", 1)
        finally:
            self.redirect_patch.start()
        self.assertEqual(found["length"], 5)
        self.assertEqual(found["destination"], "https://cdn.example/next")

    def test_private_address_is_not_fetched(self):
        def fail(url, timeout):
            raise AssertionError(f"fetched {url}")

        self.redirect_patch.stop()
        try:
            with patch.object(url_features, "_request_hop", fail):
                for url in ("http://127.0.0.1/secret", "http://169.254.169.254/", "http://2130706433/"):
                    features = extract_url_features(url)
                    self.assertEqual(features["redirects"]["status"], "unknown", url)
                    self.assertEqual(features["redirects"]["error"], "blocked address", url)
                    self.assertEqual(features["domain_age"]["error"], "no domain", url)
        finally:
            self.redirect_patch.start()

    def test_suspicious_tld_list_is_in_the_repo(self):
        path = Path("backend/data/suspicious_tlds.txt")
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8").lower()
        self.assertIn("\ntk\n", f"\n{text}\n")
        self.assertNotIn("\ncom\n", f"\n{text}\n")

    def test_edited_tld_list_is_used(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tlds.txt"
            path.write_text("# comment\ncom\n", encoding="utf-8")
            features = extract_url_features(NORMAL, tld_path=path)
        self.assertTrue(features["suspicious_tld"]["value"])
        self.assertEqual(features["suspicious_tld"]["tld"], "com")

    def test_virustotal_stays_off_without_a_key(self):
        def fail(domain, api_key, timeout):
            raise AssertionError("VirusTotal was called")

        with patch.dict(os.environ, {"VIRUSTOTAL_API_KEY": ""}, clear=False):
            with patch.object(url_features, "_lookup_virustotal", fail):
                features = extract_url_features(NORMAL)
        self.assertEqual(features["virustotal"]["status"], "off")
        self.assertIsNone(features["virustotal"]["malicious"])

    def test_virustotal_timeout_is_unknown(self):
        def slow(domain, api_key, timeout):
            import time

            time.sleep(1)
            return {"malicious": 1, "suspicious": 0}

        with patch.dict(os.environ, {"VIRUSTOTAL_API_KEY": "test-key"}, clear=False):
            with patch.object(url_features, "_lookup_virustotal", slow):
                features = extract_url_features(NORMAL, timeout=0.1)
        self.assertEqual(features["virustotal"]["status"], "unknown")
        self.assertEqual(features["virustotal"]["error"], "timed out")

    def test_virustotal_stats_when_a_key_is_set(self):
        def stats(domain, api_key, timeout):
            self.assertEqual(api_key, "test-key")
            self.assertEqual(domain, "example.com")
            return {"malicious": 4, "suspicious": 1}

        with patch.dict(os.environ, {"VIRUSTOTAL_API_KEY": "test-key"}, clear=False):
            with patch.object(url_features, "_lookup_virustotal", stats):
                features = extract_url_features(NORMAL)
        self.assertEqual(features["virustotal"]["status"], "ok")
        self.assertEqual(features["virustotal"]["malicious"], 4)
        self.assertEqual(features["virustotal"]["suspicious"], 1)


if __name__ == "__main__":
    unittest.main()
