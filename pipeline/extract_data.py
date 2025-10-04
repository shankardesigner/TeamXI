import json
import pandas as pd
import os
from glob import glob
from datetime import datetime, timedelta

INPUT_DIR = "data/raw_json/"
OUTPUT_DIR = "data/proceed/"

countries = [
    "Afghanistan","Australia","Bangladesh","Canada","England","Hong Kong",
    "India","Ireland","Kuwait","Namibia","Nepal","Netherlands","New Zealand",
    "Oman","Pakistan","PNG","Scotland","South Africa","Sri Lanka","UAE",
    "Uganda","USA","West Indies","Zimbabwe"
]

os.makedirs(OUTPUT_DIR, exist_ok=True)

json_files = glob(os.path.join(INPUT_DIR, "*.json"))
print(f"Found {len(json_files)} JSON files to process")

print("Extracting international T20/ODI data from last 10 years for selected countries only...")
all_records = []
cutoff_date = datetime.now() - timedelta(days=10*365)

processed_matches = 0
skipped_matches = 0

for file_path in json_files:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        info = data.get("info", {})
        registry = info.get("registry", {}).get("people", {})

        match_type = info.get("match_type", "")
        gender = info.get("gender", "")
        team_type = info.get("team_type", "")

        #  filter only male international T20/ODI matches
        if match_type not in ["T20", "ODI"] or gender != "male" or team_type != "international":
            skipped_matches += 1
            continue

        teams = info.get("teams", [])
        if len(teams) != 2:
            skipped_matches += 1
            continue

        #  filter only if BOTH teams are in our countries list
        if not all(team in countries for team in teams):
            skipped_matches += 1
            continue

        match_id = info.get("match_type_number")
        if not match_id:
            skipped_matches += 1
            continue

        date_str = info.get("dates", [None])[0]
        if not date_str:
            skipped_matches += 1
            continue

        try:
            match_date = datetime.strptime(date_str, "%Y-%m-%d")
            if match_date < cutoff_date:
                skipped_matches += 1
                continue
        except:
            skipped_matches += 1
            continue

        date = date_str
        venue = info.get("venue", "")
        city = info.get("city", "")
        winner = info.get("outcome", {}).get("winner", "")
        season = info.get("season", "")

        match_deliveries = 0
        for inning in data.get("innings", []):
            batting_team = inning.get("team")
            overs = inning.get("overs", [])
            for o in overs:
                over_number = o.get("over")
                deliveries = o.get("deliveries", [])
                for i, delivery in enumerate(deliveries, start=1):
                    batter = delivery.get("batter")
                    bowler = delivery.get("bowler")
                    non_striker = delivery.get("non_striker")

                    runs_batter = delivery.get("runs", {}).get("batter", 0)
                    runs_extras = delivery.get("runs", {}).get("extras", 0)
                    runs_total = delivery.get("runs", {}).get("total", 0)

                    wickets = delivery.get("wickets", [])
                    wicket_flag = 1 if wickets else 0

                    player_out = None
                    dismissal_kind = None
                    if wickets:
                        try:
                            player_out = wickets[0].get("player_out")
                            dismissal_kind = wickets[0].get("kind")
                        except (KeyError, IndexError):
                            pass

                    batter_id = registry.get(batter)
                    bowler_id = registry.get(bowler)

                    extras_detail = delivery.get("extras", {})
                    extras_types = ",".join(extras_detail.keys()) if extras_detail else ""

                    all_records.append({
                        "match_id": match_id,
                        "date": date,
                        "gender": gender,
                        "match_type": match_type,
                        "venue": venue,
                        "city": city,
                        "team_type": team_type,
                        "season": season,
                        "teams": ",".join(teams),
                        "winner": winner,
                        "batting_team": batting_team,
                        "batsman": batter,
                        "batsman_id": batter_id,
                        "bowler": bowler,
                        "bowler_id": bowler_id,
                        "non_striker": non_striker,
                        "over": over_number,
                        "ball_in_over": i,
                        "runs_batsman": runs_batter,
                        "runs_extras": runs_extras,
                        "runs_total": runs_total,
                        "wicket_flag": wicket_flag,
                        "player_out": player_out,
                        "dismissal_kind": dismissal_kind,
                        "extras_types": extras_types
                    })
                    match_deliveries += 1

        processed_matches += 1
        print(f"Processed {os.path.basename(file_path)} - {match_deliveries} deliveries")

    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        continue

print(f"\nProcessing complete:")
print(f"Total JSON files: {len(json_files)}")
print(f"Processed matches: {processed_matches}")
print(f"Skipped matches: {skipped_matches}")
print(f"Total deliveries extracted: {len(all_records)}")

if all_records:
    df = pd.DataFrame(all_records)
    output_path = os.path.join(OUTPUT_DIR, "last_10_years_data.csv")
    df.to_csv(output_path, index=False)

    print(f"\n Saved {len(df)} deliveries to {output_path}")
    print(f"Total matches: {df['match_id'].nunique()}")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"Unique batsmen: {df['batsman'].nunique()}")
    print(f"Unique bowlers: {df['bowler'].nunique()}")
    print(f"Match types: {df['match_type'].value_counts().to_dict()}")
    print(f"Total wickets: {df['wicket_flag'].sum()}")
else:
    print("No records were extracted")
