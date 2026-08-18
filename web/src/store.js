import { create } from "zustand";

export const CATEGORY_COLORS = {
  Low: "#37d67a",
  Medium: "#f2b134",
  High: "#e4572e",
};
export const ACCENT = "#38bdf8";

export const VIEWS = [
  { key: "hero", label: "Overview" },
  { key: "portfolio", label: "Portfolio" },
  { key: "applicant", label: "Applicant" },
  { key: "compare", label: "Trad vs Behavioral" },
  { key: "fairness", label: "Fairness" },
  { key: "performance", label: "Performance" },
];

const AUTH_KEY = "cr_user";
const TOKEN_KEY = "cr_token";

/**
 * Session token issued by the backend. Every /api call carries it — the server
 * derives who you are and what you may do from this, never from the body.
 */
let authToken = localStorage.getItem(TOKEN_KEY) || null;

export function setToken(token) {
  authToken = token || null;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

/** fetch() with the bearer token attached; clears an expired session. */
export async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401 && authToken) {
    // Token expired or was revoked — drop it so the app returns to sign-in.
    setToken(null);
    localStorage.removeItem(AUTH_KEY);
    useStore.setState({ user: null });
  }
  return res;
}

/** FastAPI validation errors arrive as an array; flatten to one line. */
function detailText(detail) {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || "").join(", ");
  return "";
}

function readUser() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_KEY)) || null;
  } catch {
    return null;
  }
}

