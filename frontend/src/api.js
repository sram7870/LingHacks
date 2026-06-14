const apiBase = "/api";

async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const payload = await response.json();
      if (payload?.detail) {
        errorDetail = typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail);
      }
    } catch (e) {
      // fallback
    }
    throw new Error(errorDetail);
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

export async function analyzeRelational(payload) {
  const response = await fetch(`${apiBase}/analyze/relational`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse(response);
}

// --- Landscape Management ---

export async function listLandscapes() {
  const response = await fetch(`${apiBase}/landscapes`);
  return handleResponse(response);
}

export async function createLandscape(name, description = "") {
  const response = await fetch(`${apiBase}/landscapes?name=${encodeURIComponent(name)}&description=${encodeURIComponent(description)}`, {
    method: "POST"
  });
  return handleResponse(response);
}

export async function getLandscape(id) {
  const response = await fetch(`${apiBase}/landscapes/${id}`);
  return handleResponse(response);
}

export async function deleteLandscape(id) {
  const response = await fetch(`${apiBase}/landscapes/${id}`, {
    method: "DELETE"
  });
  return handleResponse(response);
}

export async function addPaperToLandscape(landscapeId, paperId) {
  const response = await fetch(`${apiBase}/landscapes/${encodeURIComponent(landscapeId)}/papers?paper_id=${encodeURIComponent(paperId)}`, {
    method: "POST"
  });
  return handleResponse(response);
}

export async function analyzeLandscape(landscapeId) {
  const response = await fetch(`${apiBase}/landscapes/${landscapeId}/analyze`, {
    method: "POST"
  });
  return handleResponse(response);
}

// --- RPA Specialized ---

export async function rpaUploadPaper(file, landscapeId = null) {
  const formData = new FormData();
  formData.append("file", file);
  let url = `${apiBase}/rpa/upload`;
  if (landscapeId) url += `?landscape_id=${encodeURIComponent(landscapeId)}`;
  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });
  return handleResponse(response);
}

export async function rpaAnalyzePaper(paperId, landscapeId = null) {
  let url = `${apiBase}/rpa/analyze?paper_id=${encodeURIComponent(paperId)}`;
  if (landscapeId) url += `&landscape_id=${encodeURIComponent(landscapeId)}`;
  const response = await fetch(url);
  return handleResponse(response);
}

// --- Legacy & General ---

export async function uploadPaper(file, landscapeId = null) {
  const formData = new FormData();
  formData.append("file", file);
  let url = `${apiBase}/upload`;
  if (landscapeId) url += `?landscape_id=${landscapeId}`;
  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });
  return handleResponse(response);
}

export async function analyzeUploadedFile(uid) {
  const response = await fetch(`${apiBase}/analyze/upload/${uid}`, {
    method: "POST"
  });
  return handleResponse(response);
}

export async function visualizePaper(paperId) {
  const response = await fetch(`${apiBase}/visualize/paper/${encodeURIComponent(paperId)}`);
  return handleResponse(response);
}

export const visualizeUploadedFile = visualizePaper;

export async function getControversyMap(landscapeId = null) {
  let url = `${apiBase}/graph/controversy-map`;
  if (landscapeId) url += `?landscape_id=${landscapeId}`;
  const response = await fetch(url);
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

export async function healthCheck() {
  const response = await fetch(`${apiBase}/health`);
  return handleResponse(response);
}
