from __future__ import annotations

import logging
import math
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from teamxi import PlayerProjection, XISelector

LOGGER = logging.getLogger("teamxi-api")


def find_data_root() -> Path:
    """Locate the directory holding data/proceed. Serverless bundles do not
    always keep the module next to the data, so search instead of assuming."""
    here = Path(__file__).resolve().parent
    for candidate in [here, *here.parents, Path.cwd(), *Path.cwd().parents]:
        if (candidate / "data" / "proceed").is_dir():
            return candidate
    return here


def get_selector() -> XISelector:
    if not hasattr(get_selector, "_instance"):
        root_dir = find_data_root()
        LOGGER.info("Initialising XISelector with root_dir=%s", root_dir)
        get_selector._instance = XISelector(root_dir=root_dir)
    return get_selector._instance


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

    @classmethod
    def from_projection(cls, projection: PlayerProjection) -> "PlayerPayload":
        payload = projection.to_payload()
        payload["playerId"] = payload.pop("player_id")
        payload["matchType"] = payload.pop("match_type")
        payload["predictedRuns"] = payload.pop("predicted_runs")
        payload["predictedWickets"] = payload.pop("predicted_wickets")
        payload["avgBattingPosition"] = payload.pop("avg_batting_position")
        payload["avgOvers"] = payload.pop("avg_overs")
        payload["matchesBatted"] = payload.pop("matches_batted")
        payload["matchesBowled"] = payload.pop("matches_bowled")
        payload["battingRecent"] = payload.pop("batting_recent")
        payload["bowlingRecent"] = payload.pop("bowling_recent")
        payload["headshotUrl"] = payload.pop("headshot_url")
        return cls(**payload)


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


class MatchPredictionRequest(BaseModel):
    team_a: str = Field(..., alias="teamA")
    team_b: str = Field(..., alias="teamB")
    match_type: str = Field("T20", alias="matchType")
    venue: Optional[str] = None
    as_of: Optional[datetime] = Field(None, alias="asOf")


class MatchPredictionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    match_type: str = Field(..., alias="matchType")
    venue: str
    generated_at: datetime = Field(..., alias="generatedAt")
    team_a: TeamInsightResponse = Field(..., alias="teamA")
    team_b: TeamInsightResponse = Field(..., alias="teamB")
    confidence: float
    summary: str


app = FastAPI(title="TeamXI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/diag")
def diag() -> dict:
    """Reports what the running process can actually see on disk."""
    root = find_data_root()
    needed = [
        "data/proceed/player_features_batting.csv",
        "data/proceed/player_features_batting_form.csv",
        "data/proceed/player_features_bowling.csv",
        "data/proceed/player_features_bowling_form.csv",
        "data/players/active_players.json",
    ]
    return {
        "module": str(Path(__file__).resolve()),
        "cwd": str(Path.cwd()),
        "resolved_root": str(root),
        "files": {f: (root / f).is_file() for f in needed},
        "root_listing": sorted(p.name for p in root.iterdir())[:25],
    }


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


