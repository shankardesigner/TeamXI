import os
import json
import requests
from time import sleep

# CONFIGURATION
BASE_URL = "https://hs-consumer-api.espncricinfo.com/v1/pages/player/search"
OUTPUT_DIR = "data/players"
os.makedirs(OUTPUT_DIR, exist_ok=True)

#  Replace this with your latest valid token periodically
AUTH_TOKEN = "exp=1762912786~hmac=5accc828fc54f1eaad035e07b64d2d46f292580b15e9c5923ab0c778a46c42eb"

HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "origin": "https://www.espncricinfo.com",
    "referer": "https://www.espncricinfo.com/",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "x-hsci-auth-token": AUTH_TOKEN
}

# COUNTRY LIST
COUNTRIES = [
  { "id": 40, "name": "Afghanistan" },
  { "id": 2,  "name": "Australia" },
  { "id": 25, "name": "Bangladesh" },
  { "id": 1,  "name": "England" },
  { "id": 6,  "name": "India" },
  { "id": 29, "name": "Ireland" },
  { "id": 5,  "name": "New Zealand" },
  { "id": 7,  "name": "Pakistan" },
  { "id": 3,  "name": "South Africa" },
  { "id": 8,  "name": "Sri Lanka" },
  { "id": 4,  "name": "West Indies" },
  { "id": 9,  "name": "Zimbabwe" },
  { "id": 28, "name": "Namibia" },
  { "id": 32, "name": "Nepal" },
  { "id": 15, "name": "Netherlands" },
  { "id": 37, "name": "Oman" },
  { "id": 20, "name": "Papua New Guinea" },
  { "id": 30, "name": "Scotland" },
  { "id": 27, "name": "United Arab Emirates" },
  { "id": 11, "name": "United States of America" }
]

# FUNCTION: fetch_players
def fetch_players(team_id):
    """Fetch both T20 (3) and ODI (2) players for a given country ID."""
    results = {}

    for class_id, fmt in [(2, "odi"), (3, "t20")]:
        params = {
            "mode": "BOTH",
            "page": 1,
            "records": 40,
            "filterActive": "true",
            "filterTeamId": team_id,
            "filterClassId": class_id,
            "filterFormatLevel": "INTERNATIONAL",
            "sort": "ALPHA_ASC"
        }

        try:
            resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=10)
            if resp.status_code == 403:
                print(f" Forbidden for {fmt.upper()} - token expired or invalid.")
                return None
            resp.raise_for_status()
            results[fmt] = resp.json()
        except Exception as e:
            print(f" Error fetching {fmt} for team {team_id}: {e}")
            results[fmt] = None

        sleep(1)
    return results

# MAIN
for c in COUNTRIES:
    name = c["name"].replace(" ", "_")
    print(f" Fetching for {c['name']}...")
    player_data = fetch_players(c["id"])

    if player_data:
        out_path = os.path.join(OUTPUT_DIR, f"{name}_players.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(player_data, f, indent=2, ensure_ascii=False)
        print(f" Saved {name}_players.json\n")
    else:
        print(f" Skipped {c['name']} due to error.\n")

print(" Completed fetching all countries.")
