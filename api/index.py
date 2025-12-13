"""Vercel entrypoint. The repo root holds server.py and teamxi.py, so put it on
the path before importing."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402

from server import app as api_app  # noqa: E402

# Vercel rewrites /api/* here. Mount under /api first; the root mount is a
# fallback in case the platform strips the prefix before invoking us.
app = FastAPI()
app.mount("/api", api_app)
app.mount("/", api_app)
