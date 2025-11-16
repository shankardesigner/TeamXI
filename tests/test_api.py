"""API contract tests — selector is overridden with fixtures in conftest."""
import pytest
from conftest import AS_OF

AS_OF_ISO = AS_OF.isoformat()


def test_healthcheck(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_teams_endpoint(client):
    res = client.get("/teams", params={"matchType": "ODI"})
    assert res.status_code == 200
    body = res.json()
    assert body["matchType"] == "ODI"
    assert sorted(body["teams"]) == ["Australia", "India"]


def test_teams_lowercase_match_type_is_normalised(client):
    res = client.get("/teams", params={"matchType": "odi"})
    assert res.status_code == 200
    assert res.json()["matchType"] == "ODI"


def test_teams_unknown_match_type_is_404(client):
    res = client.get("/teams", params={"matchType": "TEST"})
    assert res.status_code == 404


def test_venues_endpoint(client):
    res = client.get(
        "/venues", params={"matchType": "ODI", "teamA": "India", "teamB": "Australia"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["teamA"] == "India"
    assert len(body["venues"]) > 0


def test_venues_unknown_teams_is_404(client):
    res = client.get(
        "/venues", params={"matchType": "ODI", "teamA": "Nowhere", "teamB": "Neverland"}
    )
    assert res.status_code == 404


@pytest.mark.parametrize("match_type", ["ODI", "T20"])
def test_predict_xi(client, match_type):
    venues = client.get(
        "/venues",
        params={"matchType": match_type, "teamA": "India", "teamB": "Australia"},
    ).json()["venues"]
    res = client.post(
        "/predict_xi",
        json={
            "teamA": "India",
            "teamB": "Australia",
            "matchType": match_type,
            "venue": venues[0],
            "asOf": AS_OF_ISO,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["matchType"] == match_type
    assert len(body["teamA"]["selected"]) == 11
    assert len(body["teamB"]["selected"]) == 11
    assert body["teamA"]["team"] == "India"


def test_predict_xi_player_payload_is_camel_case(client):
    res = client.post(
        "/predict_xi",
        json={
            "teamA": "India",
            "teamB": "Australia",
            "matchType": "ODI",
            "asOf": AS_OF_ISO,
        },
    )
    assert res.status_code == 200, res.text
    player = res.json()["teamA"]["selected"][0]
    for key in ("playerId", "name", "team", "matchType", "matchesBatted"):
        assert key in player, f"missing {key} in player payload"


def test_predict_xi_missing_team_is_422(client):
    res = client.post("/predict_xi", json={"teamA": "India", "matchType": "ODI"})
    assert res.status_code == 422


def test_predict_match(client):
    res = client.post(
        "/predict_match",
        json={
            "teamA": "India",
            "teamB": "Australia",
            "matchType": "ODI",
            "asOf": AS_OF_ISO,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["venue"]
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["summary"]
