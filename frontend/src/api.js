const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 204) return null;
  const body = await res.json();
  if (!res.ok) {
    const detail =
      body && typeof body === "object"
        ? Object.entries(body).map(([k, v]) => `${k}: ${[].concat(v).join("；")}`).join("\n")
        : String(body);
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return body;
}

export const api = {
  listContracts: () => request("/contracts/"),
  getContract: (id, asOf) =>
    request(`/contracts/${id}/check_plan/?as_of=${asOf}`),
  getSummary: (asOf) => request(`/summary/?as_of=${asOf}`),
  getRecognition: (asOf) => request(`/recognition/?as_of=${asOf}`),
  addEvidence: (cid, payload) =>
    request(`/contracts/${cid}/evidences`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  addUsage: (cid, payload) =>
    request(`/contracts/${cid}/usage`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
