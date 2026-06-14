const apiBase = "/api";

async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const payload = await response.json();
      if (payload?.detail) {
        errorDetail = payload.detail;
      }
    } catch (err) {
      // ignore JSON parse error
    }
    throw new Error(errorDetail || "API request failed");
  }

  return response.json();
}

export async function parsePaper(payload) {
  const response = await fetch(`${apiBase}/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse(response);
}

export async function analyzeEnriched(payload) {
  const response = await fetch(`${apiBase}/analyze/enriched`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse(response);
}

export async function uploadPaper(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${apiBase}/upload`, {
    method: "POST",
    body: formData,
  });
  return handleResponse(response);
}

export async function getControversyMap() {
  const response = await fetch(`${apiBase}/graph/controversy-map`);
  return handleResponse(response);
}

export async function healthCheck() {
  const response = await fetch(`${apiBase}/health`);
  return handleResponse(response);
}

export async function getVisualizationData(payload) {
  const response = await fetch(`${apiBase}/visualize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse(response);
}

export async function analyzeUploadedFile(uid) {
  const response = await fetch(`${apiBase}/analyze/upload/${uid}`, {
    method: "POST",
  });
  return handleResponse(response);
}

export async function visualizeUploadedFile(uid) {
  const response = await fetch(`${apiBase}/visualize/upload/${uid}`);
  return handleResponse(response);
}
