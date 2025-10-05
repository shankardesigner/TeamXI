"""
STAGE 3 (LITE)  Compute rolling bowling form metrics locally
Input : data/proceed/player_features_bowling.csv
Output: data/proceed/player_features_bowling_form.csv
"""

import pandas as pd
from pathlib import Path

# --- paths
INPUT = Path("data/proceed/player_features_bowling.csv")
OUTPUT = Path("data/proceed/player_features_bowling_form.csv")

# --- load
df = pd.read_csv(INPUT)
print(f"[INFO] Loaded {len(df):,} rows")

#  Ensure opponent_team exists
if "opponent_team" not in df.columns:
    # if missing, rebuild using batting_team reference (if present)
    if "batting_team" in df.columns:
        df["opponent_team"] = df["batting_team"]
        print("[FIX] opponent_team column added from batting_team")
    else:
        df["opponent_team"] = "Unknown"
        print("[WARN] opponent_team not found; filled with 'Unknown'")

# --- clean + prepare
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df.sort_values(["player_name", "date"]).reset_index(drop=True)
df = df.fillna({
    "wickets_taken": 0,
    "economy_rate": df["economy_rate"].median() if "economy_rate" in df else 0
})

# --- compute rolling form (last 5 matches)
df["avg_wkts_last_5"] = (
    df.groupby("player_name")["wickets_taken"]
      .rolling(window=5, min_periods=1).mean()
      .reset_index(level=0, drop=True)
)

df["avg_econ_last_5"] = (
    df.groupby("player_name")["economy_rate"]
      .rolling(window=5, min_periods=1).mean()
      .reset_index(level=0, drop=True)
)

# --- composite form score (weighted)
max_wkts = df["avg_wkts_last_5"].max() or 1
max_econ = df["avg_econ_last_5"].max() or 1

df["form_score"] = (
    0.7 * (df["avg_wkts_last_5"] / max_wkts) +             # higher wickets = better
    0.3 * ((max_econ - df["avg_econ_last_5"]) / max_econ)  # lower economy = better
)

# --- clean output order (consistent with batting)
cols_order = [
    'match_id','date','player_name','player_id','bowling_team','opponent_team',
    'venue','match_type','winner','city','season','team_type',
    'runs_conceded','balls_bowled','wickets_taken','dot_balls',
    'overs_bowled','economy_rate',
    'avg_wkts_last_5','avg_econ_last_5','form_score'
]
df = df[[c for c in cols_order if c in df.columns]]

# --- save
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUTPUT, index=False)
print(f"[OK] Saved  {OUTPUT}")
print(f"[INFO] Final shape: {df.shape}")
