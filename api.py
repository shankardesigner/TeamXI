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


class TeamsResponse(BaseModel):
    match_type: str = Field(..., alias="matchType")
    teams: List[str]


class VenuesResponse(BaseModel):
    match_type: str = Field(..., alias="matchType")
    team_a: str = Field(..., alias="teamA")
    team_b: str = Field(..., alias="teamB")
    venues: List[str]


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


@app.get("/teams", response_model=TeamsResponse)
def list_teams(match_type: str = Query("T20", alias="matchType"), selector: XISelector = Depends(get_selector)):
    match_type = match_type.upper()
    teams = selector.list_teams(match_type)
    if not teams:
        raise HTTPException(status_code=404, detail=f"No teams found for match type {match_type}")
    return TeamsResponse(matchType=match_type, teams=teams)


@app.get("/venues", response_model=VenuesResponse)
def list_venues(
    match_type: str = Query("T20", alias="matchType"),
    team_a: Optional[str] = Query(None, alias="teamA"),
    team_b: Optional[str] = Query(None, alias="teamB"),
    selector: XISelector = Depends(get_selector),
):
    match_type = match_type.upper()
    teams = [t for t in (team_a, team_b) if t]
    venues = selector.list_venues(match_type, teams if teams else None)
    if not venues:
        raise HTTPException(status_code=404, detail="No venues found for supplied filters")
    return VenuesResponse(matchType=match_type, teamA=team_a or "", teamB=team_b or "", venues=venues)


