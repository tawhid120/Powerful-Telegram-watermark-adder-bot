"""
Convenience launcher: runs the Pyrofork bot AND the FastAPI webapp server
concurrently in a single process using asyncio + a thread for uvicorn.

For production, run them as two separate systemd services / Docker containers
instead (see README.md) — this script is meant for quick local testing.
"""
import asyncio
import threading

import uvicorn

from bot.config import WEBAPP_HOST, WEBAPP_PORT
from bot.main import main as run_bot


def run_webapp():
    uvicorn.run("webapp_server.main:app", host=WEBAPP_HOST, port=WEBAPP_PORT, log_level="info")


if __name__ == "__main__":
    webapp_thread = threading.Thread(target=run_webapp, daemon=True)
    webapp_thread.start()
    asyncio.run(run_bot())
