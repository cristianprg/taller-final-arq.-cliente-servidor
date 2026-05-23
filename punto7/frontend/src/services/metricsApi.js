export async function fetchMetrics() {
  const response = await fetch("http://localhost:8000/admin/metrics", {
    headers: {
      Authorization: "Bearer admin123"
    }
  });

  if (!response.ok) {
    throw new Error("Metrics request failed");
  }

  return response.json();
}

export async function fetchConfig() {
  const response = await fetch("http://localhost:8000/admin/config", {
    headers: {
      Authorization: "Bearer admin123"
    }
  });

  if (!response.ok) {
    throw new Error("Config request failed");
  }

  return response.json();
}

export async function updateConfig(payload) {
  const response = await fetch("http://localhost:8000/admin/config", {
    method: "POST",
    headers: {
      Authorization: "Bearer admin123",
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error("Config update failed");
  }

  return response.json();
}
