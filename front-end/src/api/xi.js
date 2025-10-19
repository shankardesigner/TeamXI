const API_BASE =
  import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    const message = detail?.detail || res.statusText || "Request failed";
    throw new Error(message);
  }

  return res.json();
}

export async function fetchTeams(matchType = "T20") {
  const params = new URLSearchParams({ matchType });
  const data = await request(`/teams?${params.toString()}`);
  return data;
}

export async function fetchVenues({ matchType = "T20", teamA, teamB }) {
  const params = new URLSearchParams({ matchType });
  if (teamA) params.append("teamA", teamA);
  if (teamB) params.append("teamB", teamB);
  const data = await request(`/venues?${params.toString()}`);
  return data;
}

export async function fetchPredictedXI(payload) {
  const data = await request("/predict_xi", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
}
