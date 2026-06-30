import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const http = axios.create({ baseURL: API });

export const api = {
  // projects
  listProjects: () => http.get("/projects").then((r) => r.data),
  getProject: (id) => http.get(`/projects/${id}`).then((r) => r.data),
  createProject: (payload) => http.post("/projects", payload).then((r) => r.data),
  deleteProject: (id) => http.delete(`/projects/${id}`).then((r) => r.data),

  // settings
  getSettings: () => http.get("/settings").then((r) => r.data),
  updateSettings: (patch) => http.put("/settings", patch).then((r) => r.data),

  // documents
  listDocuments: (projectId) =>
    http.get(`/projects/${projectId}/documents`).then((r) => r.data),
  uploadDocument: (projectId, file) => {
    const fd = new FormData();
    fd.append("file", file);
    return http
      .post(`/projects/${projectId}/documents`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
  getDocument: (id) => http.get(`/documents/${id}`).then((r) => r.data),
  updateDocumentTitle: (id, title) =>
    http.patch(`/documents/${id}`, { title }).then((r) => r.data),
  deleteDocument: (id) => http.delete(`/documents/${id}`).then((r) => r.data),
  getSummary: (id) => http.get(`/documents/${id}/summary`).then((r) => r.data),
  getStatus: (id) => http.get(`/documents/${id}/status`).then((r) => r.data),
  resummarize: (id, model, personaOverride = null) =>
    http
      .post(`/documents/${id}/summarize${model ? `?model=${encodeURIComponent(model)}` : ""}`, personaOverride || {})
      .then((r) => r.data),
  pdfUrl: (id) => `${API}/documents/${id}/pdf`,

  // evidence
  evidenceForClaim: (claimId) =>
    http.post(`/claims/${claimId}/evidence`).then((r) => r.data),
  evidenceForSection: (docId, text) =>
    http.post(`/documents/${docId}/section-evidence`, { text }).then((r) => r.data),

  // outliers
  outliers: (projectId) =>
    http.get(`/projects/${projectId}/outliers`).then((r) => r.data),

  // matrix
  matrix: (projectId, documentIds = null, refresh = false, method = "default") =>
    http
      .post(`/projects/${projectId}/matrix`, { document_ids: documentIds, refresh, method })
      .then((r) => r.data),

  // ask
  ask: (projectId, question) =>
    http
      .post(`/projects/${projectId}/ask`, { question })
      .then((r) => r.data),
};
