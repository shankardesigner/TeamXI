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
