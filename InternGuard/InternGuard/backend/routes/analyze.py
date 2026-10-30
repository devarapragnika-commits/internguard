"""Paste-text and screenshot analysis. Both return the combined risk score."""

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.services.ocr import MAX_IMAGE_BYTES, OcrError, score_screenshot
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


@router.post("/analyze/image")
async def analyze_image(file: UploadFile | None = File(default=None)) -> dict:
    if file is None:
        raise HTTPException(status_code=400, detail="Choose an image before analyzing.")
    content_type = (file.content_type or "").lower()
    if content_type and not content_type.startswith("image/") and content_type != "application/octet-stream":
        raise HTTPException(status_code=400, detail="Upload an image file.")
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Choose an image before analyzing.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="That image is too large.")
    try:
        return score_screenshot(data)
    except OcrError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
