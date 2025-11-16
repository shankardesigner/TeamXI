"""Selection engine tests, run against tests/fixtures."""
import pytest
from conftest import AS_OF

TEAMS = ("India", "Australia")


@pytest.mark.parametrize("match_type", ["ODI", "T20"])
def test_lists_both_teams(selector, match_type):
    assert sorted(selector.list_teams(match_type)) == ["Australia", "India"]


@pytest.mark.parametrize("match_type", ["ODI", "T20"])
def test_lists_venues_for_matchup(selector, match_type):
    venues = selector.list_venues(match_type, list(TEAMS))
    assert venues, "expected at least one shared venue"
    assert all(isinstance(v, str) and v for v in venues)


def test_unknown_match_type_returns_nothing(selector):
    assert selector.list_teams("TEST") == []


@pytest.mark.parametrize("match_type", ["ODI", "T20"])
def test_generates_eleven_per_side(selector, match_type):
    venue = selector.list_venues(match_type, list(TEAMS))[0]
    (team_a, _), (team_b, _) = selector.generate_match_xi(
        "India", "Australia", match_type, venue, AS_OF
    )
    assert len(team_a) == 11
    assert len(team_b) == 11


def test_no_duplicate_players_in_xi(selector):
    venue = selector.list_venues("ODI", list(TEAMS))[0]
    (team_a, _), _ = selector.generate_match_xi(
        "India", "Australia", "ODI", venue, AS_OF
    )
    ids = [p.player_id for p in team_a]
    assert len(ids) == len(set(ids))


def test_players_belong_to_their_own_team(selector):
    venue = selector.list_venues("ODI", list(TEAMS))[0]
    (team_a, _), (team_b, _) = selector.generate_match_xi(
        "India", "Australia", "ODI", venue, AS_OF
    )
    assert {p.team for p in team_a} == {"India"}
    assert {p.team for p in team_b} == {"Australia"}


def test_xi_is_deterministic(selector):
    venue = selector.list_venues("ODI", list(TEAMS))[0]
    first = selector.generate_match_xi("India", "Australia", "ODI", venue, AS_OF)
    second = selector.generate_match_xi("India", "Australia", "ODI", venue, AS_OF)
    assert [p.player_id for p in first[0][0]] == [p.player_id for p in second[0][0]]


def test_projection_payload_shape(selector):
    venue = selector.list_venues("ODI", list(TEAMS))[0]
    (team_a, _), _ = selector.generate_match_xi(
        "India", "Australia", "ODI", venue, AS_OF
    )
    payload = team_a[0].to_payload()
    for key in ("player_id", "name", "team", "opponent", "match_type", "role"):
        assert key in payload, f"missing {key} in projection payload"
    assert payload["team"] == "India"


def test_every_player_has_a_role(selector):
    venue = selector.list_venues("T20", list(TEAMS))[0]
    (team_a, _), _ = selector.generate_match_xi(
        "India", "Australia", "T20", venue, AS_OF
    )
    assert all(p.role for p in team_a)


def test_predictions_are_non_negative(selector):
    venue = selector.list_venues("T20", list(TEAMS))[0]
    (team_a, _), _ = selector.generate_match_xi(
        "India", "Australia", "T20", venue, AS_OF
    )
    for p in team_a:
        if p.predicted_runs is not None:
            assert p.predicted_runs >= 0
        if p.predicted_wickets is not None:
            assert p.predicted_wickets >= 0