export const useStore = create((set, get) => ({
  data: null,
  loaded: false,
  view: "hero",
  threshold: 25,
  hoveredId: null,
  selectedId: null,

  // --- demo auth (no real backend / no credentials stored) ---
  user: readUser(),
  /** Persist an authenticated user locally. */
  _setUser(apiUser) {
    const u = {
      name: apiUser.name || apiUser.email,
      email: apiUser.email,
      role: apiUser.role === "manager" ? "Credit Manager" : "Credit Analyst",
      roleKey: apiUser.role || "analyst",   // drives permissions
    };
    localStorage.setItem(AUTH_KEY, JSON.stringify(u));
    set({ user: u });
    return u;
  },

  /** Create an account, then sign in. */
  async register({ email, password, name }) {
    const res = await api("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(detailText(err.detail) || "Could not create the account.");
    }
    const body = await res.json();
    setToken(body.token);
    return get()._setUser(body.user);
  },

  /** Sign in with email + password. */
  async signIn({ email, password }) {
    const res = await api("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(detailText(err.detail) || "Incorrect email or password.");
    }
    const body = await res.json();
    setToken(body.token);
    return get()._setUser(body.user);
  },
  logout() {
    setToken(null);
    localStorage.removeItem(AUTH_KEY);
    set({ user: null, view: "hero" });
  },

  source: null, // "api" | "static"
  demoApplicants: null, // pristine batch, for "reset to demo"
  batchLabel: "demo batch",

  async load() {
    // Shared across HeroCloud (landing) and the Dashboard — fetch at most once.
    // Exception: the landing page loads unauthenticated and falls back to the
    // static snapshot, so retry once a session token exists.
    if (get().loaded && !(get().source === "static" && get().user)) return;
    // Prefer the live FastAPI backend; fall back to the precomputed static file.
    try {
      const [aRes, mRes] = await Promise.all([
        api("/api/applicants?n=250"),
        api("/api/metrics"),
      ]);
      if (!aRes.ok || !mRes.ok) throw new Error("api unavailable");
      const a = await aRes.json();
      const metrics = await mRes.json();
      const data = {
        meta: { ...a.meta, default_threshold: 25, n_applicants: a.applicants.length },
        metrics,
        best: a.meta.best,
        features: a.meta.features,
        applicants: a.applicants,
      };
      set({
        data,
        loaded: true,
        source: "api",
        threshold: 25,
        selectedId: a.applicants[0]?.id ?? null,
        demoApplicants: a.applicants,
        batchLabel: "demo batch",
      });
      return;
    } catch {
      // backend offline — use the bundled snapshot
    }
    const res = await fetch("/data.json");
    const data = await res.json();
    set({
      data,
      loaded: true,
      source: "static",
      threshold: data.meta.default_threshold ?? 25,
      selectedId: data.applicants[0]?.id ?? null,
      demoApplicants: data.applicants,
      batchLabel: "demo batch",
    });
  },

  // --- officer decisions (system of record) ---------------------------- //
  actions: {},        // applicant_id -> latest recorded decision
  auditLog: [],       // recent decisions, newest first
  auditStats: null,

  async loadActions() {
    try {
      const res = await api("/api/actions");
      if (!res.ok) return;
      set({ actions: (await res.json()).actions || {} });
    } catch { /* offline: recorded statuses simply stay empty */ }
  },

  async loadAuditLog(limit = 100) {
    try {
      const res = await api(`/api/decisions?limit=${limit}`);
      if (!res.ok) return;
      const d = await res.json();
      set({ auditLog: d.decisions || [], auditStats: d.stats || null });
    } catch { /* offline */ }
  },

  /** Commit an officer decision, then refresh recorded statuses. */
  async recordDecision(applicant, decision, note) {
    const threshold = get().threshold;
    const res = await api("/api/decisions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        applicant_id: applicant.id,
        decision,
        note: note || "",
        threshold,
        // Features only — the server re-scores and derives the actor from the
        // session token. A client-supplied risk would be forgeable.
        applicant: {
          id: applicant.id,
          credit_score: applicant.credit_score,
          income: applicant.income,
          existing_debt: applicant.existing_debt,
          loan_amount: applicant.loan_amount,
          payment_consistency_pct: applicant.payment_consistency_pct,
          income_volatility_score: applicant.income_volatility_score,
          debt_trend: applicant.debt_trend,
        },
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Could not record decision (${res.status})`);
    }
    const out = await res.json();
    set((s) => ({ actions: { ...s.actions, [applicant.id]: out.recorded } }));
    return out;
  },

  /** Adverse-action notice for a declined decision (ECOA / Reg B). */
  async fetchNotice(decisionId) {
    const res = await api(`/api/notices/${decisionId}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Could not generate notice (${res.status})`);
    }
    return (await res.json()).notice;
  },

  // --- maker-checker: manager review queue ------------------------------ //
  pendingReviews: [],

  async loadReviews() {
    try {
      const res = await api("/api/reviews");
      if (!res.ok) return;
      set({ pendingReviews: (await res.json()).pending || [] });
    } catch { /* offline */ }
  },

  // --- team roster (managers only) --------------------------------------- //
  team: [],

  async loadTeam() {
    try {
      const res = await api("/api/users");
      if (!res.ok) return;                 // 403 for analysts — leave empty
      set({ team: (await res.json()).users || [] });
    } catch { /* offline */ }
  },

  /** Grant or withdraw override sign-off authority. */
  async setUserRole(email, role) {
    const res = await api("/api/users/role", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, role }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(detailText(err.detail) || `Could not update role (${res.status})`);
    }
    await get().loadTeam();
  },

  /** Manager approves or refuses an analyst's override. */
  async reviewDecision(decisionId, approve, note) {
    const res = await api(`/api/reviews/${decisionId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        approve,
        note: note || "",
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Review failed (${res.status})`);
    }
    await get().loadReviews();
    await get().loadActions();
    return res.json();
  },

  // Replace the working batch (re-renders the 3D field + every view).
  setApplicants(records, label) {
    const data = get().data;
    set({
      data: {
        ...data,
        applicants: records,
        meta: { ...data.meta, n_applicants: records.length },
      },
      selectedId: records[0]?.id ?? null,
      batchLabel: label ?? get().batchLabel,
    });
  },

  resetToDemo() {
    const demo = get().demoApplicants;
    if (demo) get().setApplicants(demo, "demo batch");
  },

  // Upload a CSV, score it through the live backend, and load the results.
  async uploadCsv(file) {
    const fd = new FormData();
    fd.append("file", file);
    const res = await api("/api/score-csv", { method: "POST", body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Upload failed (${res.status})`);
    }
    const out = await res.json();
    get().setApplicants(out.applicants, out.filename || "uploaded batch");
    return out.applicants.length;
  },

  setView: (view) => set({ view }),
  setThreshold: (threshold) => set({ threshold }),
  setHovered: (hoveredId) => set({ hoveredId }),
  select: (selectedId) => set({ selectedId }),

  applicantById: (id) => get().data?.applicants.find((a) => a.id === id) ?? null,
}));
