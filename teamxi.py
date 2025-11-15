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
    # Public APIs
    # ------------------------------------------------------------------

    def list_teams(self, match_type: str) -> List[str]:
        fmt = match_type.upper()
        if fmt not in self._team_cache:
            batting_teams = self.batting_raw[self.batting_raw["match_type"] == fmt][
                "batting_team"
            ].unique()
            bowling_teams = self.bowling_raw[self.bowling_raw["match_type"] == fmt][
                "bowling_team"
            ].unique()
            teams = sorted(set(batting_teams).union(set(bowling_teams)))
            self._team_cache[fmt] = {"teams": teams}
        return self._team_cache[fmt]["teams"]

    def list_venues(self, match_type: str, teams: Optional[Iterable[str]] = None) -> List[str]:
        fmt = match_type.upper()
        df = self.batting_raw[self.batting_raw["match_type"] == fmt]
        if teams:
            teams_set = set(teams)
            df = df[df["batting_team"].isin(teams_set) | df["opponent_team"].isin(teams_set)]
        venue_counts = df["venue"].value_counts().sort_values(ascending=False)
        return venue_counts.index.tolist()

    def generate_match_xi(
        self,
        team_a: str,
        team_b: str,
        match_type: str,
        venue: str,
        as_of: Optional[pd.Timestamp] = None,
    ) -> Tuple[
        Tuple[List[PlayerProjection], List[PlayerProjection]],
        Tuple[List[PlayerProjection], List[PlayerProjection]],
    ]:
        lineup_a = self._generate_team_xi(team_a, team_b, match_type, venue, as_of)
        lineup_b = self._generate_team_xi(team_b, team_a, match_type, venue, as_of)
        return lineup_a, lineup_b

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def _load_csv(self, filename: str) -> pd.DataFrame:
        path = self.data_dir / filename
        df = pd.read_csv(path)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    def _filter_recent(
        self,
        df: pd.DataFrame,
        team_col: str,
        team: str,
        match_type: str,
        as_of: Optional[pd.Timestamp],
        window_years: int = 2,
    ) -> pd.DataFrame:
        fmt = match_type.upper()
        reference_date = as_of.normalize() if as_of is not None else pd.Timestamp.today().normalize()
        start_date = reference_date - pd.DateOffset(years=window_years)
        subset = df[
            (df[team_col] == team)
            & (df["match_type"] == fmt)
            & (df["date"] >= start_date)
            & (df["date"] <= reference_date)
        ].copy()
        subset.sort_values("date", inplace=True)
        return subset

    def _generate_team_xi(
        self,
        team: str,
        opponent: str,
        match_type: str,
        venue: str,
        as_of: Optional[pd.Timestamp],
    ) -> Tuple[List[PlayerProjection], List[PlayerProjection]]:
        batting_recent = self._filter_recent(
            self.batting_form, "batting_team", team, match_type, as_of
        )
        bowling_recent = self._filter_recent(
            self.bowling_form, "bowling_team", team, match_type, as_of
        )

        if batting_recent.empty and bowling_recent.empty:
            return ([], [])

        candidate_ids = sorted(
            set(batting_recent["player_id"].unique()).union(bowling_recent["player_id"].unique())
        )

        active_lookup = self._get_active_info(team, match_type)

        projections: List[PlayerProjection] = []
        for player_id in candidate_ids:
            projection = self._build_projection(
                player_id,
                team=team,
                opponent=opponent,
                match_type=match_type,
                venue=venue,
                batting_recent=batting_recent,
                bowling_recent=bowling_recent,
                active_lookup=active_lookup,
            )
            if projection is not None:
                projections.append(projection)

        if not projections:
            return ([], [])

        return self._select_best_eleven(projections)

    def _build_projection(
        self,
        player_id: str,
        team: str,
        opponent: str,
        match_type: str,
        venue: str,
        batting_recent: pd.DataFrame,
        bowling_recent: pd.DataFrame,
        active_lookup: Dict[str, Dict[str, Any]],
    ) -> Optional[PlayerProjection]:
        bat_df = batting_recent[batting_recent["player_id"] == player_id]
        bowl_df = bowling_recent[bowling_recent["player_id"] == player_id]

        if bat_df.empty and bowl_df.empty:
            return None

        player_name = None
        if not bat_df.empty:
            player_name = bat_df["player_name"].iloc[-1]
        elif not bowl_df.empty:
            player_name = bowl_df["player_name"].iloc[-1]
        else:
            player_name = player_id

        avg_pos = bat_df["batting_position"].mean() if not bat_df.empty else None
        avg_overs = bowl_df["overs_bowled"].mean() if not bowl_df.empty else None

        matches_batted = bat_df["match_id"].nunique() if not bat_df.empty else 0
        matches_bowled = bowl_df["match_id"].nunique() if not bowl_df.empty else 0

        batting_recent_avg = (
            bat_df.tail(5)["runs_scored"].mean() if not bat_df.empty else None
        )
        bowling_recent_avg = (
            bowl_df.tail(5)["wickets_taken"].mean() if not bowl_df.empty else None
        )

        avg_wickets = bowl_df["wickets_taken"].mean() if not bowl_df.empty else 0.0

        role = self._classify_role(avg_pos, avg_overs, avg_wickets, matches_bowled)

        normalized_name = self._normalise_name(player_name)
        headshot_url = None
        active_record = active_lookup.get(normalized_name) if active_lookup else None
        if active_record:
            raw_headshot = active_record.get("headshotImageUrl")
            if isinstance(raw_headshot, str) and raw_headshot.strip():
                headshot_url = raw_headshot.strip().lstrip("/")

        predicted_runs: Optional[float] = None
        if not bat_df.empty:
            tentative_position = int(round(avg_pos)) if avg_pos and not math.isnan(avg_pos) else 5
            predicted_runs = self._predict_batting(
                player_id, opponent, venue, match_type, tentative_position
            )

        predicted_wickets: Optional[float] = None
        if not bowl_df.empty:
            predicted_wickets = self._predict_bowling(player_id, opponent, venue, match_type)

        return PlayerProjection(
            player_id=player_id,
            player_name=player_name,
            team=team,
            opponent=opponent,
            match_type=match_type,
            role=role,
            predicted_runs=predicted_runs,
            predicted_wickets=predicted_wickets,
            avg_batting_position=avg_pos,
            avg_overs=avg_overs,
            matches_batted=matches_batted,
            matches_bowled=matches_bowled,
            batting_recent=batting_recent_avg,
            bowling_recent=bowling_recent_avg,
            headshot_url=headshot_url,
        )

    def _classify_role(
        self,
        avg_position: Optional[float],
        avg_overs: Optional[float],
        avg_wickets: float,
        matches_bowled: int,
    ) -> str:
        overs = avg_overs or 0.0
        position = avg_position if avg_position is not None else 7.0

        if matches_bowled >= 3 and (overs >= 3.0 or avg_wickets >= 1.2):
            return "Bowler"
        if matches_bowled >= 2 and (overs >= 1.5 or avg_wickets >= 0.6):
            return "All-Rounder"
        if position <= 4.0:
            return "Top Batter"
        if position <= 6.0:
            return "Middle Batter"
        return "Batting All-Rounder" if matches_bowled > 0 else "Lower Batter"

    # ------------------------------------------------------------------
    # Prediction heuristics (adapted from prototypes)
    # ------------------------------------------------------------------

    def _predict_batting(
        self,
        player_id: str,
        opponent_team: str,
        venue: str,
        match_type: str,
        batting_position: int,
    ) -> Optional[float]:
        df = self.batting_raw[self.batting_raw["player_id"] == player_id].sort_values("date")
        if df.empty:
            return None

        player_avg = df["runs_scored"].mean()
        player_recent = df.tail(10)["runs_scored"].mean()
        base_prediction = max(player_avg, player_recent)

        profile = self._profile_lookup.get(player_id)
        if profile:
            player_type = profile.get("player_type", "Unknown")
            avg_runs = profile.get("avg_runs", player_avg)
            player_name = profile.get("name", player_id)
        else:
            player_type = "Unknown"
            avg_runs = player_avg
            player_name = df["player_name"].iloc[-1]

        quality_bonus = 0.0
        if "World-Class" in player_type:
            quality_bonus = 8.0
        elif "Solid" in player_type or "Reliable" in player_type:
            quality_bonus = 4.0
        elif "Dependable" in player_type:
            quality_bonus = 2.0
        elif "Hard-Hitting" in player_type or "Power Finisher" in player_type:
            quality_bonus = 3.0
        elif "Bowling All-Rounder" in player_type:
            quality_bonus = 1.0

        base_prediction = max(base_prediction, avg_runs) + quality_bonus

        opponent_norm = opponent_team.strip().title()
        strength_key = (opponent_norm, match_type.upper())
        opponent_strength = self._bowling_strength_lookup.get(strength_key)
        strength_source = "data"

        if opponent_strength is None:
            # fallbacks based on tiers
            major = {"Australia", "India", "England", "New Zealand", "South Africa", "Pakistan"}
            strong = {"Sri Lanka", "West Indies", "Bangladesh"}
            associate = {
                "United States",
                "United States Of America",
                "Netherlands",
                "Ireland",
                "Scotland",
                "Uae",
                "Canada",
                "Oman",
                "Nepal",
            }
            if opponent_norm in major:
                opponent_strength = 0.7
                strength_source = "major tier"
            elif opponent_norm in strong:
                opponent_strength = 0.6
                strength_source = "strong tier"
            elif opponent_norm in associate:
                opponent_strength = 0.4
                strength_source = "associate tier"
            else:
                opponent_strength = 0.5
                strength_source = "default"

        opponent_factor = 1.0 + (0.5 - opponent_strength)
        if opponent_strength > 0.7:
            opponent_factor *= 0.8
        elif opponent_strength > 0.6:
            opponent_factor *= 0.9
        elif opponent_strength < 0.3:
            opponent_factor *= 1.4
        elif opponent_strength < 0.4:
            opponent_factor *= 1.2

        venue_info = self._venue_lookup.get(venue, {"final_venue_factor": 1.0, "venue_type": "Neutral"})
        venue_factor = venue_info.get("final_venue_factor", 1.0)

        if batting_position <= 2:
            position_factor = 1.3
        elif batting_position <= 4:
            position_factor = 1.2
        elif batting_position <= 6:
            position_factor = 1.0
        else:
            position_factor = 0.75

        recent_series = df["runs_scored"]
        recent_5 = recent_series.tail(5).mean()
        recent_15 = recent_series.tail(15).mean()
        if np.isnan(recent_5):
            recent_5 = player_avg
        if np.isnan(recent_15):
            recent_15 = player_avg
        recent_form = recent_5 - recent_15

        if recent_form > 15:
            form_factor = 1.3
        elif recent_form > 8:
            form_factor = 1.15
        elif recent_form < -15:
            form_factor = 0.7
        elif recent_form < -8:
            form_factor = 0.85
        else:
            form_factor = 1.0

        realistic_float = (
            base_prediction * opponent_factor * venue_factor * position_factor * form_factor
        )

        if realistic_float >= 80:
            runs_predicted = realistic_float
        elif realistic_float >= 50:
            runs_predicted = round(realistic_float / 5) * 5
        elif realistic_float >= 25:
            runs_predicted = round(realistic_float / 2) * 2
        else:
            runs_predicted = round(realistic_float)

        if "World-Class" in player_type and runs_predicted < 20:
            runs_predicted = max(20, runs_predicted)

        return max(runs_predicted, 0)

    def _predict_bowling(
        self,
        player_id: str,
        opponent_team: str,
        venue: str,
        match_type: str,
    ) -> Optional[float]:
        df = self.bowling_raw[self.bowling_raw["player_id"] == player_id].sort_values("date")
        if df.empty:
            return None

        player_avg = df["wickets_taken"].mean()
        player_recent = df.tail(10)["wickets_taken"].mean()
        base_prediction = max(player_avg, player_recent)

        elite_bonus = 0.0
        if player_avg > 2.0:
            elite_bonus = 0.5
        elif player_avg > 1.5:
            elite_bonus = 0.3

        base_prediction += elite_bonus

        opponent_strength = self._T20_RATINGS.get(opponent_team.title(), 180)
        if opponent_strength >= 250:
            opponent_factor = 0.6
        elif opponent_strength >= 220:
            opponent_factor = 0.8
        elif opponent_strength >= 190:
            opponent_factor = 1.0
        elif opponent_strength >= 170:
            opponent_factor = 1.3
        else:
            opponent_factor = 1.6

        venue_upper = venue.lower()
        if "melbourne" in venue_upper or "mcg" in venue_upper:
            venue_factor = 1.2
        elif "perth" in venue_upper or "waca" in venue_upper:
            venue_factor = 1.3
        elif "chennai" in venue_upper or "mumbai" in venue_upper:
            venue_factor = 0.9
        else:
            venue_factor = 1.0

        recent_series = df["wickets_taken"]
        recent_5 = recent_series.tail(5).mean()
        recent_15 = recent_series.tail(15).mean()
        if np.isnan(recent_5):
            recent_5 = player_avg
        if np.isnan(recent_15):
            recent_15 = player_avg
        recent_form = recent_5 - recent_15

        if recent_form > 0.5:
            form_factor = 1.4
        elif recent_form > 0.2:
            form_factor = 1.2
        elif recent_form < -0.5:
            form_factor = 0.6
        elif recent_form < -0.2:
            form_factor = 0.8
        else:
            form_factor = 1.0

        realistic_float = base_prediction * opponent_factor * venue_factor * form_factor

        if realistic_float >= 4.6:
            wickets_predicted = 5
        elif realistic_float >= 3.5:
            wickets_predicted = 4
        elif realistic_float >= 2.7:
            wickets_predicted = 3
        elif realistic_float >= 1.8:
            wickets_predicted = 2
        elif realistic_float >= 0.8:
            wickets_predicted = 1
        else:
            wickets_predicted = 0

        if player_avg > 1.8 and wickets_predicted == 0:
            wickets_predicted = 1

        return float(wickets_predicted)

    # ------------------------------------------------------------------
    # Selection logic
    # ------------------------------------------------------------------

    def _select_best_eleven(
        self, projections: List[PlayerProjection]
    ) -> Tuple[List[PlayerProjection], List[PlayerProjection]]:
        if len(projections) <= 11:
            return projections, []

        team_name = projections[0].team if projections else ""
        match_type = projections[0].match_type if projections else "T20"
        active_info = self._get_active_info(team_name, match_type)
        active_names = set(active_info.keys())

        def is_active(player: PlayerProjection) -> bool:
            return self._normalise_name(player.player_name) in active_names

        def player_score(player: PlayerProjection) -> float:
            bat = player.predicted_runs or 0.0
            bowl = (player.predicted_wickets or 0.0) * 18.0
            activity = 1.0
            if (player.matches_batted or 0) >= 10 or (player.matches_bowled or 0) >= 10:
                activity *= 1.08
            else:
                activity *= 0.94
            if is_active(player):
                activity *= 1.12
            else:
                activity *= 0.85
            if player.batting_recent is not None and player.predicted_runs:
                diff = player.batting_recent - player.predicted_runs
                if diff > 8:
                    activity *= 1.04
                elif diff < -8:
                    activity *= 0.92
            if player.bowling_recent is not None and player.predicted_wickets:
                diff = player.bowling_recent - player.predicted_wickets
                if diff > 0.3:
                    activity *= 1.03
                elif diff < -0.3:
                    activity *= 0.92
            return (bat + bowl) * activity

        def avg_position(player: PlayerProjection) -> float:
            return player.avg_batting_position if player.avg_batting_position is not None else 8.5

        def is_keeper(player: PlayerProjection) -> bool:
            role = (player.role or "").lower()
            return "wicket" in role

        def is_allrounder(player: PlayerProjection) -> bool:
            role = (player.role or "").lower()
            return "all-rounder" in role or "allrounder" in role

        def is_bowler(player: PlayerProjection) -> bool:
            role = (player.role or "").lower()
            overs = player.avg_overs or 0.0
            wickets = player.predicted_wickets or 0.0
            return "bowler" in role or overs >= 2.5 or wickets >= 1.0

        def is_top_order(player: PlayerProjection) -> bool:
            return avg_position(player) <= 3.5

        def is_middle_order(player: PlayerProjection) -> bool:
            pos = avg_position(player)
            return 3.5 < pos <= 5.5

        def is_finisher(player: PlayerProjection) -> bool:
            pos = avg_position(player)
            role = (player.role or "").lower()
            return pos <= 7.2 or "finisher" in role or is_allrounder(player)

        scores = {p.player_id: player_score(p) for p in projections}

        def score_of(player: PlayerProjection) -> float:
            return scores.get(player.player_id, 0.0)

        sorted_by_score = sorted(
            projections,
            key=lambda p: (0 if is_active(p) else 1, -score_of(p)),
        )

        selected: List[PlayerProjection] = []
        selected_ids: set[str] = set()

        def ensure_category(predicate, needed: int) -> None:
            current = sum(1 for p in selected if predicate(p))
            if current >= needed:
                return
            for cand in sorted_by_score:
                if cand.player_id in selected_ids:
                    continue
                if predicate(cand):
                    selected.append(cand)
                    selected_ids.add(cand.player_id)
                    current += 1
                    if current >= needed:
                        break

        ensure_category(is_top_order, 3)
        ensure_category(is_keeper, 1)
        ensure_category(is_middle_order, 2)
        ensure_category(is_allrounder, 1)
        ensure_category(is_bowler, 3)
        ensure_category(is_finisher, 1)

        for cand in sorted_by_score:
            if len(selected) >= 11:
                break
            if cand.player_id in selected_ids:
                continue
            selected.append(cand)
            selected_ids.add(cand.player_id)

        if len(selected) > 11:
            selected.sort(key=lambda p: (avg_position(p), -score_of(p)))
            selected = selected[:11]
            selected_ids = {p.player_id for p in selected}

        remaining = [p for p in projections if p.player_id not in selected_ids]
        bench = sorted(remaining, key=score_of, reverse=True)[:15]

        selected.sort(
            key=lambda p: (
                avg_position(p),
                -score_of(p),
            )
        )
        return selected, bench


__all__ = ["XISelector", "PlayerProjection"]


