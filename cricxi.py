from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Utility data classes
# ---------------------------------------------------------------------------


@dataclass
class PlayerProjection:
    player_id: str
    player_name: str
    team: str
    opponent: str
    match_type: str
    role: str
    predicted_runs: Optional[float]
    predicted_wickets: Optional[float]
    avg_batting_position: Optional[float]
    avg_overs: Optional[float]
    matches_batted: int
    matches_bowled: int
    batting_recent: Optional[float]
    bowling_recent: Optional[float]
    headshot_url: Optional[str] = None

    def as_display_row(self) -> Dict[str, Any]:
        return {
            "Player": self.player_name,
            "Role": self.role,
            "Pred Runs": None if self.predicted_runs is None else round(self.predicted_runs, 1),
            "Pred Wkts": None if self.predicted_wickets is None else round(self.predicted_wickets, 1),
            "Avg Pos": None
            if self.avg_batting_position is None
            else round(self.avg_batting_position, 1),
            "Avg Overs": None if self.avg_overs is None else round(self.avg_overs, 1),
            "Matches (bat)": self.matches_batted,
            "Matches (bowl)": self.matches_bowled,
            "Recent bat": None if self.batting_recent is None else round(self.batting_recent, 1),
            "Recent wkts": None if self.bowling_recent is None else round(self.bowling_recent, 2),
        }

    def to_payload(self) -> Dict[str, Any]:
        return {
            "player_id": self.player_id,
            "name": self.player_name,
            "team": self.team,
            "opponent": self.opponent,
            "match_type": self.match_type,
            "role": self.role,
            "predicted_runs": None if self.predicted_runs is None else float(self.predicted_runs),
            "predicted_wickets": None
            if self.predicted_wickets is None
            else float(self.predicted_wickets),
            "avg_batting_position": None
            if self.avg_batting_position is None
            else float(self.avg_batting_position),
            "avg_overs": None if self.avg_overs is None else float(self.avg_overs),
            "matches_batted": int(self.matches_batted),
            "matches_bowled": int(self.matches_bowled),
            "batting_recent": None
            if self.batting_recent is None
            else float(self.batting_recent),
            "bowling_recent": None
            if self.bowling_recent is None
            else float(self.bowling_recent),
            "headshot_url": self.headshot_url,
        }


# ---------------------------------------------------------------------------
# Feature engineering helpers (ported from the modelling notebooks)
# ---------------------------------------------------------------------------


def _calculate_dynamic_venue_effects(df: pd.DataFrame) -> pd.DataFrame:
    venue_stats = (
        df.groupby("venue")
        .agg(
            {
                "runs_scored": ["mean", "std", "count"],
                "strike_rate": "mean",
                "boundaries": "mean",
                "sixes": "mean",
            }
        )
        .round(2)
    )
    venue_stats.columns = [
        "venue_avg_runs",
        "venue_std_runs",
        "match_count",
        "venue_avg_sr",
        "venue_avg_boundaries",
        "venue_avg_sixes",
    ]
    venue_stats = venue_stats.reset_index()

    overall_avg_runs = df["runs_scored"].mean()

    def _categorise(row: pd.Series) -> Tuple[str, float]:
        if row["match_count"] < 5:
            return "Neutral", 1.0
        if row["venue_avg_runs"] >= overall_avg_runs * 1.15:
            return "High Scoring", 1.3
        if row["venue_avg_runs"] >= overall_avg_runs * 1.05:
            return "Batter Friendly", 1.15
        if row["venue_avg_runs"] <= overall_avg_runs * 0.85:
            return "Bowler Friendly", 0.8
        if row["venue_avg_runs"] <= overall_avg_runs * 0.95:
            return "Balanced", 0.9
        return "Neutral", 1.0

    venue_stats[["venue_type", "venue_factor_cat"]] = venue_stats.apply(
        lambda x: pd.Series(_categorise(x)), axis=1
    )
    venue_stats["venue_factor"] = venue_stats["venue_avg_runs"] / overall_avg_runs
    venue_stats["final_venue_factor"] = (
        venue_stats["venue_factor"] + venue_stats["venue_factor_cat"]
    ) / 2
    return venue_stats[["venue", "venue_type", "final_venue_factor", "match_count"]]


