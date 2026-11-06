"""Liveness route used to confirm the API is running."""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from backend.config import ROOT_DIR

router = APIRouter()

def frontend_index():
    for path in (
        ROOT_DIR / "frontend" / "dist" / "index.html",
        ROOT_DIR.parent / "frontend" / "dist" / "index.html",
    ):
        if path.is_file():
            return path
    return None


@router.get("/")
def root():
    index = frontend_index()
    if index is not None:
        return FileResponse(index)
    return {
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
        "analyze": "POST /analyze/text",
        "site": "frontend not built",
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
