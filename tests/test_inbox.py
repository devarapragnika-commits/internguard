"""Checks for the pre-open inbox badge. No mailbox is opened."""

import json
import unittest
from unittest.mock import patch

from backend.routes.inbox import inbox_list
from backend.services import url_features
from backend.services.inbox import FIXTURES, list_inbox, score_inbox_row
from backend.services.mail import score_email
from backend.services.risk import HIGH_AT, MEDIUM_AT


class InboxBadgeTests(unittest.TestCase):
    def test_demo_inbox_shows_high_medium_and_low_on_unopened_rows(self):
        rows = list_inbox()["messages"]
        self.assertEqual(len(rows), 3)
        bands = {row["band"] for row in rows}
        self.assertEqual(bands, {"high", "medium", "low"})
        for row in rows:
            self.assertTrue(row["unread"])
            self.assertIn(row["band"], {"high", "medium", "low"})
            self.assertGreaterEqual(row["score"], 0)
            self.assertLessEqual(row["score"], 100)

    def test_badge_uses_the_same_bands_as_score_message(self):
        for item in FIXTURES:
            row = score_inbox_row(item)
            scored = score_email(
                headers=item["headers"],
                snippet=item["snippet"],
                attachments=item["attachments"],
            )
            self.assertEqual(row["score"], scored["score"])
            self.assertEqual(row["band"], scored["band"])
            self.assertEqual(row["reasons"], scored["reasons"])
            self.assertEqual(row["recommendation"], scored["recommendation"])
            if row["score"] >= HIGH_AT:
                self.assertEqual(row["band"], "high")
            elif row["score"] >= MEDIUM_AT:
                self.assertEqual(row["band"], "medium")
            else:
                self.assertEqual(row["band"], "low")

    def test_high_row_reasons_include_sender_and_attachment_flags(self):
        row = next(item for item in list_inbox()["messages"] if item["band"] == "high")
        reasons = " ".join(row["reasons"])
        self.assertIn("registration fee", reasons)
        self.assertIn("Sender failed the DKIM check.", row["reasons"])
        self.assertIn("Attachment uses a double extension such as pdf.exe.", row["reasons"])
        self.assertGreater(row["slices"]["sender_authenticity"]["points"], 0)
        self.assertGreater(row["slices"]["attachment"]["points"], 0)

    def test_message_with_no_risk_signals_stays_low(self):
        row = next(item for item in list_inbox()["messages"] if item["id"] == "low-unpaid-offer")
        self.assertEqual(row["band"], "low")
        self.assertEqual(row["score"], 0)
        self.assertEqual(row["slices"]["sender_authenticity"]["points"], 0)
        self.assertEqual(row["slices"]["attachment"]["points"], 0)
        self.assertEqual(row["reasons"], [])
        self.assertEqual(row["recommendation"], "Proceed with normal caution.")

    def test_fixtures_have_no_body_and_no_remote_content(self):
        blob = json.dumps(FIXTURES).lower()
        self.assertNotIn("<img", blob)
        self.assertNotIn("http://", blob)
        self.assertNotIn("https://", blob)
        self.assertNotIn("cid:", blob)
        for item in FIXTURES:
            self.assertNotIn("body", item)
            self.assertNotIn("html", item)
            self.assertNotIn("raw", item)

    def test_list_view_does_not_fetch_remote_message_content(self):
        with patch.object(url_features, "_lookup_whois", side_effect=AssertionError("whois")):
            with patch.object(url_features, "_lookup_redirects", side_effect=AssertionError("redirects")):
                rows = list_inbox()["messages"]
        self.assertEqual(len(rows), 3)

    def test_route_returns_the_sandbox_list(self):
        result = inbox_list()
        self.assertEqual(len(result["messages"]), 3)
        ids = [row["id"] for row in result["messages"]]
        self.assertEqual(
            ids,
            ["high-fee-double-extension", "medium-auth-and-attachment", "low-unpaid-offer"],
        )
