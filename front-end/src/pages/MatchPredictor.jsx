import { useEffect, useMemo, useState } from "react";
import { fetchMatchPrediction, fetchTeams, fetchVenues } from "../api/xi.js";

const MATCH_TYPES = ["T20", "ODI"];

export default function MatchPredictorPage({ onNavigateXI }) {
  const [matchType, setMatchType] = useState(MATCH_TYPES[0]);
  const [teams, setTeams] = useState([]);
  const [venues, setVenues] = useState([]);
  const [teamSelection, setTeamSelection] = useState({ teamA: "", teamB: "" });
  const [selectedVenue, setSelectedVenue] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const probabilities = useMemo(() => {
    if (!result) {
      return { teamA: 0.5, teamB: 0.5 };
    }
    return {
      teamA: result.teamA.winProbability,
      teamB: result.teamB.winProbability,
    };
  }, [result]);

  useEffect(() => {
    let cancelled = false;
    async function loadTeams() {
      try {
        const response = await fetchTeams(matchType);
        if (cancelled) return;
        setTeams(response.teams);
        setError("");
        setTeamSelection((current) => {
          const next = { ...current };
          const available = response.teams;
          if (!available.includes(next.teamA)) {
            next.teamA = available[0] || "";
          }
          if (!available.includes(next.teamB) || next.teamA === next.teamB) {
            next.teamB =
              available.find((team) => team !== next.teamA) || available[0] || "";
          }
          return next;
        });
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Failed to load teams");
        }
      }
    }
    loadTeams();
    return () => {
      cancelled = true;
    };
  }, [matchType]);

  useEffect(() => {
    let cancelled = false;
    async function loadVenues() {
      if (!teamSelection.teamA || !teamSelection.teamB) return;
      try {
        const response = await fetchVenues({
          matchType,
          teamA: teamSelection.teamA,
          teamB: teamSelection.teamB,
        });
        if (cancelled) return;
        setVenues(response.venues);
        setError("");
        setSelectedVenue((current) =>
          response.venues.includes(current) ? current : response.venues[0] || "",
        );
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Failed to load venues");
          setVenues([]);
          setSelectedVenue("");
        }
      }
    }
    loadVenues();
    return () => {
      cancelled = true;
    };
  }, [matchType, teamSelection]);

  const handlePredict = async () => {
    if (!teamSelection.teamA || !teamSelection.teamB || !selectedVenue) {
      setError("Select teams and venue first");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const inverseMatchType = matchType === "T20" ? "ODI" : "T20";
      const response = await fetchMatchPrediction({
        teamA: teamSelection.teamA,
        teamB: teamSelection.teamB,
        matchType: inverseMatchType,
        venue: selectedVenue,
      });
      setResult(response);
    } catch (err) {
      setError(err.message || "Failed to predict match outcome");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleTeamChange = (panelKey) => (event) => {
    const value = event.target.value;
    setTeamSelection((current) => {
      const otherKey = panelKey === "teamA" ? "teamB" : "teamA";
      if (current[otherKey] === value) {
        return current;
      }
      return { ...current, [panelKey]: value };
    });
  };

  const handleVenueChange = (event) => {
    setSelectedVenue(event.target.value);
  };

  const probabilityA = Math.round(probabilities.teamA * 100);
  const probabilityB = Math.round(probabilities.teamB * 100);

  return (
    <div className="match-shell">
      <section className="match-header">
        <div className="match-headline">
          <h1>Match Outcome Predictor</h1>
          <p>
            Choose two teams, the venue and format to simulate who holds the edge.
            The model aggregates XI predictions, batting depth and wicket threat to
            surface strengths and risks for both sides.
          </p>
        </div>
        <div className="match-controls">
          <div className="match-control-group">
            <label htmlFor="match-type-home">Match Type</label>
            <select
              id="match-type-home"
              value={matchType}
              onChange={(event) => {
                setMatchType(event.target.value);
                setTeamSelection({ teamA: "", teamB: "" });
                setSelectedVenue("");
                setResult(null);
              }}
            >
              {MATCH_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>
          <div className="match-control-group">
            <label htmlFor="match-team-a">Team A</label>
            <select
              id="match-team-a"
              value={teamSelection.teamA}
              onChange={handleTeamChange("teamA")}
            >
              <option value="" disabled>
                Select team
              </option>
              {teams
                .filter((team) => team !== teamSelection.teamB)
                .map((team) => (
                  <option key={team} value={team}>
                    {team}
                  </option>
                ))}
            </select>
          </div>
          <div className="match-control-group">
            <label htmlFor="match-team-b">Team B</label>
            <select
              id="match-team-b"
              value={teamSelection.teamB}
              onChange={handleTeamChange("teamB")}
            >
              <option value="" disabled>
                Select team
              </option>
              {teams
                .filter((team) => team !== teamSelection.teamA)
                .map((team) => (
                  <option key={team} value={team}>
                    {team}
                  </option>
                ))}
            </select>
          </div>
          <div className="match-control-group venue">
            <label htmlFor="match-venue">Venue</label>
            <select
              id="match-venue"
              value={selectedVenue}
              onChange={handleVenueChange}
              disabled={!venues.length}
            >
              {!venues.length ? <option value="">No venues</option> : null}
              {venues.map((venue) => (
                <option key={venue} value={venue}>
                  {venue}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            className="predict-button match-predict-button"
            onClick={handlePredict}
            disabled={
              loading ||
              !teamSelection.teamA ||
              !teamSelection.teamB ||
              !selectedVenue
            }
          >
            {loading ? "Predicting…" : "Predict Outcome"}
          </button>
        </div>
      </section>

      <div className="match-body">
        {error ? <div className="match-error">{error}</div> : null}

        {loading ? (
          <div className="loading-overlay" aria-live="polite">
            <div className="spinner" />
            <span className="loading-text">Predicting outcome…</span>
          </div>
        ) : null}

        {result ? (
          <section className="match-results">
            <article className="match-summary">
              <h2>Projected Outcome</h2>
              <div className="probability-bar" aria-hidden="true">
                <div
                  className="probability-segment probability-a"
                  style={{ width: `${probabilityA}%` }}
                >
                  <span>{result.teamA.team}</span>
                  <strong>{probabilityA}%</strong>
                </div>
                <div
                  className="probability-segment probability-b"
                  style={{ width: `${probabilityB}%` }}
                >
                  <strong>{probabilityB}%</strong>
                  <span>{result.teamB.team}</span>
                </div>
              </div>
              <p className="summary-text">{result.summary}</p>
            </article>

            <div className="team-insights-grid">
              {[result.teamA, result.teamB].map((team, index) => (
                <article
                  key={team.team}
                  className={`team-insight-card ${index === 0 ? "team-a" : "team-b"}`}
                >
                  <header className="team-card-header">
                    <div>
                      <h3>{team.team}</h3>
                      <p>vs {team.opponent}</p>
                    </div>
                    <div className="team-probability">
                      <span>Win chance</span>
                      <strong>{Math.round(team.winProbability * 100)}%</strong>
                    </div>
                  </header>

                  <div className="team-metrics">
                    <div className="metric metric-runs">
                      <span className="metric-label">Expected Runs</span>
                      <span className="metric-value">{Math.round(team.expectedRuns)}</span>
                    </div>
                    <div className="metric metric-wickets">
                      <span className="metric-label">Expected Wickets</span>
                      <span className="metric-value">{team.expectedWickets.toFixed(1)}</span>
                    </div>
                    <div className="metric metric-batting">
                      <span className="metric-label">Batting Rating</span>
                      <span className="metric-value">{team.battingRating.toFixed(0)}</span>
                    </div>
                    <div className="metric metric-bowling">
                      <span className="metric-label">Bowling Rating</span>
                      <span className="metric-value">{team.bowlingRating.toFixed(0)}</span>
                    </div>
                  </div>

                  <div className="insight-columns">
                    <div>
                      <h4>Strengths</h4>
                      <ul>
                        {team.strengths.map((point) => (
                          <li key={point}>{point}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <h4>Risks</h4>
                      <ul>
                        {(team.weaknesses.length ? team.weaknesses : ["No obvious weaknesses detected"]).map(
                          (point) => (
                            <li key={point}>{point}</li>
                          ),
                        )}
                      </ul>
                    </div>
                  </div>

                  <div className="key-players">
                    <div>
                      <h4>Key Batters</h4>
                      <ul>
                        {(team.keyBatters ?? []).map((player) => (
                          <li key={`${team.team}-${player.name}-bat`}>
                            <strong>{player.name}</strong>
                            {player.predictedRuns != null ? (
                              <span>{Math.round(player.predictedRuns)} runs</span>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <h4>Strike Bowlers</h4>
                      <ul>
                        {(team.keyBowlers ?? []).map((player) => (
                          <li key={`${team.team}-${player.name}-bowl`}>
                            <strong>{player.name}</strong>
                            {player.predictedWickets != null ? (
                              <span>{Number(player.predictedWickets).toFixed(1)} wkts</span>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ) : (
          <section className="match-placeholder">
            <div className="placeholder-card">
              <h2>Select match details to see the projected winner</h2>
              <p>
                Pick teams, venue and format, then hit Predict Outcome to generate
                win probabilities plus tactical talking points for both sides.
              </p>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
