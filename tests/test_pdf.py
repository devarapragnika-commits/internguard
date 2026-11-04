"""PDF offer-letter scoring. JavaScript is not run and no paid API is called."""

import asyncio
import inspect
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.routes.analyze import analyze_pdf
from backend.services import pdf_offer, url_features
from backend.services.pdf_offer import PdfError, extract_pdf_content, score_pdf

FEE_TEXT = (
    "You are selected for a Microsoft internship. "
    "Kindly pay the registration fee to confirm your place."
)
UNPAID_TEXT = (
    "We are pleased to offer you an unpaid software internship. "
    "There is no registration fee. The stipend is Rs 15000 per month."
)
LOOKALIKE = "http://microsoft.secure-login.tk/offer"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


class _Upload:
    def __init__(self, data: bytes, content_type: str, filename: str = "offer.pdf"):
        self._data = data
        self.content_type = content_type
        self.filename = filename

    async def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            return self._data
        return self._data[:size]


def make_pdf(text: str, uri: str | None = None, javascript: str | None = None) -> bytes:
    """Build a small one-page PDF. Optional URI annot; JS is stored, not run."""
    escaped = (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\r", " ")
        .replace("\n", ") Tj 0 -16 Td (")
    )
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1", "replace")
    annot = ""
    js_obj = ""
    page_extra = ""
    catalog_extra = ""
    if uri:
        annot = (
            "6 0 obj<< /Type /Annot /Subtype /Link /Rect [72 700 400 740] /Border [0 0 0] "
            f"/A << /S /URI /URI ({_escape_pdf(uri)}) >> >>endobj\n"
        )
        page_extra = " /Annots [6 0 R]"
    if javascript:
        js_obj = (
            "7 0 obj<< /S /JavaScript /JS ("
            f"{_escape_pdf(javascript)}"
            ") >>endobj\n"
        )
        catalog_extra = " /OpenAction 7 0 R"
    objects = [
        f"1 0 obj<< /Type /Catalog /Pages 2 0 R{catalog_extra} >>endobj\n".encode(),
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        (
            "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >>{page_extra} >>endobj\n"
        ).encode(),
        b"4 0 obj<< /Length "
        + str(len(stream)).encode()
        + b" >>stream\n"
        + stream
        + b"\nendstream\nendobj\n",
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    if annot:
        objects.append(annot.encode())
    if js_obj:
        objects.append(js_obj.encode())
    body = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(body))
        body += obj
    xref_at = len(body)
    count = len(objects) + 1
    xref = [f"xref\n0 {count}\n0000000000 65535 f \n".encode()]
    for offset in offsets[1:]:
        xref.append(f"{offset:010d} 00000 n \n".encode())
    tail = (
        b"".join(xref)
        + f"trailer<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    )
    return body + tail


def _escape_pdf(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_fixtures() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    (FIXTURE_DIR / "fee_offer.pdf").write_bytes(make_pdf(FEE_TEXT, LOOKALIKE))
    (FIXTURE_DIR / "unpaid_offer.pdf").write_bytes(make_pdf(UNPAID_TEXT))


write_fixtures()


class PdfScoreTests(unittest.TestCase):
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

    def test_fee_fixture_pdf_matches_pasted_fee(self):
        data = (FIXTURE_DIR / "fee_offer.pdf").read_bytes()
        self.assertTrue(data.startswith(b"%PDF-"))
        result = score_pdf(data)
        pasted = __import__("backend.services.risk", fromlist=["score_message"]).score_message(
            FEE_TEXT + " " + LOOKALIKE
        )
        self.assertEqual(result["slices"]["financial_request"]["points"], 25)
        self.assertEqual(
            result["slices"]["financial_request"]["points"],
            pasted["slices"]["financial_request"]["points"],
        )
        self.assertIn("registration fee", " ".join(result["reasons"]))
        self.assertIn("claimed company does not match link domain.", result["reasons"])
        self.assertIn(result["band"], ("medium", "high"))
        self.assertIn("registration fee", result["text"])
        self.assertIn("score", result)
        self.assertIn("recommendation", result)

    def test_unpaid_fixture_pdf_stays_low(self):
        result = score_pdf((FIXTURE_DIR / "unpaid_offer.pdf").read_bytes())
        self.assertEqual(result["slices"]["financial_request"]["points"], 0)
        self.assertEqual(result["band"], "low")
        self.assertEqual(result["score"], 0)

    def test_link_uri_is_scored_even_if_missing_from_visible_text(self):
        data = make_pdf("You are selected for a Microsoft internship.", LOOKALIKE)
        _text, links = extract_pdf_content(data)
        self.assertIn(LOOKALIKE, links)
        result = score_pdf(data)
        self.assertGreater(result["slices"]["url_domain"]["points"], 0)
        self.assertIn("claimed company does not match link domain.", result["reasons"])

    def test_javascript_is_not_treated_as_message_text(self):
        data = make_pdf(
            UNPAID_TEXT,
            javascript="app.alert('Kindly pay the registration fee');",
        )
        result = score_pdf(data)
        self.assertEqual(result["slices"]["financial_request"]["points"], 0)
        self.assertEqual(result["band"], "low")

    def test_non_pdf_empty_and_blank_do_not_invent_a_score(self):
        with self.assertRaises(PdfError) as rejected:
            score_pdf(b"this is not a pdf")
        self.assertEqual(str(rejected.exception), "Upload a PDF file.")
        with self.assertRaises(PdfError) as empty:
            score_pdf(b"")
        self.assertEqual(str(empty.exception), "Choose a PDF before analyzing.")
        with self.assertRaises(PdfError) as blank:
            score_pdf(make_pdf("   "))
        self.assertEqual(str(blank.exception), "No text was found in this PDF.")

    def test_route_rejects_a_text_file_and_scores_a_pdf(self):
        with self.assertRaises(HTTPException) as rejected:
            asyncio.run(analyze_pdf(_Upload(b"hello", "text/plain", "note.txt")))
        self.assertEqual(rejected.exception.status_code, 400)
        self.assertEqual(rejected.exception.detail, "Upload a PDF file.")
        result = asyncio.run(
            analyze_pdf(_Upload((FIXTURE_DIR / "fee_offer.pdf").read_bytes(), "application/pdf"))
        )
        self.assertEqual(result["slices"]["financial_request"]["points"], 25)

    def test_does_not_fetch_remote_images_or_run_a_paid_api(self):
        source = inspect.getsource(pdf_offer)
        self.assertNotIn("httpx", source)
        self.assertNotIn("urllib", source)
        self.assertNotIn("requests", source)
        self.assertNotIn("openai", source.lower())
        self.assertNotIn("openrouter", source.lower())
        self.assertIn("not executed", (inspect.getdoc(pdf_offer) or "").lower())


if __name__ == "__main__":
    unittest.main()
