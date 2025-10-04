"""
STAGE 2  Aggregate ball-by-ball  Batting & Bowling summaries
====================================================================
Input : data/proceed/last_10_years_data.csv
Output:
  data/proceed/player_features_batting.csv
  data/proceed/player_features_bowling.csv
"""

import os
import pandas as pd

# CONFIG
INPUT_PATH = "data/proceed/last_10_years_data.csv"
OUT_BAT   = "data/proceed/player_features_batting.csv"
OUT_BOWL  = "data/proceed/player_features_bowling.csv"

# LOAD DATA
df = pd.read_csv(INPUT_PATH)
print(f"[INFO] Loaded {len(df):,} deliveries from {INPUT_PATH}")
print(f"[INFO] Matches: {df['match_id'].nunique()} | "
      f"Batsmen: {df['batsman'].nunique()} | Bowlers: {df['bowler'].nunique()}")

# TEAM MAPPING
def get_opponent(row):
    teams = str(row["teams"]).split(",")
    for t in teams:
        if t.strip() != row["batting_team"]:
            return t.strip()
    return None

df["opponent_team"] = df.apply(get_opponent, axis=1)
df["bowling_team"]  = df["opponent_team"]
#  for bowlers, the team bowled against is the batting_team
df["opponent_team_bowl"] = df["batting_team"]
