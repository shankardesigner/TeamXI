# TeamXI

Predicts a best playing XI, per-player runs/wickets projections, and match outcome
for two international teams at a given venue — served by a FastAPI backend with a
React (Vite) frontend.

## Layout

```
app/
├── api.py                # FastAPI server (routes, request/response models)
├── teamxi.py             # XISelector — selection + projection engine
├── data/                 # NOT in git — see "Data" below
│   ├── proceed/          # per-player, per-match feature tables (batting/bowling + rolling form)
│   └── players/          # active_players.json (squads, roles, headshots)
├── models/               # trained LightGBM models (batting / bowling)
├── train/                # model training scripts (Colab)
├── pipeline/             # data prep scripts that build data/proceed/
├── tests/                # pytest suite + trimmed fixtures
├── front-end/            # React + Vite UI
└── Presentation/         # project deck (pdf + pptx)
```

## Run it

Backend (from `app/`):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```

Frontend (from `app/front-end/`):

```bash
npm install
npm run dev
```

The UI defaults to `http://localhost:8000` for the API. Override with `VITE_API_BASE`
in `front-end/.env` if the backend runs elsewhere.

## Data

`data/` is **not** tracked in git. The API needs these five files present before it
will start:

```
data/proceed/player_features_batting.csv
data/proceed/player_features_batting_form.csv
data/proceed/player_features_bowling.csv
data/proceed/player_features_bowling_form.csv
data/players/active_players.json
```

Build them from scratch with the raw Cricsheet ball-by-ball JSON in `data/raw_json/`
(~2.7 GB), running from `app/`:

```bash
python pipeline/extract_data.py                    # raw_json/ -> data/proceed/last_10_years_data.csv
python pipeline/aggregate_player_match_v2.py       # -> player_features_batting.csv, player_features_bowling.csv
python pipeline/batting_form.py                    # -> player_features_batting_form.csv
python pipeline/player_features_bowling_form.py    # -> player_features_bowling_form.csv
python pipeline/crawl_players_by_country.py        # -> data/players/ squads
```

Steps 1–4 are a chain, each reading the previous step's output. Step 5 is independent
and hits the network. The intermediate `last_10_years_data.csv` is ~123 MB and the
four feature tables total ~16 MB.

## Tests

```bash
pip install -r requirements-dev.txt
pytest          # backend: engine + API contract
cd front-end && npm run lint && npm run build
```

Tests run against trimmed fixtures in `tests/fixtures/` (India vs Australia,
~190 KB), so they need neither the real `data/` nor a network. Dates are pinned
to 2025-10-31 so the rolling form window can't slide off the fixtures.

CI runs both suites on every push and PR — see `.github/workflows/ci.yml`.

## Training

`train/batting_train.py` and `train/bowling_train.py` were run in Google Colab and
still reference Google Drive paths; adjust the paths at the top before running locally.
Outputs are the `.pkl` files in `models/`.
