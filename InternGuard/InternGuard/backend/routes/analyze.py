"""Paste-text analysis. One call returns the combined text and URL score."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.risk import score_message

router = APIRouter()


class AnalyzeTextBody(BaseModel):
    text: str = ""


@router.post("/analyze/text")
def analyze_text(body: AnalyzeTextBody) -> dict:
    message = body.text.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Paste a message before analyzing.")
    return score_message(message)
