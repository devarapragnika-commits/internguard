"""Checks for listing text sent to score_message. No job-board account is used."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.routes.analyze import AnalyzeTextBody, analyze_text
from backend.services import url_features
from backend.services.listing import (
    LEGIT_LISTING_BODY,
    LEGIT_LISTING_TITLE,
    SCAM_LISTING_BODY,
    SCAM_LISTING_TITLE,
    extract_listing_text,
    listing_text_for_score,
)
from backend.services.risk import score_message

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
EXTENSION = ROOT / "extension"
FRONTEND_APP = ROOT / "frontend" / "src" / "App.jsx"


class ListingExtractTests(unittest.TestCase):
    def test_linkedin_fixture_text_matches_the_visible_post(self):
        html = (FIXTURES / "linkedin_scam.html").read_text(encoding="utf-8")
        text = extract_listing_text(html)
        expected = listing_text_for_score(title=SCAM_LISTING_TITLE, body=SCAM_LISTING_BODY)
        self.assertEqual(text, expected)
        self.assertIn("registration fee", text)
        self.assertNotIn("LinkedIn Home", text)
        self.assertNotIn("do-not-read", text)

    def test_indeed_fixture_uses_the_same_listing_text(self):
        html = (FIXTURES / "indeed_scam.html").read_text(encoding="utf-8")
        text = extract_listing_text(html)
        expected = listing_text_for_score(title=SCAM_LISTING_TITLE, body=SCAM_LISTING_BODY)
        self.assertEqual(text, expected)

    def test_open_linkedin_message_is_read_without_a_login_scrape(self):
        html = (FIXTURES / "linkedin_message.html").read_text(encoding="utf-8")
        text = extract_listing_text(html)
        self.assertIn("registration fee", text)
        self.assertIn("Microsoft Careers", text)
        self.assertNotIn("Messaging", text)

    def test_legit_careers_fixture_omits_chrome_and_keeps_the_offer(self):
        html = (FIXTURES / "linkedin_legit.html").read_text(encoding="utf-8")
        text = extract_listing_text(html)
        expected = listing_text_for_score(title=LEGIT_LISTING_TITLE, body=LEGIT_LISTING_BODY)
        self.assertEqual(text, expected)
        self.assertIn("unpaid software internship", text)
        self.assertNotIn("Messaging", text)


class ListingScoreTests(unittest.TestCase):
    def setUp(self):
        self.redirect_patch = patch.object(
            url_features,
            "_lookup_redirects",
            side_effect=lambda url, timeout: {"length": 0, "destination": url},
        )
        self.redirect_patch.start()
        self.addCleanup(self.redirect_patch.stop)

    def test_extracted_text_scores_the_same_as_pasting(self):
        html = (FIXTURES / "linkedin_scam.html").read_text(encoding="utf-8")
        text = extract_listing_text(html)
        pasted = score_message(text)
        routed = analyze_text(AnalyzeTextBody(text=text))
        self.assertEqual(pasted["score"], routed["score"])
        self.assertEqual(pasted["band"], routed["band"])
        self.assertEqual(pasted["reasons"], routed["reasons"])
        self.assertEqual(pasted["recommendation"], routed["recommendation"])
        self.assertGreater(pasted["score"], 0)

    def test_http_analyze_text_matches_score_message_for_the_fixture(self):
        from backend.main import app

        text = extract_listing_text((FIXTURES / "linkedin_scam.html").read_text(encoding="utf-8"))
        client = TestClient(app)
        response = client.post("/analyze/text", json={"text": text})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        expected = score_message(text)
        self.assertEqual(body["score"], expected["score"])
        self.assertEqual(body["band"], expected["band"])
        self.assertEqual(body["reasons"], expected["reasons"])

    def test_legitimate_careers_post_stays_low(self):
        html = (FIXTURES / "linkedin_legit.html").read_text(encoding="utf-8")
        text = extract_listing_text(html)
        result = score_message(text)
        self.assertEqual(result["band"], "low")
        self.assertEqual(result["recommendation"], "Proceed with normal caution.")


class ListingExtensionTests(unittest.TestCase):
    def test_extension_reads_the_open_page_and_does_not_store_it(self):
        listing = (EXTENSION / "listing.js").read_text(encoding="utf-8")
        popup = (EXTENSION / "popup.js").read_text(encoding="utf-8")
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        scripts = {item["js"][0]: item["matches"] for item in manifest["content_scripts"]}
        self.assertIn("listing.js", scripts)
        self.assertIn("https://www.linkedin.com/*", scripts["listing.js"])
        self.assertIn("https://www.indeed.com/*", scripts["listing.js"])
        self.assertIn("get-listing-text", listing)
        self.assertIn("/analyze/text", popup)
        self.assertNotIn("localStorage", listing)
        self.assertNotIn("chrome.storage", listing)
        self.assertNotIn("chrome.storage", popup)
        blob = f"{listing}\n{popup}".lower()
        for forbidden in ("voyager", "linkedin.com/voyager", "apply now request", "oauth"):
            self.assertNotIn(forbidden, blob)

    def test_listing_script_does_not_scan_until_the_popup_asks(self):
        listing = (EXTENSION / "listing.js").read_text(encoding="utf-8")
        self.assertNotIn("score-list", listing)
        self.assertNotIn("/analyze/text", listing)
        self.assertIn("onMessage.addListener", listing)

    def test_analyze_page_is_unchanged(self):
        app = FRONTEND_APP.read_text(encoding="utf-8")
        self.assertIn("/analyze/text", app)
        self.assertNotIn("get-listing-text", app)
        self.assertNotIn("extract_listing_text", app)
        self.assertNotIn("listing.js", app)
