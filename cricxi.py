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
