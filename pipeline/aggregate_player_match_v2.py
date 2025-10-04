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

# MATCH PHASE (T20/ODI)
def get_phase(over, match_type):
    if match_type == "ODI":
        if over < 10:  return "powerplay"
        elif over < 40: return "middle"
        else:            return "death"
    else:  # T20
        if over < 6:   return "powerplay"
        elif over < 15: return "middle"
        else:            return "death"

df["phase"] = df.apply(lambda x: get_phase(x["over"], x["match_type"]), axis=1)

# BASIC CLEANUP
df = df[df["runs_total"].between(0, 7)]
df = df[df["runs_batsman"].between(0, 6)]
df = df.dropna(subset=["batsman", "bowler"])
df["batsman"] = df["batsman"].str.strip()
df["bowler"]  = df["bowler"].str.strip()
print(f"[INFO] After cleanup: {len(df):,} deliveries")

#  BATSMEN AGGREGATION  (already correct  safe to skip export)
print("[INFO] Aggregating batting data...")
bat_group = [
    "match_id","date","batting_team","batsman","batsman_id",
    "opponent_team","venue","match_type","winner","city","season","team_type"
]
bat = (
    df.groupby(bat_group)
      .agg(
          runs_scored=("runs_batsman","sum"),
          balls_faced=("runs_batsman","count"),
          boundaries=("runs_batsman",lambda x:(x>=4).sum()),
          sixes=("runs_batsman",lambda x:(x==6).sum()),
          dismissals=("wicket_flag","sum")
      ).reset_index()
)
bat["strike_rate"] = (bat["runs_scored"]/bat["balls_faced"]*100).round(2).fillna(0)

first_over = (
    df.groupby(["match_id","batting_team","batsman"])["over"]
      .min().reset_index().rename(columns={"over":"first_over"})
)
bat = bat.merge(first_over,on=["match_id","batting_team","batsman"],how="left")
bat["batting_position"] = (
    bat.groupby(["match_id","batting_team"])["first_over"].rank(method="dense").astype(int)
)

phase_runs = (
    df.groupby(["match_id","batting_team","batsman","phase"])["runs_batsman"]
      .sum().unstack(fill_value=0).reset_index()
)
phase_balls = (
    df.groupby(["match_id","batting_team","batsman","phase"])["runs_batsman"]
      .count().unstack(fill_value=0).reset_index()
)

#  FIXED  use Pandas-safe check instead of .setdefault()
for p in ["powerplay","middle","death"]:
    if p not in phase_runs.columns:
        phase_runs[p] = 0
    if p not in phase_balls.columns:
        phase_balls[p] = 0

phase_runs.columns=["match_id","batting_team","batsman"]+[f"{p}_runs" for p in ["powerplay","middle","death"]]
phase_balls.columns=["match_id","batting_team","batsman"]+[f"{p}_balls" for p in ["powerplay","middle","death"]]
bat = bat.merge(phase_runs,on=["match_id","batting_team","batsman"],how="left")
bat = bat.merge(phase_balls,on=["match_id","batting_team","batsman"],how="left")
bat.fillna(0,inplace=True)
bat.rename(columns={"batsman":"player_name","batsman_id":"player_id"},inplace=True)

#  BOWLING AGGREGATION  (fixed opponent_team)
print("[INFO] Aggregating bowling data...")

bowl_group = [
    "match_id","date","bowler","bowler_id","bowling_team",
    "opponent_team_bowl","venue","match_type","winner","city","season","team_type"
]

bowl = (
    df.groupby(bowl_group)
      .agg(
          runs_conceded=("runs_total","sum"),
          balls_bowled=("runs_total","count"),
          wickets_taken=("wicket_flag","sum"),
          dot_balls=("runs_total",lambda x:(x==0).sum())
      ).reset_index()
)

bowl["overs_bowled"] = (bowl["balls_bowled"]/6).round(2)
bowl["economy_rate"] = (
    bowl["runs_conceded"]/bowl["overs_bowled"].replace(0,pd.NA)
).round(2).fillna(0)

bowl.rename(columns={
    "bowler":"player_name",
    "bowler_id":"player_id",
    "opponent_team_bowl":"opponent_team"
},inplace=True)

# SAVE FILES
os.makedirs(os.path.dirname(OUT_BOWL), exist_ok=True)
bat.to_csv(OUT_BAT,index=False)   # keep or comment out if already done
bowl.to_csv(OUT_BOWL,index=False)

print("="*60)
print(f"[SUCCESS] Bowling summary  {OUT_BOWL}  ({len(bowl):,} rows)")
print(f"Bowling Columns:\n{', '.join(bowl.columns)}")