def _create_dynamic_player_profiles(df: pd.DataFrame) -> pd.DataFrame:
    player_profiles = (
        df.groupby("player_id")
        .agg(
            {
                "player_name": "last",
                "runs_scored": ["mean", "max", "std", "count"],
                "strike_rate": "mean",
                "batting_position": ["mean", "min", "max"],
                "boundaries": "mean",
                "sixes": "mean",
            }
        )
        .round(2)
    )
    player_profiles.columns = [
        "name",
        "avg_runs",
        "max_runs",
        "std_runs",
        "matches_played",
        "avg_strike_rate",
        "avg_position",
        "min_position",
        "max_position",
        "avg_boundaries",
        "avg_sixes",
    ]
    player_profiles = player_profiles.reset_index()

    def _classify(row: pd.Series) -> str:
        matches = row["matches_played"]
        avg_runs = row["avg_runs"]
        position = row["avg_position"]
        sr = row["avg_strike_rate"]

        if matches < 5:
            return "New Player"
        if avg_runs > 45 and position <= 3:
            return "World-Class Top Order"
        if avg_runs > 35 and position <= 3:
            return "Solid Top Order"
        if avg_runs > 30 and position <= 4:
            return "Reliable Top/Middle"
        if avg_runs > 25 and position <= 6:
            return "Dependable Middle Order"
        if position >= 7 and sr > 135:
            return "Power Finisher"
        if sr > 140:
            return "Hard-Hitting Finisher"
        if position >= 6:
            return "Bowling All-Rounder"
        return "Utility Batter"

    player_profiles["player_type"] = player_profiles.apply(_classify, axis=1)
    return player_profiles


def _calculate_opponent_bowling_strength(bowling_df: pd.DataFrame) -> pd.DataFrame:
    df = bowling_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["opponent_team", "match_type", "date"])

    grp_cols = ["opponent_team", "match_type", "date", "match_id", "venue"]
    match_stats = (
        df.groupby(grp_cols)
        .agg(
            {
                "runs_conceded": "sum",
                "balls_bowled": "sum",
                "wickets_taken": "sum",
                "dot_balls": "sum",
                "overs_bowled": "sum",
            }
        )
        .reset_index()
    )

    match_stats["economy_rate"] = (
        match_stats["runs_conceded"] / match_stats["overs_bowled"].replace(0, np.nan)
    ).fillna(6.5)
    match_stats["wickets_per_match"] = match_stats["wickets_taken"]
    match_stats["dot_ball_pct"] = (
        match_stats["dot_balls"] / match_stats["balls_bowled"].replace(0, np.nan) * 100
    ).fillna(25.0)

    def _rolling(series: pd.Series) -> pd.Series:
        return series.rolling(5, min_periods=1).mean()

    group_keys = ["opponent_team", "match_type"]
    match_stats["economy_last_5"] = match_stats.groupby(group_keys)["economy_rate"].transform(_rolling)
    match_stats["wickets_last_5"] = match_stats.groupby(group_keys)["wickets_per_match"].transform(_rolling)
    match_stats["dot_pct_last_5"] = match_stats.groupby(group_keys)["dot_ball_pct"].transform(_rolling)

    venue_stats = (
        match_stats.groupby(["opponent_team", "match_type", "venue"])
        .agg(
            {
                "economy_rate": "mean",
                "wickets_per_match": "mean",
                "dot_ball_pct": "mean",
            }
        )
        .reset_index()
    )
    venue_stats.columns = [
        "opponent_team",
        "match_type",
        "venue",
        "venue_economy",
        "venue_wickets",
        "venue_dot_pct",
    ]

    match_stats = match_stats.merge(
        venue_stats, on=["opponent_team", "match_type", "venue"], how="left"
    )

    for col, fallback in [
        ("venue_economy", match_stats["economy_rate"].mean()),
        ("venue_wickets", match_stats["wickets_per_match"].mean()),
        ("venue_dot_pct", match_stats["dot_ball_pct"].mean()),
    ]:
        match_stats[col] = match_stats[col].fillna(fallback)

    match_stats["bowling_strength_raw"] = (
        (1 - (match_stats["economy_last_5"] / 12.0)) * 0.4
        + (match_stats["wickets_last_5"] / 10.0) * 0.3
        + (match_stats["dot_pct_last_5"] / 50.0) * 0.3
    )

    min_val = match_stats["bowling_strength_raw"].min()
    max_val = match_stats["bowling_strength_raw"].max()
    scale = max(max_val - min_val, 1e-6)
    match_stats["bowling_strength_norm"] = (match_stats["bowling_strength_raw"] - min_val) / scale

    return match_stats[
        [
            "opponent_team",
            "match_type",
            "date",
            "match_id",
            "venue",
            "economy_last_5",
            "wickets_last_5",
            "dot_pct_last_5",
            "venue_economy",
            "venue_wickets",
            "venue_dot_pct",
            "bowling_strength_norm",
        ]
    ]


