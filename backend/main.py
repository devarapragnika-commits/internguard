"""InternGuard HTTP API."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.config import CORS_ORIGIN_REGEX, ROOT_DIR, get_cors_origins
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

_FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
_FRONTEND_ASSETS = _FRONTEND_DIST / "assets"
_API_PREFIXES = ("analyze/", "health", "inbox", "docs", "redoc", "openapi.json")

if _FRONTEND_ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_ASSETS), name="assets")


@app.get("/{full_path:path}")
def frontend_file(full_path: str):
    if not full_path or full_path.startswith(_API_PREFIXES):
        raise HTTPException(status_code=404, detail="Not found")
    target = (_FRONTEND_DIST / full_path).resolve()
    try:
        target.relative_to(_FRONTEND_DIST.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    if target.is_file():
        return FileResponse(target)
    raise HTTPException(status_code=404, detail="Not found")
