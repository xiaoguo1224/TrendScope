from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(settings.log_level)
    logger.info("application_started")
    yield
    logger.info("application_stopped")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": "Request validation failed", "errors": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def _frontend_directory() -> Path | None:
    """Return the built SPA directory when the desktop distribution supplies one."""
    configured_directory = os.getenv("TRENDSCOPE_FRONTEND_DIR")
    if not configured_directory:
        return None
    directory = Path(configured_directory)
    index_file = directory / "index.html"
    return directory if index_file.is_file() else None


frontend_directory = _frontend_directory()
if frontend_directory is not None:
    assets_directory = frontend_directory / "assets"
    if assets_directory.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_directory), name="frontend-assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{frontend_path:path}", include_in_schema=False)
    def serve_frontend(frontend_path: str = "") -> FileResponse:
        """Serve Vite assets and fall back to the SPA entry point for client routes."""
        requested_file = (frontend_directory / frontend_path).resolve()
        if frontend_path and requested_file.is_file() and frontend_directory in requested_file.parents:
            return FileResponse(requested_file)
        return FileResponse(frontend_directory / "index.html")
