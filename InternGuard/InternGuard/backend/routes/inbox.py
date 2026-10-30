"""Sandbox inbox list. Fixtures only; no personal mailbox."""

from fastapi import APIRouter

from backend.services.inbox import list_inbox

router = APIRouter()


@router.get("/inbox")
def inbox_list() -> dict:
    return list_inbox()
