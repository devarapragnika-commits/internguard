"""Liveness route used to confirm the API is running."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def root() -> dict[str, str]:
    return {
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
        "analyze": "POST /analyze/text",
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
