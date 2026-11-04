"""Checks for Gmail list badges from already-loaded metadata. No mailbox is opened."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.routes.analyze import AnalyzeListBody, AnalyzeListMessage, analyze_list
from backend.services.gmail_list import (
    DEMO_LIST_MESSAGES,
    MAX_LIST_MESSAGES,
    parse_gmail_list_html,
    score_list_messages,
    score_list_metadata,
)
from backend.services import url_features
from backend.services.mail import score_email
from backend.services.risk import HIGH_AT, MEDIUM_AT

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "tests" / "fixtures" / "gmail_list.html").read_text(encoding="utf-8")
EXTENSION = ROOT / "extension"


class GmailListParserTests(unittest.TestCase):
    def test_parser_reads_subject_sender_and_snippet_from_list_markup(self):
        rows = parse_gmail_list_html(HTML)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["from_name"], "Microsoft Careers")
        self.assertEqual(rows[0]["from_address"], "offers@gmail.com")
        self.assertEqual(rows[0]["subject"], "Microsoft internship — act now")
        self.assertIn("registration fee", rows[0]["snippet"])
        self.assertIn("microsoft.secure-login.tk", rows[0]["snippet"])
        self.assertEqual(rows[1]["subject"], "Registration fee for onboarding")
        self.assertEqual(rows[2]["from_address"], "jobs@careers.microsoft.com")
        self.assertEqual(rows[2]["subject"], "Internship next steps")

    def test_parser_does_not_keep_or_fetch_remote_images(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("urlopen")):
            with patch("http.client.HTTPConnection", side_effect=AssertionError("http")):
                with patch("http.client.HTTPSConnection", side_effect=AssertionError("https")):
                    rows = parse_gmail_list_html(HTML)
        blob = json.dumps(rows).lower()
        self.assertNotIn("evil.example", blob)
        self.assertNotIn("pixel.png", blob)
        self.assertNotIn("open.gif", blob)
        self.assertNotIn("<img", blob)
        for row in rows:
            self.assertNotIn("body", row)
            self.assertNotIn("html", row)
            self.assertNotIn("raw", row)


class _StubRedirects:
    def setUp(self):
        self.redirect_patch = patch.object(
            url_features,
            "_lookup_redirects",
            side_effect=lambda url, timeout: {"length": 0, "destination": url},
        )
        self.redirect_patch.start()
        self.addCleanup(self.redirect_patch.stop)


class GmailListScoreTests(_StubRedirects, unittest.TestCase):
    def test_high_row_stays_high_when_url_lookups_do_not_finish(self):
        with patch("backend.services.risk._url_risk", return_value=(0, [], [])):
            row = score_list_metadata(
                from_name=DEMO_LIST_MESSAGES[0]["from_name"],
                from_address=DEMO_LIST_MESSAGES[0]["from_address"],
                subject=DEMO_LIST_MESSAGES[0]["subject"],
                snippet=DEMO_LIST_MESSAGES[0]["snippet"],
            )
        self.assertEqual(row["band"], "high")
        self.assertGreaterEqual(row["score"], HIGH_AT)

    def test_unopened_list_rows_show_high_medium_and_low(self):
        rows = score_list_messages(DEMO_LIST_MESSAGES)["messages"]
        self.assertEqual(len(rows), 3)
        self.assertEqual({row["band"] for row in rows}, {"high", "medium", "low"})
        self.assertEqual(rows[0]["band"], "high")
        self.assertEqual(rows[1]["band"], "medium")
        self.assertEqual(rows[2]["band"], "low")

    def test_badge_uses_the_same_bands_as_score_message(self):
        rows = score_list_messages(DEMO_LIST_MESSAGES)["messages"]
        parsed = parse_gmail_list_html(HTML)
        self.assertEqual(len(parsed), 3)
        for row, item, html_row in zip(rows, DEMO_LIST_MESSAGES, parsed):
            scored = score_list_metadata(
                from_name=item["from_name"],
                from_address=item["from_address"],
                subject=item["subject"],
                snippet=item["snippet"],
            )
            emailed = score_email(
                headers=(
                    f'From: "{item["from_name"]}" <{item["from_address"]}>\r\n'
                    f'Subject: {item["subject"]}\r\n'
                ),
                snippet=item["snippet"],
            )
            self.assertEqual(row["score"], scored["score"])
            self.assertEqual(row["band"], scored["band"])
            self.assertEqual(row["reasons"], scored["reasons"])
            self.assertEqual(row["score"], emailed["score"])
            self.assertEqual(row["band"], emailed["band"])
            self.assertEqual(html_row["subject"], item["subject"])
            if row["score"] >= HIGH_AT:
                self.assertEqual(row["band"], "high")
            elif row["score"] >= MEDIUM_AT:
                self.assertEqual(row["band"], "medium")
            else:
                self.assertEqual(row["band"], "low")

    def test_html_fixture_scores_the_same_bands(self):
        parsed = parse_gmail_list_html(HTML)
        rows = score_list_messages(parsed)["messages"]
        self.assertEqual([row["band"] for row in rows], ["high", "medium", "low"])

    def test_list_scoring_does_not_fetch_full_message_bodies(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("urlopen")):
            rows = score_list_messages(
                [
                    {
                        "from_name": "Hiring Desk",
                        "from_address": "desk@campus-jobs.example",
                        "subject": "Registration fee for onboarding",
                        "snippet": "Kindly pay the registration fee to confirm your place.",
                    }
                ]
            )["messages"]
        self.assertEqual(rows[0]["band"], "medium")


class GmailListRouteTests(_StubRedirects, unittest.TestCase):
    def test_analyze_list_returns_the_same_score_as_the_helper(self):
        body = AnalyzeListBody(
            messages=[AnalyzeListMessage(**item) for item in DEMO_LIST_MESSAGES]
        )
        result = analyze_list(body)
        expected = score_list_messages(DEMO_LIST_MESSAGES)
        self.assertEqual(result["messages"][0]["score"], expected["messages"][0]["score"])
        self.assertEqual([row["band"] for row in result["messages"]], ["high", "medium", "low"])

    def test_route_rejects_an_empty_list(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as raised:
            analyze_list(AnalyzeListBody(messages=[]))
        self.assertEqual(raised.exception.status_code, 400)

    def test_route_rejects_too_many_messages(self):
        from fastapi import HTTPException

        extra = [
            AnalyzeListMessage(subject=f"row {index}", snippet="hello")
            for index in range(MAX_LIST_MESSAGES + 1)
        ]
        with self.assertRaises(HTTPException) as raised:
            analyze_list(AnalyzeListBody(messages=extra))
        self.assertEqual(raised.exception.status_code, 400)

    def test_http_batch_avoids_one_request_per_row(self):
        from backend.main import app

        client = TestClient(app)
        response = client.post("/analyze/list", json={"messages": DEMO_LIST_MESSAGES})
        self.assertEqual(response.status_code, 200)
        bands = [row["band"] for row in response.json()["messages"]]
        self.assertEqual(bands, ["high", "medium", "low"])


class GmailListExtensionTests(unittest.TestCase):
    def test_extension_requests_no_send_or_modify_scopes(self):
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        blob = " ".join(
            [
                json.dumps(manifest),
                (EXTENSION / "content.js").read_text(encoding="utf-8"),
                (EXTENSION / "background.js").read_text(encoding="utf-8"),
                (EXTENSION / "popup.js").read_text(encoding="utf-8"),
            ]
        ).lower()
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["host_permissions"], ["http://127.0.0.1:8000/*", "http://localhost:8000/*"])
        self.assertNotIn("identity", manifest.get("permissions", []))
        gmail_script = next(
            item for item in manifest["content_scripts"] if "content.js" in item.get("js", [])
        )
        self.assertEqual(gmail_script["matches"], ["https://mail.google.com/*"])
        self.assertEqual(manifest["background"]["service_worker"], "background.js")
        for forbidden in (
            "gmail.send",
            "gmail.modify",
            "gmail.googleapis.com",
            "users.messages",
            "format=full",
            "oauth2",
            "https://mail.google.com/mail",
        ):
            self.assertNotIn(forbidden, blob)

    def test_content_script_does_not_load_remote_images_or_full_bodies(self):
        content = (EXTENSION / "content.js").read_text(encoding="utf-8")
        background = (EXTENSION / "background.js").read_text(encoding="utf-8")
        self.assertNotIn("createElement('img')", content)
        self.assertNotIn('createElement("img")', content)
        self.assertNotIn(".src =", content)
        self.assertNotIn("users.messages.get", content)
        self.assertNotIn("format=full", content)
        self.assertIn("/analyze/list", background)
        self.assertIn("score-list", content)
        self.assertIn("get-gmail-rows", content)

    def test_sandbox_popup_still_loads_fixtures(self):
        popup = (EXTENSION / "popup.js").read_text(encoding="utf-8")
        html = (EXTENSION / "popup.html").read_text(encoding="utf-8")
        self.assertIn("/inbox", popup)
        self.assertIn("Sandbox fixtures", html)
        self.assertIn("gmail-list", html)
