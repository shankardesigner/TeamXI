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
