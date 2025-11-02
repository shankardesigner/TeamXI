import { useEffect, useState } from "react";
import ConfettiOverlay from "../components/ConfettiOverlay.jsx";
import { fetchPredictedXI, fetchTeams, fetchVenues } from "../api/xi.js";

function isBowlingRole(playerType) {
  if (!playerType) {
    return false;
  }
  const normalized = playerType.toLowerCase();
  return (
    normalized.includes("bowler") ||
    normalized.includes("spinner") ||
    normalized.includes("all-rounder") ||
    normalized.includes("allrounder")
  );
}

function toPlayerCard(player, panelKey) {
  const placeholder = `https://api.dicebear.com/7.x/initials/svg?background=0B2239&color=ffffff&scale=110&seed=${encodeURIComponent(
    player.name,
  )}`;
  const headshotPath = player.headshotUrl ? player.headshotUrl.replace(/^\/+/, "") : null;
  const image = headshotPath
    ? `https://img1.hscicdn.com/image/upload/f_auto,t_h_100_2x/${headshotPath}`
    : placeholder;
  return {
    id: player.playerId,
    name: player.name,
    type: player.role,
    image,
    variant: panelKey,
    predictedRuns: player.predictedRuns,
    predictedWickets: player.predictedWickets,
  };
}

function buildRoster({ squad, panelKey }) {
  return {
    title: squad.team,
    subtitle: `${squad.matchType} vs ${squad.opponent}`,
    background: DEFAULT_BACKGROUNDS[panelKey],
    players: squad.selected.map((player) => toPlayerCard(player, panelKey)),
    substitutes: squad.bench.map((player) => ({
      name: player.name,
      role: player.role,
    })),
  };
}

const MATCH_TYPES = ["T20", "ODI"];
const DEFAULT_BACKGROUNDS = {
  teamA: { from: "#0d35a3", to: "#011e66" },
  teamB: { from: "#b3141a", to: "#690406" },
};

