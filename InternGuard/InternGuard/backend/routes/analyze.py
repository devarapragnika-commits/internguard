"""Text analysis route."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.text_score import score_text

router = APIRouter()


class AnalyzeTextRequest(BaseModel):
    text: str = Field(min_length=1)


@router.post("/analyze/text")
def analyze_text(body: AnalyzeTextRequest) -> dict[str, object]:
    message = body.text.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message text is required.")
    return score_text(message)
