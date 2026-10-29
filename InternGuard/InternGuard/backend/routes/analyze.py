"""Paste-text analysis. Currently returns the payment-request score."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.payment import detect_payment_request

router = APIRouter()


class AnalyzeTextBody(BaseModel):
    text: str = ""


@router.post("/analyze/text")
def analyze_text(body: AnalyzeTextBody) -> dict:
    message = body.text.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Paste a message before analyzing.")
    return detect_payment_request(message)
