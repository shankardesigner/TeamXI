from __future__ import annotations

import logging
import math
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

from cricxi import PlayerProjection, XISelector


LOGGER = logging.getLogger("cricxi-api")


def get_selector() -> XISelector:
    if not hasattr(get_selector, "_instance"):
        root_dir = Path(__file__).resolve().parent
        LOGGER.info("Initialising XISelector with root_dir=%s", root_dir)
        setattr(get_selector, "_instance", XISelector(root_dir=root_dir))
    return getattr(get_selector, "_instance")


app = FastAPI(title="CricXI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthcheck() -> dict:
    return {"status": "ok"}


