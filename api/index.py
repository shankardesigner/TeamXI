"""Vercel entrypoint. The repo root holds server.py and teamxi.py, so put it on
the path before importing."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402

from server import app as api_app  # noqa: E402

# Vercel rewrites /api/<path> to /api/index/<path>, so the app is mounted at
# both prefixes: /api/index for the rewritten path, /api in case the platform
# forwards the original one. Nothing is mounted at "/" — that would make this
# function answer every request and shadow the static frontend.
app = FastAPI()
app.mount("/api/index", api_app)
app.mount("/api", api_app)
