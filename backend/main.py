"""InternGuard HTTP API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.analyze import router as analyze_router
from backend.routes.health import router as health_router
from backend.routes.inbox import router as inbox_router

app = FastAPI(title="InternGuard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(analyze_router)
app.include_router(inbox_router)
