"""Liveness route used to confirm the API is running."""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from backend.config import ROOT_DIR

router = APIRouter()

FRONTEND_INDEX = ROOT_DIR / "frontend" / "dist" / "index.html"


@router.get("/")
def root():
    if FRONTEND_INDEX.is_file():
        return FileResponse(FRONTEND_INDEX)
    return {
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
        "analyze": "POST /analyze/text",
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