export default function XIPredictorPage({ onBack }) {
  const [showConfetti, setShowConfetti] = useState(false);
  const [matchType, setMatchType] = useState(MATCH_TYPES[0]);
  const [teams, setTeams] = useState([]);
  const [venues, setVenues] = useState([]);
  const [teamSelection, setTeamSelection] = useState({ teamA: "", teamB: "" });
  const [selectedVenue, setSelectedVenue] = useState("");
  const [rosters, setRosters] = useState({
    teamA: {
      title: "Team A XI",
      subtitle: "",
      background: DEFAULT_BACKGROUNDS.teamA,
      players: [],
      substitutes: [],
    },
    teamB: {
      title: "Team B XI",
      subtitle: "",
      background: DEFAULT_BACKGROUNDS.teamB,
      players: [],
      substitutes: [],
    },
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleDragStart = (payload) => (event) => {
    event.dataTransfer.setData("application/json", JSON.stringify(payload));
    event.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  };

  const handleDrop = (target) => (event) => {
    event.preventDefault();
    const data = event.dataTransfer.getData("application/json");
    if (!data) {
      return;
    }
    let payload;
    try {
      payload = JSON.parse(data);
    } catch {
      return;
    }
    if (
      !payload ||
      !payload.panelKey ||
      !payload.list ||
      typeof payload.index !== "number"
    ) {
      return;
    }
    if (payload.panelKey !== target.panelKey) {
      return;
    }
    if (payload.list === target.list) {
      return;
    }

    setRosters((prev) => {
      const column = prev[payload.panelKey];
      if (!column) {
        return prev;
      }

      if (
        target.list === "players" &&
        payload.list !== "players" &&
        column.players.length >= 11 &&
        typeof target.index !== "number"
      ) {
        return prev;
      }

      const sourceList = [...column[payload.list]];
      const [moved] = sourceList.splice(payload.index, 1);
      if (!moved) {
        return prev;
      }

      if (payload.list === target.list) {
        const reordered = sourceList;
        const insertIndex =
          typeof target.index === "number" ? target.index : reordered.length;
        reordered.splice(insertIndex, 0, moved);
        return {
          ...prev,
          [payload.panelKey]: {
            ...column,
            [payload.list]: reordered,
          },
        };
      }

      const destinationList = [...(column[target.list] || [])];
      let displaced;

      if (typeof target.index === "number") {
        displaced = destinationList[target.index];
        destinationList.splice(target.index, 1, moved);
      } else {
        destinationList.push(moved);
      }

      if (displaced) {
        sourceList.push(displaced);
      }

      return {
        ...prev,
        [payload.panelKey]: {
          ...column,
          [payload.list]: sourceList,
          [target.list]: destinationList,
        },
      };
    });
  };

  const panelOrder = [
    { key: "teamA", className: "panel panel-asia" },
    { key: "teamB", className: "panel panel-world" },
  ];

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
    const inverseMatchType = matchType === "T20" ? "ODI" : "T20";
    setLoading(true);
    setError("");
    setShowConfetti(false);
    try {
      const response = await fetchPredictedXI({
        teamA: teamSelection.teamA,
        teamB: teamSelection.teamB,
        matchType: inverseMatchType,
        venue: selectedVenue,
      });
      setRosters({
        teamA: buildRoster({ squad: response.teamA, panelKey: "teamA" }),
        teamB: buildRoster({ squad: response.teamB, panelKey: "teamB" }),
      });
      setShowConfetti(true);
    } catch (err) {
      setError(err.message || "Failed to fetch XI predictions");
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

  return (
    <div className="app-shell">
      {showConfetti ? <ConfettiOverlay onComplete={() => setShowConfetti(false)} /> : null}
      <header className="control-bar">
        <button type="button" className="back-button" onClick={onBack}>
          ← Back
        </button>
        <div className="control-group">
          <label htmlFor="match-type">Match Type</label>
          <select
            id="match-type"
            value={matchType}
            onChange={(event) => {
              setMatchType(event.target.value);
              setTeamSelection({ teamA: "", teamB: "" });
              setSelectedVenue("");
              setRosters((prev) => ({
                teamA: { ...prev.teamA, players: [], substitutes: [] },
                teamB: { ...prev.teamB, players: [], substitutes: [] },
              }));
            }}
          >
            {MATCH_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
        <div className="control-group">
          <label htmlFor="team-a">Team A</label>
          <select
            id="team-a"
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
        <div className="control-group">
          <label htmlFor="team-b">Team B</label>
          <select
            id="team-b"
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
        <div className="control-group control-group-venue">
          <label htmlFor="venue">Venue</label>
          <select
            id="venue"
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
        <div className="control-status">
          {error ? <span className="chip chip-error">{error}</span> : null}
          <button
            className="predict-button"
            type="button"
            onClick={handlePredict}
            disabled={
              loading ||
              !teamSelection.teamA ||
              !teamSelection.teamB ||
              !selectedVenue
            }
          >
            {loading ? "Predicting…" : "Predict XI"}
          </button>
        </div>
      </header>
      <div className="duel-container">
        {loading ? (
          <div className="loading-overlay" aria-live="polite">
            <div className="spinner" />
            <span className="loading-text">Predicting XI…</span>
          </div>
        ) : null}
        {panelOrder.map(({ key, className }) => {
          const column = rosters[key];
          return (
            <section
              key={key}
              className={`${className} ${loading ? "panel-blurred" : ""}`}
              style={{
                background: `linear-gradient(155deg, ${column.background.from}, ${column.background.to})`,
              }}
            >
              <header className="panel-header">
                <span className="panel-badge">
                  {key === "teamA" ? "Team A" : "Team B"}
                </span>
                <h1 className="panel-title">{column.title}</h1>
                {/* {column.subtitle ? (
                  <p className="panel-subtitle">{column.subtitle}</p>
                ) : null} */}
              </header>
              <div
                className="panel-grid"
                onDragOver={handleDragOver}
                onDrop={handleDrop({ panelKey: key, list: "players" })}
              >
                {column.players.length === 0 && !loading ? (
                  <div className="panel-empty">Select teams to view predicted XI</div>
                ) : null}
                {column.players.map((player, index) => (
                  <article
                    key={`${player.name}-${index}`}
                    className="panel-player player-draggable"
                    draggable
                    onDragOver={handleDragOver}
                    onDrop={handleDrop({
                      panelKey: key,
                      list: "players",
                      index,
                    })}
                    onDragStart={handleDragStart({
                      panelKey: key,
                      list: "players",
                      index,
                    })}
                  >
                    <div className="player-avatar">
                      <img src={player.image} alt={player.name} />
                      {player.type ? (
                        <span className="player-pill player-pill-center">{player.type}</span>
                      ) : null}
                    </div>
                    <div className="player-text">
                      <span className="player-name">{player.name}</span>
                      {(player.predictedRuns !== null &&
                        player.predictedRuns !== undefined) ||
                      (player.predictedWickets !== null &&
                        player.predictedWickets !== undefined &&
                        (player.predictedWickets !== 0 ||
                          isBowlingRole(player.type))) ? (
                        <span className="player-stat-line">
                          {player.predictedRuns !== null &&
                          player.predictedRuns !== undefined
                            ? `${Math.round(player.predictedRuns)} Runs`
                            : ""}
                          {player.predictedRuns !== null &&
                          player.predictedRuns !== undefined &&
                          player.predictedWickets !== null &&
                          player.predictedWickets !== undefined &&
                          (player.predictedWickets !== 0 ||
                            isBowlingRole(player.type))
                            ? " · "
                            : ""}
                          {player.predictedWickets !== null &&
                          player.predictedWickets !== undefined &&
                          (player.predictedWickets !== 0 ||
                            isBowlingRole(player.type))
                            ? `${Number(player.predictedWickets)
                                .toFixed(1)
                                .replace(/\.0$/, "")} Wkts`
                            : ""}
                        </span>
                      ) : null}
                    </div>
                  </article>
                ))}
              </div>
              {column.substitutes?.length ? (
                <footer className="panel-subs">
                  <span className="subs-label">Substitutes</span>
                  <div
                    className="subs-list"
                    onDragOver={handleDragOver}
                    onDrop={handleDrop({ panelKey: key, list: "substitutes" })}
                  >
                    {column.substitutes.map((sub, index) => (
                      <div
                        key={`${sub.name}-${index}`}
                        className="subs-item player-draggable"
                        draggable
                        onDragOver={handleDragOver}
                        onDrop={handleDrop({
                          panelKey: key,
                          list: "substitutes",
                          index,
                        })}
                        onDragStart={handleDragStart({
                          panelKey: key,
                          list: "substitutes",
                          index,
                        })}
                      >
                        <strong>{sub.name}</strong>
                        <span>{sub.role}</span>
                      </div>
                    ))}
                  </div>
                </footer>
              ) : null}
            </section>
          );
        })}
      </div>
    </div>
  );
}
