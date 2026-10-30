"""Score the three demo messages on text, link, screenshot, and email.

URL lookups are stubbed so the printed scores can be regenerated offline.
Screenshot scoring uses a generated PNG. If Tesseract is missing, that
channel is recorded as skipped instead of inventing a score.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from backend.ml.train_baselines import DEFAULT_DATA_PATH, dataset_version, load_messages
from backend.services import url_features
from backend.services.mail import score_email
from backend.services.ocr import OcrError, score_screenshot
from backend.services.risk import score_message
from demos.messages import DEMOS, email_source

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "demos"


def _png(text: str) -> bytes:
    image = Image.new("RGB", (900, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.multiline_text((16, 16), text, fill="black", spacing=8)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _summary(result: dict) -> dict:
    return {
        "score": result["score"],
        "band": result["band"],
        "reasons": result["reasons"],
        "recommendation": result["recommendation"],
    }


def run_demo() -> dict:
    rows = []
    with patch.object(url_features, "_lookup_whois", return_value=datetime(2018, 1, 15)):
        with patch.object(
            url_features,
            "_lookup_redirects",
            side_effect=lambda url, timeout: {"length": 0, "destination": url},
        ):
            for demo in DEMOS:
                text = demo["text"]
                text_result = score_message(text)
                email_result = score_email(email_source(text, demo["id"]))
                screenshot: dict[str, object]
                try:
                    screenshot = _summary(score_screenshot(_png(text)))
                    screenshot["status"] = "ok"
                except OcrError as exc:
                    screenshot = {"status": "skipped", "detail": str(exc)}
                rows.append(
                    {
                        "id": demo["id"],
                        "text": text,
                        "channels": {
                            "text": _summary(text_result),
                            "link": _summary(text_result),
                            "screenshot": screenshot,
                            "email": _summary(email_result),
                        },
                    }
                )
    frame = load_messages(DEFAULT_DATA_PATH)
    payload = {
        "dataset_version": dataset_version(DEFAULT_DATA_PATH, len(frame)),
        "n_demo_messages": len(rows),
        "results": rows,
    }
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    (DEMO_DIR / "last_run.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    expected = {
        item["id"]: {
            "expected_band": item["channels"]["text"]["band"],
            "text": item["text"],
        }
        for item in rows
    }
    (DEMO_DIR / "expected.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    for demo in DEMOS:
        (DEMO_DIR / f"{demo['id']}.eml").write_text(
            email_source(demo["text"], demo["id"]),
            encoding="utf-8",
        )
        (DEMO_DIR / f"{demo['id']}.txt").write_text(demo["text"] + "\n", encoding="utf-8")
    return payload


def main() -> None:
    payload = run_demo()
    for item in payload["results"]:
        print(item["id"])
        for channel, result in item["channels"].items():
            if result.get("status") == "skipped":
                print(f"  {channel}: skipped ({result.get('detail')})")
                continue
            reasons = "; ".join(result.get("reasons") or []) or "none"
            print(f"  {channel}: {result['score']}/100 {result['band']} | {reasons}")
    print(f"Wrote {DEMO_DIR / 'expected.json'}")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