# ---------------------------------------------------------------------------
# XI Selection Engine
# ---------------------------------------------------------------------------


class XISelector:
    """Generate predicted playing XIs using batting and bowling heuristics."""

    _T20_RATINGS: Dict[str, int] = {
        "India": 272,
        "Australia": 267,
        "England": 258,
        "New Zealand": 251,
        "South Africa": 240,
        "West Indies": 237,
        "Pakistan": 234,
        "Sri Lanka": 230,
        "Bangladesh": 223,
        "Afghanistan": 220,
        "Ireland": 201,
        "Zimbabwe": 199,
        "Netherlands": 182,
        "Scotland": 182,
        "Namibia": 181,
        "United Arab Emirates": 178,
        "Nepal": 176,
        "United States": 175,
        "Canada": 154,
        "Oman": 150,
        "Uganda": 142,
        "PNG": 136,
    }

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        base_path = Path(root_dir) if root_dir else Path(__file__).resolve().parent
        self.root_dir = base_path
        self.data_dir = self.root_dir / "data" / "proceed"

        # Load datasets
        self.batting_raw = self._load_csv("player_features_batting.csv")
        self.batting_form = self._load_csv("player_features_batting_form.csv")
        self.bowling_raw = self._load_csv("player_features_bowling.csv")
        self.bowling_form = self._load_csv("player_features_bowling_form.csv")

        self.batting_raw["match_type"] = self.batting_raw["match_type"].str.upper()
        self.batting_form["match_type"] = self.batting_form["match_type"].str.upper()
        self.bowling_raw["match_type"] = self.bowling_raw["match_type"].str.upper()
        self.bowling_form["match_type"] = self.bowling_form["match_type"].str.upper()

        # Derived data
        self.venue_effects = _calculate_dynamic_venue_effects(self.batting_raw)
        self.player_profiles = _create_dynamic_player_profiles(self.batting_raw)
        self.bowling_strength_df = _calculate_opponent_bowling_strength(self.bowling_raw)

        self._venue_lookup = self.venue_effects.set_index("venue").to_dict("index")
        self._profile_lookup = self.player_profiles.set_index("player_id").to_dict("index")

        strength_df = self.bowling_strength_df.copy()
        strength_df["opponent_team_norm"] = strength_df["opponent_team"].str.strip().str.title()
        strength_df["match_type"] = strength_df["match_type"].str.upper()
        self._bowling_strength_lookup = strength_df.groupby(
            ["opponent_team_norm", "match_type"]
        )["bowling_strength_norm"].mean().to_dict()

        self._team_cache: Dict[str, Dict[str, List[str]]] = {}
        self._active_player_lookup = self._load_active_players()

    @staticmethod
    def _normalise_team(value: str) -> str:
        return (value or "").strip().lower()

    @staticmethod
    def _normalise_name(value: str) -> str:
        return (value or "").strip().lower()

    def _load_active_players(self) -> Dict[Tuple[str, str], Dict[str, Dict[str, Any]]]:
        lookup: Dict[Tuple[str, str], Dict[str, Dict[str, Any]]] = {}
        path = self.root_dir / "data" / "players" / "active_players.json"
        if not path.exists():
            return lookup
        try:
            with path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except Exception:
            return lookup

        for team_name, formats in raw.items():
            team_key = self._normalise_team(team_name)
            if not isinstance(formats, dict):
                continue
            for fmt, players in formats.items():
                if not isinstance(players, list):
                    continue
                key = (team_key, str(fmt).lower())
                info: Dict[str, Dict[str, Any]] = {}
                for player in players:
                    if not isinstance(player, dict):
                        continue
                    name = player.get("name")
                    if not name:
                        continue
                    norm_name = self._normalise_name(name)
                    info[norm_name] = player
                if info:
                    lookup[key] = info
        return lookup

    def _get_active_info(self, team: str, match_type: str) -> Dict[str, Dict[str, Any]]:
        team_key = self._normalise_team(team)
        fmt_key = match_type.lower()
        return self._active_player_lookup.get((team_key, fmt_key), {})

    def _get_active_names(self, team: str, match_type: str) -> set[str]:
        return set(self._get_active_info(team, match_type).keys())

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def _load_csv(self, filename: str) -> pd.DataFrame:
        path = self.data_dir / filename
        df = pd.read_csv(path)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df
