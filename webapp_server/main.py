"""
Main FastAPI app: serves the Mini App static frontend AND the JSON API it calls.

Run with:
    uvicorn webapp_server.main:app --host 0.0.0.0 --port 8080

In production, put this behind nginx/caddy with a valid TLS certificate —
Telegram requires HTTPS for Mini App URLs.
"""
from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from bot.database.db import init_db
from webapp_server.routes_auth import router as auth_router
from webapp_server.routes_templates import router as templates_router
from webapp_server.routes_process import router as process_router
from webapp_server.routes_misc import router as misc_router

BASE_DIR = Path(__file__).resolve().parent.parent
WEBAPP_STATIC_DIR = BASE_DIR / "webapp"

app = FastAPI(title="WMark Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Telegram WebView origin varies; API auth is via JWT, not CORS
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(templates_router)
app.include_router(process_router)
app.include_router(misc_router)


@app.on_event("startup")
async def on_startup():
    await init_db()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Serve the Mini App frontend (HTML/CSS/JS) as static files.
# Must be mounted last so it doesn't shadow the /api/* routes above.
app.mount("/", StaticFiles(directory=WEBAPP_STATIC_DIR, html=True), name="webapp")
