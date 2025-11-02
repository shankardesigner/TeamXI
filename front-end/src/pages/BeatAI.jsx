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
