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


class PlayerPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    player_id: str = Field(..., alias="playerId")
    name: str
    team: str
    opponent: str
    match_type: str = Field(..., alias="matchType")
    role: str
    predicted_runs: Optional[float] = Field(None, alias="predictedRuns")
    predicted_wickets: Optional[float] = Field(None, alias="predictedWickets")
    avg_batting_position: Optional[float] = Field(None, alias="avgBattingPosition")
    avg_overs: Optional[float] = Field(None, alias="avgOvers")
    matches_batted: int = Field(..., alias="matchesBatted")
    matches_bowled: int = Field(..., alias="matchesBowled")
    batting_recent: Optional[float] = Field(None, alias="battingRecent")
    bowling_recent: Optional[float] = Field(None, alias="bowlingRecent")
    headshot_url: Optional[str] = Field(None, alias="headshotUrl")


class SquadPayload(BaseModel):
    team: str
    opponent: str
    match_type: str = Field(..., alias="matchType")
    selected: List[PlayerPayload]
    bench: List[PlayerPayload]


class XIRequest(BaseModel):
    team_a: str = Field(..., alias="teamA")
    team_b: str = Field(..., alias="teamB")
    match_type: str = Field("T20", alias="matchType")
    venue: Optional[str] = None
    as_of: Optional[datetime] = Field(None, alias="asOf")


class XIResponse(BaseModel):
    match_type: str = Field(..., alias="matchType")
    venue: str
    generated_at: datetime = Field(..., alias="generatedAt")
    team_a: SquadPayload = Field(..., alias="teamA")
    team_b: SquadPayload = Field(..., alias="teamB")


class KeyPlayerSummary(BaseModel):
    name: str
    role: str
    predicted_runs: Optional[float] = Field(None, alias="predictedRuns")
    predicted_wickets: Optional[float] = Field(None, alias="predictedWickets")


class TeamInsightResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    team: str
    opponent: str
    win_probability: float = Field(..., alias="winProbability")
    expected_runs: float = Field(..., alias="expectedRuns")
    expected_wickets: float = Field(..., alias="expectedWickets")
    batting_rating: float = Field(..., alias="battingRating")
    bowling_rating: float = Field(..., alias="bowlingRating")
    strengths: List[str]
    weaknesses: List[str]
    key_batters: List[KeyPlayerSummary] = Field(..., alias="keyBatters")
    key_bowlers: List[KeyPlayerSummary] = Field(..., alias="keyBowlers")


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


@app.post("/predict_xi", response_model=XIResponse)
def predict_xi(payload: XIRequest, selector: XISelector = Depends(get_selector)):
    match_type = payload.match_type.upper()
    venue = payload.venue
    if not venue:
        venues = selector.list_venues(match_type, [payload.team_a, payload.team_b])
        if not venues:
            raise HTTPException(status_code=400, detail="Unable to infer venue; please provide one explicitly.")
        venue = venues[0]

    as_of = payload.as_of
    if isinstance(as_of, datetime):
        as_of = as_of.tzinfo and as_of.astimezone(tz=None) or as_of

    (team_a_selected, team_a_bench), (team_b_selected, team_b_bench) = selector.generate_match_xi(
        team_a=payload.team_a,
        team_b=payload.team_b,
        match_type=match_type,
        venue=venue,
        as_of=as_of,
    )

    response = XIResponse(
        matchType=match_type,
        venue=venue,
        generatedAt=datetime.utcnow(),
        teamA=SquadPayload(
            team=payload.team_a,
            opponent=payload.team_b,
            matchType=match_type,
            selected=[PlayerPayload.from_projection(p) for p in team_a_selected],
            bench=[PlayerPayload.from_projection(p) for p in team_a_bench],
        ),
        teamB=SquadPayload(
            team=payload.team_b,
            opponent=payload.team_a,
            matchType=match_type,
            selected=[PlayerPayload.from_projection(p) for p in team_b_selected],
            bench=[PlayerPayload.from_projection(p) for p in team_b_bench],
        ),
    )
    return response


def _key_player_summary(projection: PlayerProjection) -> KeyPlayerSummary:
    payload = projection.to_payload()
    return KeyPlayerSummary(
        name=payload["name"],
        role=payload["role"],
        predictedRuns=payload["predicted_runs"],
        predictedWickets=payload["predicted_wickets"],
    )


