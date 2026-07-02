import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const TOKEN_KEY = "jurnalmap.token";

const http = axios.create({ baseURL: API });

// Request interceptor: attach bearer token if present.
http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers = config.headers || {};
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: on 401 (expired/invalid token), clear token and
// redirect to /login unless we are already on an auth screen.
http.interceptors.response.use(
  (resp) => resp,
  (err) => {
    if (err?.response?.status === 401) {
      const p = window.location.pathname;
      const onAuthPage = p === "/login" || p === "/register" || p === "/forgot-password";
      // Do not force-redirect when the 401 came from a login attempt itself
      const isAuthEndpoint = /\/auth\/(login|register|forgot-password)$/.test(err.config?.url || "");
      if (!onAuthPage && !isAuthEndpoint) {
        localStorage.removeItem(TOKEN_KEY);
        window.location.assign("/login");
      }
    }
    return Promise.reject(err);
  },
);

export const api = {
  // ── Auth ──────────────────────────────────────────────────
  login: (username, password) =>
    http.post("/auth/login", { username, password }).then((r) => r.data),
  register: (payload) =>
    http.post("/auth/register", payload).then((r) => r.data),
  forgotPassword: (payload) =>
    http.post("/auth/forgot-password", payload).then((r) => r.data),
  changePassword: (current_password, new_password) =>
    http.post("/auth/change-password", { current_password, new_password }).then((r) => r.data),
  me: () => http.get("/auth/me").then((r) => r.data),

  // ── Projects ─────────────────────────────────────────────────
  listProjects: () => http.get("/projects").then((r) => r.data),
  getProject: (id) => http.get(`/projects/${id}`).then((r) => r.data),
  createProject: (payload) => http.post("/projects", payload).then((r) => r.data),
  deleteProject: (id) => http.delete(`/projects/${id}`).then((r) => r.data),

  // ── Settings ─────────────────────────────────────────────────
  getSettings: () => http.get("/settings").then((r) => r.data),
  updateSettings: (patch) => http.put("/settings", patch).then((r) => r.data),
  getConfig: () => http.get("/config").then((r) => r.data),

  // ── Documents ────────────────────────────────────────────────
  listDocuments: (projectId) =>
    http.get(`/projects/${projectId}/documents`).then((r) => r.data),
  /**
   * Upload one or more PDF files to a project. Accepts a single File or an
   * array of Files (max 5). The backend endpoint is
   * `POST /projects/{id}/documents` and expects the multipart field name
   * `files` (plural) for every file part.
   */
  uploadDocuments: (projectId, filesInput) => {
    const files = Array.isArray(filesInput) ? filesInput : [filesInput];
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    return http
      .post(`/projects/${projectId}/documents`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
  retryDocument: (id) => http.post(`/documents/${id}/retry`).then((r) => r.data),
  queue: (projectId) => http.get(`/projects/${projectId}/queue`).then((r) => r.data),
  // Backwards-compat alias so any leftover callers keep working.
  uploadDocument: (projectId, file) =>
    api.uploadDocuments(projectId, [file]),
  getDocument: (id) => http.get(`/documents/${id}`).then((r) => r.data),
  updateDocumentTitle: (id, title) =>
    http.patch(`/documents/${id}`, { title }).then((r) => r.data),
  deleteDocument: (id) => http.delete(`/documents/${id}`).then((r) => r.data),
  getSummary: (id) => http.get(`/documents/${id}/summary`).then((r) => r.data),
  getStatus: (id) => http.get(`/documents/${id}/status`).then((r) => r.data),
  resummarize: (id, model, personaOverride = null, language = null) => {
    const params = new URLSearchParams();
    if (model) params.set("model", model);
    if (language) params.set("language", language);
    const qs = params.toString();
    return http
      .post(`/documents/${id}/summarize${qs ? `?${qs}` : ""}`, personaOverride || {})
      .then((r) => r.data);
  },
  pdfUrl: (id) => `${API}/documents/${id}/pdf`,

  // ── Evidence ─────────────────────────────────────────────────
  evidenceForClaim: (claimId) =>
    http.post(`/claims/${claimId}/evidence`).then((r) => r.data),
  evidenceForSection: (docId, text) =>
    http.post(`/documents/${docId}/section-evidence`, { text }).then((r) => r.data),

  // ── Network Graph ────────────────────────────────────────────
  network: (projectId) =>
    http.get(`/projects/${projectId}/network`).then((r) => r.data),

  // ── Matrix ──────────────────────────────────────────────────
  matrix: (projectId, documentIds = null, refresh = false, method = "default", model = null, language = null) =>
    http
      .post(`/projects/${projectId}/matrix`, { document_ids: documentIds, refresh, method, model, language })
      .then((r) => r.data),

  // ── Ask ─────────────────────────────────────────────────────
  ask: (projectId, question, language = null, model = null, history = []) => {
    const params = new URLSearchParams();
    if (language) params.set("language", language);
    if (model) params.set("model", model);
    const qs = params.toString();
    return http
      .post(`/projects/${projectId}/ask${qs ? `?${qs}` : ""}`, { question, history })
      .then((r) => r.data);
  },

  // ── Check & Fix ────────────────────────────────────────────────
  runCheck: (projectId, payload) =>
    http.post(`/projects/${projectId}/check`, payload).then((r) => r.data),
  getLastCheck: (projectId) =>
    http.get(`/projects/${projectId}/check`).then((r) => r.data),
  getSentenceDetail: (documentId, sentenceId) =>
    http
      .get(`/documents/${documentId}/sentence/${sentenceId}`)
      .then((r) => r.data),
  testApiKey: (payload) =>
    http.post(`/settings/test-api-key`, payload).then((r) => r.data),
};
