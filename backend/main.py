"""InternGuard HTTP API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.config import CORS_ORIGIN_REGEX, get_cors_origins
from backend.routes.analyze import router as analyze_router
from backend.routes.health import router as health_router
from backend.routes.inbox import router as inbox_router
from backend.services.rate_limit import allow_analyze, rate_limit_message

app = FastAPI(title="InternGuard")


class AnalyzeRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path.startswith("/analyze/"):
            client = request.client.host if request.client else "unknown"
            if not allow_analyze(client):
                return JSONResponse(status_code=429, content={"detail": rate_limit_message()})
        return await call_next(request)


app.add_middleware(AnalyzeRateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(analyze_router)
app.include_router(inbox_router)