def _summarise_team(
    lineup: List[PlayerProjection],
    team_name: str,
    opponent: str,
    match_type: str,
    win_probability: float,
) -> TeamInsightResponse:
    def batting_weight(player: PlayerProjection, idx: int) -> float:
        pos = player.avg_batting_position if player.avg_batting_position is not None else 8.5
        role = (player.role or "").lower()
        if pos <= 2.5:
            base = 1.0
        elif pos <= 3.5:
            base = 0.95
        elif pos <= 4.5:
            base = 0.88
        elif pos <= 5.5:
            base = 0.78
        elif pos <= 6.5:
            base = 0.66
        elif pos <= 7.5:
            base = 0.52
        else:
            base = 0.38
        if "all-rounder" in role and base < 0.66:
            base = max(base, 0.6)
        if player.matches_batted and player.matches_batted >= 10:
            base *= 1.05
        else:
            base *= 0.9
        if player.batting_recent is not None and player.predicted_runs:
            recent_delta = player.batting_recent - player.predicted_runs
            if recent_delta > 10:
                base *= 1.05
            elif recent_delta < -10:
                base *= 0.92
        decay = 0.97 ** idx
        return max(0.2, min(base * decay, 1.05))

    def bowling_weight(player: PlayerProjection, idx: int) -> float:
        overs = player.avg_overs if player.avg_overs is not None else 2.0
        role = (player.role or "").lower()
        if overs >= 3.8:
            base = 1.0
        elif overs >= 3.2:
            base = 0.9
        elif overs >= 2.6:
            base = 0.78
        elif overs >= 2.0:
            base = 0.64
        else:
            base = 0.5
        if "all-rounder" in role and base < 0.72:
            base = max(base, 0.72)
        if player.matches_bowled and player.matches_bowled >= 10:
            base *= 1.04
        else:
            base *= 0.92
        if player.bowling_recent is not None and player.predicted_wickets:
            recent_delta = player.bowling_recent - player.predicted_wickets
            if recent_delta > 0.4:
                base *= 1.04
            elif recent_delta < -0.4:
                base *= 0.9
        decay = 0.96 ** idx
        return max(0.25, min(base * decay, 1.05))

    max_batters = 9 if match_type.upper() == "ODI" else 7
    max_bowlers = 7 if match_type.upper() == "ODI" else 5

    sorted_batters = sorted(
        lineup,
        key=lambda p: p.avg_batting_position if p.avg_batting_position is not None else 99.0,
    )
    weighted_runs = []
    for idx, player in enumerate(sorted_batters):
        if idx >= max_batters:
            break
        runs = player.predicted_runs or 0.0
        if runs <= 0:
            continue
        weighted_runs.append(runs * batting_weight(player, idx))

    sorted_bowlers = sorted(
        lineup,
        key=lambda p: (
            -(p.predicted_wickets or 0.0),
            -(p.avg_overs or 0.0),
        ),
    )
    weighted_wickets = []
    for idx, player in enumerate(sorted_bowlers):
        if idx >= max_bowlers:
            break
        wkts = player.predicted_wickets or 0.0
        if wkts <= 0:
            continue
        weighted_wickets.append(wkts * bowling_weight(player, idx))

    if match_type.upper() == "ODI":
        base_runs = 28.0
        base_wickets = 0.8
        batting_reference = 330.0
        bowling_reference = 9.5
        high_run_threshold = 305
        solid_run_threshold = 275
        low_run_threshold = 240
        anchor_threshold = 55
    else:  # T20
        base_runs = 8.0
        base_wickets = 0.4
        batting_reference = 200.0
        bowling_reference = 8.0
        high_run_threshold = 175
        solid_run_threshold = 160
        low_run_threshold = 140
        anchor_threshold = 38

    total_runs = float(sum(weighted_runs) + base_runs)
    total_wickets = float(sum(weighted_wickets) + base_wickets)

    top_batters = sorted(lineup, key=lambda p: p.predicted_runs or -1.0, reverse=True)[:3]
    top_bowlers = sorted(lineup, key=lambda p: p.predicted_wickets or -1.0, reverse=True)[:3]

    strengths: List[str] = []
    weaknesses: List[str] = []

    max_run = max((p.predicted_runs or 0.0) for p in lineup) if lineup else 0.0
    strike_batters = sum(1 for value in weighted_runs if value >= 25)
    strike_bowlers = sum(1 for value in weighted_wickets if value >= 1.6)

    if total_runs >= high_run_threshold:
        strengths.append("Explosive batting potential")
    elif total_runs >= solid_run_threshold:
        strengths.append("Balanced scoring depth")

    if max_run >= anchor_threshold and top_batters:
        strengths.append(f"Form player: {top_batters[0].player_name}")

    if strike_batters >= 3:
        strengths.append("Middle order consistency")

    if total_wickets >= (8.0 if match_type.upper() == "ODI" else 6.0):
        strengths.append("Wicket-taking attack")
    elif strike_bowlers >= 2:
        strengths.append("Multiple strike bowlers")

    if total_runs < low_run_threshold:
        weaknesses.append("Runs on the board could be a concern")
    if max_run < anchor_threshold * 0.75:
        weaknesses.append("Need a reliable top-order anchor")
    if total_wickets < (6.0 if match_type.upper() == "ODI" else 4.5):
        weaknesses.append("Bowling penetration looks light")
    if strike_bowlers <= 1:
        weaknesses.append("Reliant on a single strike bowler")

    batting_rating = max(0.0, min(100.0, (total_runs / batting_reference) * 100.0))
    bowling_rating = max(0.0, min(100.0, (total_wickets / bowling_reference) * 100.0))

    key_batters = [_key_player_summary(p) for p in top_batters if (p.predicted_runs or 0) > 0]
    key_bowlers = [_key_player_summary(p) for p in top_bowlers if (p.predicted_wickets or 0) > 0]

    if not key_batters and top_batters:
        key_batters = [_key_player_summary(top_batters[0])]
    if not key_bowlers and top_bowlers:
        key_bowlers = [_key_player_summary(top_bowlers[0])]

    return TeamInsightResponse(
        team=team_name or (lineup[0].team if lineup else ""),
        opponent=opponent,
        win_probability=round(win_probability, 4),
        expected_runs=round(total_runs, 1),
        expected_wickets=round(total_wickets, 2),
        batting_rating=round(batting_rating, 1),
        bowling_rating=round(bowling_rating, 1),
        strengths=strengths or ["Balanced lineup"],
        weaknesses=weaknesses[:3],
        key_batters=key_batters,
        key_bowlers=key_bowlers,
    )


