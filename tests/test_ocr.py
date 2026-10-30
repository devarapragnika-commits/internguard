"""Checks for screenshot scoring. Tesseract and the network are not called."""

import asyncio
import unittest
from datetime import datetime
from io import BytesIO
from unittest.mock import patch

from fastapi import HTTPException
from PIL import Image, ImageDraw

from backend.routes.analyze import analyze_image
from backend.services import url_features
from backend.services.ocr import OcrError, clean_ocr_text, score_screenshot

FEE_IMAGE = (
    "You are selected for a Microsoft internship. "
    "Kindly pay the registrati0n fee to confirm your place. "
    "Apply at http : / / microsoft . secure-login . tk / offer"
)
UNPAID_IMAGE = (
    "We are pleased to offer you an unpaid software internship. "
    "The stipend is Rs 15000 per month."
)


class _Upload:
    def __init__(self, data: bytes, content_type: str):
        self._data = data
        self.content_type = content_type

    async def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            return self._data
        return self._data[:size]


def _png(words: list[str]) -> bytes:
    image = Image.new("RGB", (640, 200), "white")
    drawing = ImageDraw.Draw(image)
    drawing.text((16, 40), " ".join(words), fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _page(text: str, words: list[str]) -> dict:
    boxes = []
    x = 10
    for word in words:
        boxes.append({"text": word, "x": x, "y": 40, "width": 8 * len(word), "height": 16})
        x += 8 * len(word) + 8
    return {"text": text, "width": 640, "height": 200, "words": boxes}


class OcrCleanupTests(unittest.TestCase):
    def test_broken_line_digit_swap_and_spaced_url_are_repaired(self):
        cleaned = clean_ocr_text(
            "Kindly pay the regis-\ntration fee to confirm your place. "
            "Apply at http : / / microsoft . secure-login . tk / offer"
        )
        self.assertIn("registration fee", cleaned)
        self.assertIn("http://microsoft.secure-login.tk/offer", cleaned)
        self.assertNotIn("regis-", cleaned)

    def test_digit_between_letters_and_spaced_letters_are_repaired(self):
        cleaned = clean_ocr_text("Kindly pay the r e g i s t r a t i 0 n fee.")
        self.assertIn("registration fee", cleaned)

    def test_cleanup_does_not_crash_on_messy_text(self):
        for text in ("", "   ", None, "!!! ???", "pay the 5", 123):
            cleaned = clean_ocr_text(text)
            self.assertIsInstance(cleaned, str)


class ScreenshotScoreTests(unittest.TestCase):
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

    def test_fixture_image_shows_fee_and_lookalike_and_marks_both(self):
        image = _png(["registration", "fee", "http://microsoft.secure-login.tk/offer"])
        self.assertTrue(image.startswith(b"\x89PNG"))
        words = ["Kindly", "pay", "the", "registrati0n", "fee", "http://microsoft.secure-login.tk/offer"]

        def reader(data: bytes) -> dict:
            self.assertTrue(data.startswith(b"\x89PNG"))
            return _page(FEE_IMAGE, words)

        result = score_screenshot(image, reader=reader)
        self.assertIn("score", result)
        self.assertIn("band", result)
        self.assertIn("reasons", result)
        self.assertIn("recommendation", result)
        self.assertIn("slices", result)
        reasons = " ".join(result["reasons"])
        self.assertIn("registration fee", reasons)
        self.assertIn("claimed company does not match link domain.", reasons)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)
        self.assertEqual(result["slices"]["financial_request"]["points"], 25)
        self.assertGreater(result["slices"]["url_domain"]["points"], 0)
        marked = " ".join(box["text"] for box in result["highlights"])
        self.assertIn("registrati0n", marked)
        self.assertIn("fee", marked)
        self.assertIn("secure-login.tk", marked)

    def test_unpaid_fixture_stays_low_with_no_url_risk(self):
        def reader(data: bytes) -> dict:
            return _page(UNPAID_IMAGE, UNPAID_IMAGE.split())

        result = score_screenshot(_png(["unpaid"]), reader=reader)
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["band"], "low")
        self.assertEqual(result["slices"]["url_domain"]["points"], 0)
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["highlights"], [])

    def test_non_image_empty_and_failed_read_do_not_invent_a_score(self):
        with self.assertRaises(OcrError) as rejected:
            score_screenshot(b"this is not an image")
        self.assertEqual(str(rejected.exception), "Upload an image file.")

        with self.assertRaises(OcrError) as empty:
            score_screenshot(b"")
        self.assertEqual(str(empty.exception), "Choose an image before analyzing.")

        def fail(data: bytes) -> dict:
            raise RuntimeError("tesseract down")

        with self.assertRaises(OcrError) as failed:
            score_screenshot(_png(["fee"]), reader=fail)
        self.assertEqual(str(failed.exception), "Could not read text from this image.")

        def blank(data: bytes) -> dict:
            return _page("   \n", [])

        with self.assertRaises(OcrError) as no_text:
            score_screenshot(_png(["blank"]), reader=blank)
        self.assertEqual(str(no_text.exception), "No text was found in this image.")

    def test_route_rejects_a_text_file_and_scores_a_png(self):
        with self.assertRaises(HTTPException) as rejected:
            asyncio.run(analyze_image(_Upload(b"hello", "text/plain")))
        self.assertEqual(rejected.exception.status_code, 400)
        self.assertEqual(rejected.exception.detail, "Upload an image file.")

        image = _png(["fee"])

        def reader(data: bytes) -> dict:
            return _page(FEE_IMAGE, ["registrati0n", "fee", "http://microsoft.secure-login.tk/offer"])

        with patch("backend.services.ocr.read_image", reader):
            result = asyncio.run(analyze_image(_Upload(image, "image/png")))
        self.assertEqual(result["slices"]["financial_request"]["points"], 25)
        self.assertIn("claimed company does not match link domain.", result["reasons"])
        self.assertIn("score", result)
        self.assertIn("band", result)
