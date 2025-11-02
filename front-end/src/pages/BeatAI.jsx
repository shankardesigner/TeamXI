import { useEffect, useState } from "react";
import { fetchPredictedXI, fetchTeams, fetchVenues } from "../api/xi.js";
import ConfettiOverlay from "../components/ConfettiOverlay.jsx";

const MATCH_TYPES = ["T20", "ODI"];

function buildPlayerCard(player) {
  const placeholder = `https://api.dicebear.com/7.x/initials/svg?background=0B2239&color=ffffff&scale=110&seed=${encodeURIComponent(
    player.name,
  )}`;
  const headshotPath = player.headshotUrl ? player.headshotUrl.replace(/^\/+/, "") : null;
  const image = headshotPath
    ? `https://img1.hscicdn.com/image/upload/f_auto,t_h_100_2x/${headshotPath}`
    : placeholder;
  return {
    key: `${player.playerId}-${Math.random().toString(36).slice(2)}`,
    id: player.playerId,
    name: player.name,
    role: player.role,
    image,
    predictedRuns: player.predictedRuns,
    predictedWickets: player.predictedWickets,
  };
}

export default function BeatAIPage({ onBack }) {
  const [matchType, setMatchType] = useState(MATCH_TYPES[0]);
  const [teams, setTeams] = useState([]);
  const [venues, setVenues] = useState([]);
  const [teamSelection, setTeamSelection] = useState({ teamA: "", venue: "" });
  const [userXI, setUserXI] = useState([]);
  const [bench, setBench] = useState([]);
  const [aiXI, setAiXI] = useState([]);
  const [pendingAiXI, setPendingAiXI] = useState([]);
  const [squadLoading, setSquadLoading] = useState(false);
  const [error, setError] = useState("");
  const [showConfetti, setShowConfetti] = useState(false);
  const [comparison, setComparison] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function loadTeams() {
      try {
        const response = await fetchTeams(matchType);
        if (cancelled) return;
        const available = response.teams ?? [];
        setTeams(available);
        setError("");
        setTeamSelection((current) => {
          const nextTeam = available.includes(current.teamA) ? current.teamA : available[0] || "";
          return {
            teamA: nextTeam,
            venue: nextTeam === current.teamA ? current.venue : "",
          };
        });
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Failed to load teams");
          setTeams([]);
          setTeamSelection({ teamA: "", venue: "" });
        }
      }
    }
    loadTeams();
    return () => {
      cancelled = true;
    };
  }, [matchType]);

  useEffect(() => {
    if (!teamSelection.teamA) {
      setVenues([]);
      setTeamSelection((current) => ({ ...current, venue: "" }));
      return;
    }
    let cancelled = false;
    async function loadVenues() {
      try {
        const response = await fetchVenues({
          matchType,
          teamA: teamSelection.teamA,
        });
        if (cancelled) return;
        const available = response.venues ?? [];
        setVenues(available);
        setError("");
        setTeamSelection((current) => {
          const nextVenue = available.includes(current.venue) ? current.venue : available[0] || "";
          return { ...current, venue: nextVenue };
        });
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Failed to load venues");
          setVenues([]);
          setTeamSelection((current) => ({ ...current, venue: "" }));
        }
      }
    }
    loadVenues();
    return () => {
      cancelled = true;
    };
  }, [matchType, teamSelection.teamA]);

  useEffect(() => {
    if (!teamSelection.teamA || !teamSelection.venue) {
      setBench([]);
      setUserXI([]);
      setAiXI([]);
      setPendingAiXI([]);
      setShowConfetti(false);
      setComparison(null);
      return;
    }
    let cancelled = false;
    async function loadSquad() {
      setSquadLoading(true);
      setError("");
      try {
        const response = await fetchPredictedXI({
          teamA: teamSelection.teamA,
          teamB: teamSelection.teamA,
          matchType,
          venue: teamSelection.venue,
        });
        if (cancelled) return;
        const squad = response.teamA;
        const rosterPlayers = squad.selected.map(buildPlayerCard);
        const benchPlayers = squad.bench.map(buildPlayerCard);
        const combined = [...rosterPlayers, ...benchPlayers].sort((a, b) => a.name.localeCompare(b.name));
        setBench(combined);
        setUserXI([]);
        setAiXI([]);
        setPendingAiXI(rosterPlayers);
        // Store AI squad for later comparison
        setShowConfetti(false);
        setComparison(null);
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Failed to load squad");
          setBench([]);
          setUserXI([]);
          setAiXI([]);
          setPendingAiXI([]);
          setComparison(null);
          // Clear pending AI squad on error
        }
      } finally {
        if (!cancelled) {
          setSquadLoading(false);
        }
      }
    }
    loadSquad();
    return () => {
      cancelled = true;
    };
  }, [matchType, teamSelection.teamA, teamSelection.venue]);

  const handleAddToUserXI = (index) => {
    if (userXI.length >= 11) {
      setError("You already have 11 players selected.");
      return;
    }
    let selectedPlayer = null;
    const updatedBench = [...bench];
    if (index < 0 || index >= updatedBench.length) {
      return;
    }
    const [player] = updatedBench.splice(index, 1);
    selectedPlayer = player;
    setBench(updatedBench);
    if (!selectedPlayer) {
      return;
    }
    setUserXI((prev) => {
      if (prev.find((p) => p.id === selectedPlayer.id) || prev.length >= 11) {
        // put it back
        setBench((prevBench) =>
          [...prevBench, selectedPlayer].sort((a, b) => a.name.localeCompare(b.name)),
        );
        return prev;
      }
      setError("");
      setAiXI([]);
      setComparison(null);
      setShowConfetti(false);
      return [...prev, selectedPlayer];
    });
  };

  const handleRemoveFromUserXI = (index) => {
    const updatedXI = [...userXI];
    if (index < 0 || index >= updatedXI.length) {
      return;
    }
    const [removedPlayer] = updatedXI.splice(index, 1);
    setUserXI(updatedXI);
    setError("");
    setBench((prevBench) =>
      [...prevBench, removedPlayer].sort((a, b) => a.name.localeCompare(b.name)),
    );
    setAiXI([]);
    setComparison(null);
    setShowConfetti(false);
  };

  const handleBeatTheAI = () => {
    if (!teamSelection.teamA || !teamSelection.venue) {
      setError("Select a team and venue first");
      return;
    }
    if (pendingAiXI.length === 0) {
      setError("AI XI is not ready yet. Please try again in a moment.");
      return;
    }
    if (userXI.length !== 11) {
      setError("Pick 11 players for your XI before challenging the AI.");
      return;
    }
    setError("");
    const aiLineup = pendingAiXI;
    const userImpact = userXI.reduce((total, player) => {
      const runs = player.predictedRuns || 0;
      const wkts = player.predictedWickets || 0;
      return total + runs + wkts * 18;
    }, 0);
    const aiImpact = aiLineup.reduce((total, player) => {
      const runs = player.predictedRuns || 0;
      const wkts = player.predictedWickets || 0;
      return total + runs + wkts * 18;
    }, 0);
    const userWins = userImpact > aiImpact;
    setAiXI(aiLineup);
    setComparison({
      userImpact,
      aiImpact,
      outcome: userWins ? "user" : "ai",
    });
    setShowConfetti(userWins);
  };

  const canBeat =
    !squadLoading && teamSelection.teamA && teamSelection.venue && userXI.length === 11 && pendingAiXI.length > 0;

  return (
    <div className="beat-shell">
      {showConfetti ? <ConfettiOverlay onComplete={() => setShowConfetti(false)} /> : null}

      <header className="beat-header">
        <div className="beat-headline">
          <div className="beat-headline-top">
            <h1>Beat the AI (Fantasy Challenge)</h1>
            <button type="button" className="back-button beat-back-button" onClick={onBack}>
              ← Back
            </button>
          </div>
          <p>
            Pick your best XI against the AI-selected lineup. Select players from the bench, then hit Beat the AI to see
            who comes out on top.
          </p>
        </div>
        <div className="beat-controls">
          <div className="beat-control-group">
            <label htmlFor="beat-match-type">Match Type</label>
            <select
              id="beat-match-type"
              value={matchType}
              onChange={(event) => {
                const nextType = event.target.value;
                setMatchType(nextType);
                setTeamSelection({ teamA: "", venue: "" });
                setBench([]);
                setUserXI([]);
                setAiXI([]);
                setPendingAiXI([]);
                // Reset pending AI squad until new data loads
                setShowConfetti(false);
                setComparison(null);
              }}
            >
              {MATCH_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>

          <div className="beat-control-group">
            <label htmlFor="beat-team">Team</label>
            <select
              id="beat-team"
              value={teamSelection.teamA}
              onChange={(event) => {
                const nextTeam = event.target.value;
                setTeamSelection({ teamA: nextTeam, venue: "" });
                setBench([]);
                setUserXI([]);
                setAiXI([]);
                setPendingAiXI([]);
                // Reset pending AI squad until new data loads
                setShowConfetti(false);
                setComparison(null);
              }}
            >
              <option value="" disabled>
                Select team
              </option>
              {teams.map((team) => (
                <option key={team} value={team}>
                  {team}
                </option>
              ))}
            </select>
          </div>

          <div className="beat-control-group">
            <label htmlFor="beat-venue">Venue</label>
            <select
              id="beat-venue"
              value={teamSelection.venue}
              onChange={(event) => {
                const nextVenue = event.target.value;
                setTeamSelection((current) => ({ ...current, venue: nextVenue }));
                setBench([]);
                setUserXI([]);
                setAiXI([]);
                setPendingAiXI([]);
                setShowConfetti(false);
                setComparison(null);
              }}
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
            className="predict-button beat-action-button"
            onClick={handleBeatTheAI}
            disabled={!canBeat}
          >
            Beat Me
          </button>
        </div>
      </header>

      {error ? <div className="match-error">{error}</div> : null}
      {comparison ? (
        <div className={`beat-result beat-result-${comparison.outcome}`}>
          <h2>{comparison.outcome === "user" ? "Congratulations!" : "AI Beats You"}</h2>
          <p>
            Your XI impact: <strong>{comparison.userImpact.toFixed(1)}</strong> · AI impact:{" "}
            <strong>{comparison.aiImpact.toFixed(1)}</strong>
          </p>
        </div>
      ) : null}

      <section className="beat-body">
        <div className="beat-column">
          <h2>Your XI</h2>
          <div className="beat-xi">
            {userXI.length === 0 ? (
              <div className="beat-bench-empty">Select players from the bench to build your XI.</div>
            ) : null}
            {userXI.map((player, index) => (
              <article key={player.key} className="beat-card">
                <div className="beat-avatar">
                  <img src={player.image} alt={player.name} />
                </div>
                <div className="beat-text">
                  <span className="beat-name">{player.name}</span>
                  <span className="beat-role">{player.role}</span>
                  <div className="beat-metrics">
                    <span>Runs {Math.round(player.predictedRuns || 0)}</span>
                    <span>Wkts {(player.predictedWickets || 0).toFixed(1)}</span>
                  </div>
                </div>
                <button type="button" className="beat-remove" onClick={() => handleRemoveFromUserXI(index)}>
                  Remove
                </button>
              </article>
            ))}
          </div>
        </div>

        <div className="beat-column">
          <h2>Available Players</h2>
          <p className="bench-note">Choose players into your XI to challenge the AI.</p>
          <div className="beat-bench">
            {squadLoading ? (
              <div className="beat-bench-empty">Loading players…</div>
            ) : bench.length === 0 ? (
              <div className="beat-bench-empty">Select a team and venue to load available players.</div>
            ) : (
              bench.map((player, index) => (
                <article key={player.key} className="beat-card beat-card-bench">
                  <div className="beat-avatar">
                    <img src={player.image} alt={player.name} />
                  </div>
                  <div className="beat-text">
                    <span className="beat-name">{player.name}</span>
                    <span className="beat-role">{player.role}</span>
                  </div>
                <button
                  type="button"
                  className="beat-add"
                  onClick={() => handleAddToUserXI(index)}
                  disabled={userXI.length >= 11}
                >
                    Add
                  </button>
                </article>
              ))
            )}
          </div>
        </div>

        <div className="beat-column">
          <h2>AI XI</h2>
          <div className="beat-xi ai-xi">
            {aiXI.length === 0 ? (
              <div className="beat-bench-empty">Hit Beat the AI to reveal the AI XI.</div>
            ) : null}
            {aiXI.map((player) => (
              <article key={player.key} className="beat-card">
                <div className="beat-avatar">
                  <img src={player.image} alt={player.name} />
                </div>
                <div className="beat-text">
                  <span className="beat-name">{player.name}</span>
                  <span className="beat-role">{player.role}</span>
                  <div className="beat-metrics">
                    <span>Runs {Math.round(player.predictedRuns || 0)}</span>
                    <span>Wkts {(player.predictedWickets || 0).toFixed(1)}</span>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