@app.post("/predict_match", response_model=MatchPredictionResponse)
def predict_match(payload: MatchPredictionRequest, selector: XISelector = Depends(get_selector)):
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

    (team_a_selected, _), (team_b_selected, _) = selector.generate_match_xi(
        team_a=payload.team_a,
        team_b=payload.team_b,
        match_type=match_type,
        venue=venue,
        as_of=as_of,
    )

    insight_a = _summarise_team(team_a_selected, payload.team_a, payload.team_b, match_type, 0.5)
    insight_b = _summarise_team(team_b_selected, payload.team_b, payload.team_a, match_type, 0.5)

    score_a = (insight_a.batting_rating * 0.7 + insight_a.bowling_rating * 0.3)
    score_b = (insight_b.batting_rating * 0.7 + insight_b.bowling_rating * 0.3)

    diff = score_a - score_b
    logistic_scale = 14.0 if match_type.upper() == "ODI" else 8.0
    if score_a == 0 and score_b == 0:
        prob_a = prob_b = 0.5
    else:
        prob_a = 1.0 / (1.0 + math.exp(-diff / logistic_scale))
        prob_b = 1.0 - prob_a

    insight_a.win_probability = round(prob_a, 4)
    insight_b.win_probability = round(prob_b, 4)

    prob_a = insight_a.win_probability
    prob_b = insight_b.win_probability

    confidence = round(max(prob_a, prob_b), 4)
    favoured = insight_a.team if prob_a >= prob_b else insight_b.team
    underdog = insight_b.team if prob_a >= prob_b else insight_a.team
    fav_prob = confidence * 100
    summary = (
        f"{favoured} hold a {fav_prob:.0f}% edge over {underdog} at {venue}."
        if favoured and underdog
        else f"Projected outcome compiled for {payload.team_a} vs {payload.team_b}."
    )

    return MatchPredictionResponse(
        matchType=match_type,
        venue=venue,
        generatedAt=datetime.utcnow(),
        teamA=insight_a,
        teamB=insight_b,
        confidence=confidence,
        summary=summary,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)

