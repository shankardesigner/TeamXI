"""
STAGE 3 (LITE)  Compute rolling form metrics locally
Input : data/proceed/player_features_batting.csv
Output: data/proceed/player_features_batting_form.csv
"""

import pandas as pd
from pathlib import Path

# --- paths
INPUT = Path("data/proceed/player_features_batting.csv")
OUTPUT = Path("data/proceed/player_features_batting_form.csv")

# --- load
df = pd.read_csv(INPUT)
print(f"[INFO] Loaded {len(df):,} rows")

# ensure date sort
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df.sort_values(["player_name", "date"]).reset_index(drop=True)

# --- compute rolling form (last 5 matches)
df["avg_runs_last_5"] = (
    df.groupby("player_name")["runs_scored"]
      .rolling(window=5, min_periods=1).mean()
      .reset_index(level=0, drop=True)
)

df["avg_sr_last_5"] = (
    df.groupby("player_name")["strike_rate"]
      .rolling(window=5, min_periods=1).mean()
      .reset_index(level=0, drop=True)
)

# --- composite form score (weighted 70/30)
df["form_score"] = (0.7 * df["avg_runs_last_5"]/df["avg_runs_last_5"].max() +
                    0.3 * df["avg_sr_last_5"]/df["avg_sr_last_5"].max())

# --- save
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUTPUT, index=False)
print(f"[OK] Saved  {OUTPUT}")
