import React, { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useStore, CATEGORY_COLORS, ACCENT } from "./store.js";
import Login from "./Login.jsx";
import "./crm.css";

/* ------------------------------- helpers -------------------------------- */
function riskColor(risk) {
  if (risk < 15) return CATEGORY_COLORS.Low;
  if (risk < 40) return CATEGORY_COLORS.Medium;
  return CATEGORY_COLORS.High;
}

/* Turn a model feature into a sentence a loan officer can read. */
const REASONS = {
  "Payment consistency %": ["Pays bills on time", "Has missed payments"],
  "Income volatility": ["Income is steady", "Income is unpredictable"],
  "Debt trend": ["Paying debt down", "Debt is growing"],
  "Credit score": ["Strong credit score", "Weak credit score"],
  "Annual income": ["Income supports the loan", "Income is low for this loan"],
  "Existing debt": ["Low existing debt", "Already carrying high debt"],
  "Loan amount": ["Loan size is manageable", "Loan is large for this profile"],
};

function plainReason(label, good) {
  const pair = REASONS[label];
  if (!pair) return `${label} ${good ? "is favourable" : "is a concern"}`;
  return good ? pair[0] : pair[1];
}

const SECTIONS = [
  { key: "overview", label: "Overview", icon: "⌂" },
  { key: "applicants", label: "Applicants", icon: "☰" },
  { key: "customers", label: "Customers", icon: "☺" },
  { key: "pipeline", label: "Pipeline", icon: "▤" },
  { key: "reports", label: "Reports", icon: "▥" },
  { key: "distribution", label: "Risk distribution", icon: "▦" },
  { key: "approvals", label: "Approvals", icon: "⚖" },
  { key: "audit", label: "Audit log", icon: "⎘" },
  { key: "team", label: "Team", icon: "☗" },
];

/* --------------------------------- shell --------------------------------- */
function Sidebar({ section, setSection }) {
  const user = useStore((s) => s.user);
  const logout = useStore((s) => s.logout);
  const pendingCount = useStore((s) => s.pendingReviews.length);
  const initials = user ? user.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase() : "";
  return (
    <nav className="nav crm-side">
      <Link to="/" className="brand" style={{ textDecoration: "none" }}>
        <span className="brand-mark" aria-hidden="true">◆</span>
        <div>
          <div className="brand-title">Credit Risk</div>
          <div className="brand-sub">Decision Engine</div>
        </div>
      </Link>
      <ul role="tablist" aria-label="Dashboard sections" className="crm-nav">
        {SECTIONS.map((s) => (
          <li
            key={s.key}
            role="tab"
            tabIndex={0}
            aria-selected={section === s.key}
            className={section === s.key ? "active" : ""}
            onClick={() => setSection(s.key)}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSection(s.key); } }}
          >
            <span className="crm-nav-ico" aria-hidden="true">{s.icon}</span>
            {s.label}
            {s.key === "approvals" && pendingCount > 0 && (
              <span className="nav-badge" aria-label={`${pendingCount} awaiting approval`}>
                {pendingCount}
              </span>
            )}
          </li>
        ))}
      </ul>
      <div className="user-menu">
        <div className="avatar">{initials}</div>
        <div className="user-info">
          <div className="user-name">{user?.name}</div>
          <div className="user-role">{user?.role}</div>
        </div>
        <button className="logout" onClick={logout} title="Log out" aria-label="Log out">
          <span aria-hidden="true">⏻</span>
        </button>
      </div>
      <Link to="/" className="nav-back">← Back to site</Link>
    </nav>
  );
}

function SourceBadge() {
  const source = useStore((s) => s.source);
  if (!source) return null;
  const live = source === "api";
  return (
    <div className={`source-badge ${live ? "live" : "static"}`}>
      <span className="dot" />
      {live ? "Live API" : "Static snapshot"}
    </div>
  );
}

/* -------------------------------- toolbar -------------------------------- */
function Toolbar({ title, hint, search, setSearch, showThreshold }) {
  const threshold = useStore((s) => s.threshold);
  const setThreshold = useStore((s) => s.setThreshold);
  const batchLabel = useStore((s) => s.batchLabel);
  const applicants = useStore((s) => s.data.applicants);
  const source = useStore((s) => s.source);
  const uploadCsv = useStore((s) => s.uploadCsv);
  const resetToDemo = useStore((s) => s.resetToDemo);
  const features = useStore((s) => s.data.features);
  const fileRef = useRef();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true); setError(null);
    try { await uploadCsv(file); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const downloadTemplate = () => {
    const keys = features.map((f) => f.key);
    const cols = ["id", ...keys];
    const rows = applicants.slice(0, 3).map((a, i) => [a.id ?? `APP-${i + 1}`, ...keys.map((k) => a[k])].join(","));
    const csv = [cols.join(","), ...rows].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const link = document.createElement("a");
    link.href = url; link.download = "applicant_template.csv"; link.click();
    URL.revokeObjectURL(url);
  };

  const custom = batchLabel !== "demo batch";
  return (
    <header className="crm-topbar">
      <div className="crm-topbar-title">
        <h1>{title}</h1>
        {hint && <p>{hint}</p>}
      </div>
      <div className="crm-topbar-actions">
        {setSearch && (
          <input
            className="crm-search"
            type="search"
            placeholder="Search applicant ID…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search applicants"
          />
        )}
        {showThreshold && (
          <label className="crm-threshold">
            Auto-approve below
            <input
              type="range" min="1" max="90" value={threshold}
              aria-label="Approval risk threshold percent"
              onChange={(e) => setThreshold(+e.target.value)}
            />
            <b>{threshold}%</b>
          </label>
        )}
        <button className="mini" onClick={downloadTemplate}>Template</button>
        <button className="mini primary" onClick={() => fileRef.current?.click()} disabled={busy || source !== "api"}
          title={source !== "api" ? "Backend offline — upload needs the live API" : ""}>
          {busy ? "Scoring…" : "Upload CSV"}
        </button>
        {custom && <button className="mini" onClick={resetToDemo}>Reset</button>}
        <input ref={fileRef} type="file" accept=".csv" onChange={onFile} style={{ display: "none" }} />
        <SourceBadge />
      </div>
      {error && <div className="batch-error crm-toolbar-error">{error}</div>}
    </header>
  );
}

/* -------------------------------- overview --------------------------------- */
function OverviewView({ goTo, onOpen }) {
  const applicants = useStore((s) => s.data.applicants);
  const threshold = useStore((s) => s.threshold);
  const best = useStore((s) => s.data.best);
  const batchLabel = useStore((s) => s.batchLabel);

  const stats = useMemo(() => {
    const approved = applicants.filter((a) => a.risk < threshold);
    const flips = applicants.filter((a) => a.risk_traditional >= threshold && a.risk < threshold).length;
    return {
      n: applicants.length,
      approvalRate: applicants.length ? approved.length / applicants.length : 0,
      avgRisk: applicants.length ? applicants.reduce((s, a) => s + a.risk, 0) / applicants.length : 0,
      flips,
    };
  }, [applicants, threshold]);

  const needsReview = useMemo(
    () => [...applicants].filter((a) => a.category === "Medium").sort((a, b) => b.risk - a.risk).slice(0, 5),
    [applicants]
  );
  const delta = (best.alternative.auc_pr - best.traditional.auc_pr).toFixed(2);

  return (
    <>
      <Toolbar title="Overview" hint={`${batchLabel} · ${stats.n} applicants`} />
      <div className="crm-overview">
        <div className="kpis crm-overview-kpis">
          <div className="kpi"><div className="kpi-label">Applicants</div><div className="kpi-value">{stats.n}</div></div>
          <div className="kpi"><div className="kpi-label">Approval rate</div><div className="kpi-value">{(stats.approvalRate * 100).toFixed(0)}%</div></div>
          <div className="kpi"><div className="kpi-label">Avg risk</div><div className="kpi-value">{stats.avgRisk.toFixed(1)}%</div></div>
          <div className="kpi"><div className="kpi-label">Rescued by behavioral data</div><div className="kpi-value" style={{ color: ACCENT }}>+{stats.flips}</div></div>
        </div>

        <div className="crm-overview-row">
          <div className="panel crm-review-card">
            <div className="panel-head"><h2>Needs review</h2><span className="hint">Medium-risk, highest first</span></div>
            <div className="crm-review-list">
              {needsReview.map((a) => (
                <button className="crm-review-item" key={a.id} onClick={() => onOpen(a.id)}>
                  <span className="crm-risk-dot" style={{ background: riskColor(a.risk) }} aria-hidden="true" />
                  <span className="mono">{a.id}</span>
                  <span>{a.risk.toFixed(1)}%</span>
                </button>
              ))}
            </div>
            <button className="mini" onClick={() => goTo("pipeline")}>Open pipeline →</button>
          </div>

          <div className="panel crm-review-card">
            <div className="panel-head"><h2>Model quality</h2></div>
            <p className="finding">Behavioral data lifts AUC-PR by <b>+{delta}</b> over traditional-only scoring.</p>
            <button className="mini" onClick={() => goTo("reports")}>View reports →</button>
          </div>
        </div>
      </div>
    </>
  );
}

/* ------------------------------ applicants -------------------------------- */
function StatusPill({ risk, threshold, recorded }) {
  if (recorded) {
    return (
      <span className={`crm-pill ${recorded.decision === "approve" ? "ok" : "no"}`}>
        {recorded.decision === "approve" ? "Approved" : "Declined"}
        <span className="pill-check" aria-label="decision recorded"> ✓</span>
      </span>
    );
  }
  const approve = risk < threshold;
  return <span className={`crm-pill pending ${approve ? "ok" : "no"}`}>{approve ? "Approve" : "Decline"}</span>;
}

function exportCsv(rows, filename) {
  const cols = ["id", "credit_score", "income", "risk", "risk_traditional", "category"];
  const csv = [cols.join(","), ...rows.map((a) => cols.map((c) => a[c]).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.click();
  URL.revokeObjectURL(url);
}

function ApplicantsView({ onOpen }) {
  const applicants = useStore((s) => s.data.applicants);
  const threshold = useStore((s) => s.threshold);
  const actions = useStore((s) => s.actions);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState("risk");
  const [sortDir, setSortDir] = useState("desc");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [selected, setSelected] = useState(() => new Set());

  const rows = useMemo(() => {
    let r = applicants;

    // Free-text search across id, credit score and income.
    const q = search.trim().toLowerCase();
    if (q) {
      r = r.filter((a) =>
        a.id.toLowerCase().includes(q) ||
        String(a.credit_score).includes(q) ||
        String(Math.round(a.income)).includes(q)
      );
    }

    // Work-queue filters.
    if (statusFilter === "pending") r = r.filter((a) => !actions[a.id]);
    else if (statusFilter === "approved") r = r.filter((a) => actions[a.id]?.decision === "approve");
    else if (statusFilter === "declined") r = r.filter((a) => actions[a.id]?.decision === "decline");
    else if (statusFilter === "flips") {
      r = r.filter((a) => a.risk_traditional >= threshold && a.risk < threshold);
    }

    const dir = sortDir === "asc" ? 1 : -1;
    return [...r].sort((a, b) => {
      const x = a[sortKey], y = b[sortKey];
      if (typeof x === "number" && typeof y === "number") return (x - y) * dir;
      return String(x).localeCompare(String(y)) * dir;
    });
  }, [applicants, search, sortKey, sortDir, statusFilter, actions, threshold]);

  const stats = useMemo(() => {
    const approved = applicants.filter((a) => a.risk < threshold);
    return {
      n: applicants.length,
      approvalRate: applicants.length ? approved.length / applicants.length : 0,
      avgRisk: applicants.length ? applicants.reduce((s, a) => s + a.risk, 0) / applicants.length : 0,
    };
  }, [applicants, threshold]);

  const toggle = (id, e) => {
    e.stopPropagation();
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  // Page the filtered rows so large batches stay responsive.
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageRows = rows.slice((safePage - 1) * pageSize, safePage * pageSize);

  const allSelected = pageRows.length > 0 && pageRows.every((r) => selected.has(r.id));
  const toggleAll = () =>
    setSelected(allSelected ? new Set() : new Set(pageRows.map((r) => r.id)));

  const sortBy = (key) => {
    if (key === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir(key === "id" ? "asc" : "desc"); }
    setPage(1);
  };
  const arrow = (key) => (sortKey === key ? (sortDir === "asc" ? " ↑" : " ↓") : "");

  const FILTERS = [
    ["all", "All"],
    ["pending", "Awaiting decision"],
    ["approved", "Approved"],
    ["declined", "Declined"],
    ["flips", "Rescued by behaviour"],
  ];

  return (
    <>
      <Toolbar title="Applicants" hint={`${stats.n} records · ${(stats.approvalRate * 100).toFixed(0)}% approval rate · ${stats.avgRisk.toFixed(1)}% avg risk`}
        search={search} setSearch={(v) => { setSearch(v); setPage(1); }} showThreshold />

      <div className="queue-filters">
        {FILTERS.map(([k, label]) => (
          <button key={k} className={`mini ${statusFilter === k ? "primary" : ""}`}
            onClick={() => { setStatusFilter(k); setPage(1); }}>
            {label}
          </button>
        ))}
        <span className="queue-count">
          {rows.length === stats.n ? `${rows.length} applicants` : `${rows.length} of ${stats.n}`}
        </span>
      </div>

      {selected.size > 0 && (
        <div className="crm-bulkbar">
          <span>{selected.size} selected</span>
          <button className="mini primary" onClick={() => exportCsv(rows.filter((r) => selected.has(r.id)), "selected_applicants.csv")}>
            Export selected
          </button>
          <button className="mini" onClick={() => setSelected(new Set())}>Clear</button>
        </div>
      )}

      <div className="crm-table-wrap">
        <table className="crm-table">
          <thead>
            <tr>
              <th className="crm-th-check"><input type="checkbox" checked={allSelected} onChange={toggleAll} aria-label="Select all on this page" /></th>
              <th onClick={() => sortBy("id")}>ID{arrow("id")}</th>
              <th onClick={() => sortBy("credit_score")}>Credit score{arrow("credit_score")}</th>
              <th onClick={() => sortBy("income")}>Income{arrow("income")}</th>
              <th onClick={() => sortBy("risk")}>Risk{arrow("risk")}</th>
              <th>Status</th>
              <th aria-hidden="true"></th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((a) => (
              <tr key={a.id} tabIndex={0} onClick={() => onOpen(a.id)}
                onKeyDown={(e) => { if (e.key === "Enter") onOpen(a.id); }}>
                <td className="crm-th-check" onClick={(e) => e.stopPropagation()}>
                  <input type="checkbox" checked={selected.has(a.id)} onChange={(e) => toggle(a.id, e)} aria-label={`Select ${a.id}`} />
                </td>
                <td className="mono">{a.id}</td>
                <td>{a.credit_score}</td>
                <td>${Math.round(a.income).toLocaleString()}</td>
                <td>
                  <span className="crm-risk-dot" style={{ background: riskColor(a.risk) }} aria-hidden="true" />
                  {a.risk.toFixed(1)}%
                </td>
                <td><StatusPill risk={a.risk} threshold={threshold} recorded={actions[a.id]} /></td>
                <td className="crm-chevron" aria-hidden="true">›</td>
              </tr>
            ))}
            {pageRows.length === 0 && (
              <tr><td colSpan={7}>
                <div className="empty-state">
                  <div className="empty-ico" aria-hidden="true">◎</div>
                  <p>{search ? `No applicants match “${search}”.` : "Nothing in this view."}</p>
                </div>
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {rows.length > 0 && (
        <div className="pager">
          <span className="pager-info">
            {(safePage - 1) * pageSize + 1}–{Math.min(safePage * pageSize, rows.length)} of {rows.length}
          </span>
          <div className="pager-controls">
            <label className="pager-size">
              Rows
              <select value={pageSize} aria-label="Rows per page"
                onChange={(e) => { setPageSize(+e.target.value); setPage(1); }}>
                {[25, 50, 100, 250].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
            <button className="mini" disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>← Prev</button>
            <span className="pager-page">Page {safePage} / {totalPages}</span>
            <button className="mini" disabled={safePage >= totalPages} onClick={() => setPage(safePage + 1)}>Next →</button>
          </div>
        </div>
      )}
    </>
  );
}

/* -------------------------------- pipeline -------------------------------- */
function PipelineView({ onOpen }) {
  const applicants = useStore((s) => s.data.applicants);
  const columns = [
    { key: "Low", title: "Auto-approve", sub: "Low risk" },
    { key: "Medium", title: "Needs review", sub: "Medium risk" },
    { key: "High", title: "Decline", sub: "High risk" },
  ];
  return (
    <>
      <Toolbar title="Pipeline" hint="Applicants grouped by risk band." />
      <div className="crm-board">
        {columns.map((c) => {
          const items = applicants.filter((a) => a.category === c.key);
          return (
            <div className="crm-col" key={c.key}>
              <div className="crm-col-head">
                <span className="crm-col-dot" style={{ background: CATEGORY_COLORS[c.key] }} aria-hidden="true" />
                <div><h3>{c.title}</h3><span>{c.sub} · {items.length}</span></div>
              </div>
              <div className="crm-col-body">
                {items.slice(0, 60).map((a) => (
                  <button className="crm-card" key={a.id} onClick={() => onOpen(a.id)}>
                    <span className="mono">{a.id}</span>
                    <span className="crm-card-risk" style={{ color: riskColor(a.risk) }}>{a.risk.toFixed(1)}%</span>
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

/* -------------------------------- reports --------------------------------- */
function ReportsView() {
  const applicants = useStore((s) => s.data.applicants);
  const threshold = useStore((s) => s.threshold);
  const metrics = useStore((s) => s.data.metrics);
  const best = useStore((s) => s.data.best);

  const brackets = useMemo(() => {
    const sorted = [...applicants].sort((a, b) => a.income - b.income);
    const third = Math.floor(sorted.length / 3) || 1;
    const groups = [
      { label: "Low income", rows: sorted.slice(0, third) },
      { label: "Medium income", rows: sorted.slice(third, 2 * third) },
      { label: "High income", rows: sorted.slice(2 * third) },
    ];
    return groups.map((g) => ({
      label: g.label,
      rate: g.rows.length ? (g.rows.filter((r) => r.risk < threshold).length / g.rows.length) * 100 : 0,
    }));
  }, [applicants, threshold]);

  const gap = Math.max(...brackets.map((b) => b.rate)) - Math.min(...brackets.map((b) => b.rate));
  const maxAuc = Math.max(...metrics.map((m) => m.auc_pr));
  const delta = (best.alternative.auc_pr - best.traditional.auc_pr).toFixed(2);

  return (
    <>
      <Toolbar title="Reports" hint="Portfolio fairness and model performance." />
      <div className="crm-reports">
        <div className="panel crm-report-card">
          <div className="panel-head"><h2>Approval access by income</h2></div>
          <div className="bars">
            {brackets.map((b) => (
              <div className="bar-col" key={b.label}>
                <div className="bar-track">
                  <div className="bar-fill" style={{ height: `${b.rate}%`, background: ACCENT }}><span>{b.rate.toFixed(0)}%</span></div>
                </div>
                <div className="bar-label">{b.label}</div>
              </div>
            ))}
          </div>
          <p className="finding">{gap < 10 ? `Within ${gap.toFixed(0)} pts — no large access gap.` : `${gap.toFixed(0)}-pt gap between highest and lowest bracket.`}</p>
        </div>

        <div className="panel crm-report-card">
          <div className="panel-head"><h2>Model performance</h2></div>
          <table className="perf-table">
            <thead><tr><th>Feature set</th><th>Model</th><th>Precision</th><th>Recall</th><th>F1</th><th>AUC-PR</th></tr></thead>
            <tbody>
              {metrics.map((m, i) => (
                <tr key={i}>
                  <td>{m.feature_set === "alternative" ? "Trad + Behavioral" : "Traditional"}</td>
                  <td>{m.model}</td><td>{m.precision.toFixed(3)}</td><td>{m.recall.toFixed(3)}</td><td>{m.f1.toFixed(3)}</td>
                  <td><span className="auc-cell" style={{ background: `rgba(56,189,248,${(m.auc_pr / maxAuc) * 0.7})` }}>{m.auc_pr.toFixed(3)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="finding">Behavioral data lifts best-model AUC-PR by <b>+{delta}</b>.</p>
          <div className="disclaimer">⚠ Prototype on synthetic data — not for production lending decisions.</div>
        </div>
      </div>
    </>
  );
}

/* ---------------------------- risk distribution ----------------------------- */
function DistributionView({ onOpen }) {
  const applicants = useStore((s) => s.data.applicants);
  const threshold = useStore((s) => s.threshold);
  const [bucket, setBucket] = useState(null);

  const buckets = useMemo(() => {
    const out = Array.from({ length: 10 }, (_, i) => ({
      from: i * 10, to: i * 10 + 10, rows: [],
    }));
    applicants.forEach((a) => {
      const i = Math.min(Math.floor(a.risk / 10), 9);
      out[i].rows.push(a);
    });
    return out;
  }, [applicants]);

  const maxCount = Math.max(...buckets.map((b) => b.rows.length), 1);
  const selected = bucket != null ? buckets[bucket] : null;

  return (
    <>
      <Toolbar title="Risk distribution" hint="How many applicants fall into each risk band." showThreshold />
      <div className="crm-dist">
        <div className="panel crm-dist-card">
          <div className="panel-head">
            <h2>Applicants by risk band</h2>
            <span className="hint">Bars left of the line are auto-approved</span>
          </div>

          <div className="dist-chart">
            {buckets.map((b, i) => {
              const pct = (b.rows.length / maxCount) * 100;
              const approved = b.to <= threshold;
              const color = b.from < 15 ? CATEGORY_COLORS.Low : b.from < 40 ? CATEGORY_COLORS.Medium : CATEGORY_COLORS.High;
              return (
                <button
                  key={i}
                  className={`dist-bar-col ${bucket === i ? "sel" : ""}`}
                  onClick={() => setBucket(bucket === i ? null : i)}
                  aria-label={`${b.from} to ${b.to} percent risk, ${b.rows.length} applicants`}
                >
                  <span className="dist-count">{b.rows.length}</span>
                  <span className="dist-bar" style={{ height: `${pct}%`, background: color, opacity: approved ? 1 : 0.45 }} />
                  <span className="dist-x">{b.from}</span>
                </button>
              );
            })}
          </div>
          <div className="dist-axis-label">Default risk (%)</div>

          <div className="dist-legend">
            <span><i style={{ background: CATEGORY_COLORS.Low }} aria-hidden="true" /> Low (&lt;15%)</span>
            <span><i style={{ background: CATEGORY_COLORS.Medium }} aria-hidden="true" /> Medium (15–40%)</span>
            <span><i style={{ background: CATEGORY_COLORS.High }} aria-hidden="true" /> High (40%+)</span>
            <span className="dist-dim">Faded = above your {threshold}% approval threshold</span>
          </div>
        </div>

        <div className="panel crm-dist-card">
          <div className="panel-head">
            <h2>{selected ? `${selected.from}–${selected.to}% risk` : "Select a band"}</h2>
            {selected && <button className="mini" onClick={() => setBucket(null)}>Clear</button>}
          </div>
          {selected ? (
            <div className="crm-review-list">
              {selected.rows.slice(0, 12).map((a) => (
                <button className="crm-review-item" key={a.id} onClick={() => onOpen(a.id)}>
                  <span className="crm-risk-dot" style={{ background: riskColor(a.risk) }} aria-hidden="true" />
                  <span className="mono">{a.id}</span>
                  <span>{a.risk.toFixed(1)}%</span>
                </button>
              ))}
              {selected.rows.length > 12 && (
                <p className="finding">+{selected.rows.length - 12} more in this band</p>
              )}
              {selected.rows.length === 0 && <div className="empty-state"><p>No applicants in this band.</p></div>}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-ico" aria-hidden="true">▤</div>
              <p>Click any bar to list the applicants in that risk band.</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

/* ------------------------------- customers ---------------------------------- */
function money(n) { return `$${Math.round(n).toLocaleString()}`; }

function CustomersView({ onOpen }) {
  const applicants = useStore((s) => s.data.applicants);
  const actions = useStore((s) => s.actions);
  const threshold = useStore((s) => s.threshold);
  const [selectedId, setSelectedId] = useState(null);
  const [q, setQ] = useState("");

  const list = useMemo(() => {
    const t = q.trim().toLowerCase();
    const r = t ? applicants.filter((a) => a.id.toLowerCase().includes(t)) : applicants;
    return r.slice(0, 100);
  }, [applicants, q]);

  const c = useMemo(
    () => applicants.find((a) => a.id === (selectedId ?? list[0]?.id)),
    [applicants, selectedId, list]
  );

  if (!c) {
    return (
      <>
        <Toolbar title="Customers" hint="Full profile for each applicant." />
        <div className="crm-overview">
          <div className="panel"><div className="empty-state"><p>No customers loaded.</p></div></div>
        </div>
      </>
    );
  }

  const recorded = actions[c.id];
  const dti = c.income ? (c.existing_debt / c.income) * 100 : 0;
  const loanToIncome = c.income ? (c.loan_amount / c.income) * 100 : 0;

  return (
    <>
      <Toolbar title="Customers" hint="Full profile, affordability and decision history." />
      <div className="customers-layout">
        {/* Left: customer list */}
        <div className="panel customers-list">
          <input className="crm-search" placeholder="Find customer…" aria-label="Find customer"
            value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="cust-scroll">
            {list.map((a) => (
              <button key={a.id}
                className={`cust-item ${a.id === c.id ? "active" : ""}`}
                onClick={() => setSelectedId(a.id)}>
                <span className="crm-risk-dot" style={{ background: riskColor(a.risk) }} aria-hidden="true" />
                <span className="mono">{a.id}</span>
                <span className="cust-item-risk">{a.risk.toFixed(0)}%</span>
              </button>
            ))}
          </div>
        </div>

        {/* Right: full profile */}
        <div className="cust-detail">
          <div className="panel">
            <div className="cust-head">
              <div className="cust-avatar" aria-hidden="true">{c.id.slice(-2)}</div>
              <div>
                <h2 className="cust-name">Customer {c.id}</h2>
                <div className="cust-sub">
                  {recorded
                    ? `${recorded.decision === "approve" ? "Approved" : "Declined"} by ${recorded.actor}`
                    : "No decision recorded yet"}
                </div>
              </div>
              <span className={`crm-pill ${c.risk < threshold ? "ok" : "no"}`}>
                {c.risk.toFixed(1)}% risk
              </span>
            </div>

            <div className="cust-grid">
              <div><span>Credit score</span><b>{c.credit_score}</b></div>
              <div><span>Annual income</span><b>{money(c.income)}</b></div>
              <div><span>Existing debt</span><b>{money(c.existing_debt)}</b></div>
              <div><span>Loan requested</span><b>{money(c.loan_amount)}</b></div>
              <div><span>Debt-to-income</span><b>{dti.toFixed(0)}%</b></div>
              <div><span>Loan-to-income</span><b>{loanToIncome.toFixed(0)}%</b></div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head"><h2>Payment behaviour</h2></div>
            <div className="behaviour-bars">
              {[
                ["Pays on time", c.payment_consistency_pct, "%", true],
                ["Income stability", 100 - c.income_volatility_score, "%", true],
                ["Debt direction", c.debt_trend, "", false],
              ].map(([label, val, unit, isPct]) => (
                <div className="bhv-row" key={label}>
                  <span className="bhv-label">{label}</span>
                  {isPct ? (
                    <>
                      <div className="bhv-track">
                        <div className="bhv-fill" style={{
                          width: `${Math.max(0, Math.min(100, val))}%`,
                          background: val >= 70 ? CATEGORY_COLORS.Low
                            : val >= 40 ? CATEGORY_COLORS.Medium : CATEGORY_COLORS.High,
                        }} />
                      </div>
                      <span className="bhv-val">{Math.round(val)}{unit}</span>
                    </>
                  ) : (
                    <span className={`bhv-trend ${val > 0 ? "bad" : "good"}`}>
                      {val > 0 ? "↑ Debt increasing" : "↓ Debt reducing"}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h2>Decision</h2>
              <button className="mini primary" onClick={() => onOpen(c.id)}>Open decision sheet →</button>
            </div>
            {recorded ? (
              <div className="cust-decision">
                <span className={`crm-pill ${recorded.decision === "approve" ? "ok" : "no"}`}>
                  {recorded.decision === "approve" ? "Approved" : "Declined"}
                </span>
                <span className="cust-decision-meta">
                  by {recorded.actor}
                  {recorded.status === "pending_review" && " · awaiting manager approval"}
                  {recorded.reviewed_by && ` · signed off by ${recorded.reviewed_by}`}
                </span>
                {recorded.note && <p className="recorded-note">“{recorded.note}”</p>}
              </div>
            ) : (
              <p className="finding">
                Model recommends <b>{c.risk < threshold ? "approve" : "decline"}</b> at {c.risk.toFixed(1)}% risk.
                No decision recorded yet.
              </p>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

/* ------------------------------- approvals ---------------------------------- */
function ApprovalsView() {
  const pending = useStore((s) => s.pendingReviews);
  const loadReviews = useStore((s) => s.loadReviews);
  const reviewDecision = useStore((s) => s.reviewDecision);
  const user = useStore((s) => s.user);
  const isManager = user?.roleKey === "manager";
  const [busy, setBusy] = useState(null);
  const [notes, setNotes] = useState({});
  const [error, setError] = useState(null);

  React.useEffect(() => { loadReviews(); }, [loadReviews]);

  const act = async (id, approve) => {
    setBusy(id); setError(null);
    try { await reviewDecision(id, approve, notes[id]); }
    catch (e) { setError(e.message); }
    finally { setBusy(null); }
  };

  return (
    <>
      <Toolbar title="Approvals"
        hint="Overrides where an analyst disagreed with the model — these need manager sign-off." />
      <div className="crm-overview">
        {!isManager && (
          <div className="role-notice">
            You're signed in as an analyst. Only a manager can sign off overrides —
            sign in as Manager to action these.
          </div>
        )}
        {error && <div className="batch-error">{error}</div>}

        {pending.length === 0 ? (
          <div className="panel">
            <div className="empty-state">
              <div className="empty-ico" aria-hidden="true">✓</div>
              <p>Nothing awaiting approval. Overrides appear here for sign-off.</p>
            </div>
          </div>
        ) : (
          <div className="approvals-list">
            {pending.map((d) => (
              <div className="panel approval-card" key={d.id}>
                <div className="approval-head">
                  <div>
                    <span className="mono">{d.applicant_id}</span>
                    <span className="approval-meta">
                      {d.actor} wants to <b>{d.decision}</b> · model said{" "}
                      <b>{d.risk < d.threshold ? "approve" : "decline"}</b> at {d.risk.toFixed(1)}% risk
                    </span>
                  </div>
                  <span className="audit-flag">override</span>
                </div>

                {d.note && <p className="recorded-note">“{d.note}”</p>}

                <input
                  className="crm-search approval-note"
                  placeholder="Sign-off note (optional)"
                  aria-label={`Review note for ${d.applicant_id}`}
                  value={notes[d.id] || ""}
                  onChange={(e) => setNotes((n) => ({ ...n, [d.id]: e.target.value }))}
                />

                <div className="decide-actions">
                  <button className="btn-decide approve" disabled={!isManager || busy === d.id}
                    onClick={() => act(d.id, true)}>
                    {busy === d.id ? "Saving…" : "✓ Approve override"}
                  </button>
                  <button className="btn-decide decline" disabled={!isManager || busy === d.id}
                    onClick={() => act(d.id, false)}>
                    ✕ Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

/* -------------------------------- audit log --------------------------------- */
function TeamView() {
  const team = useStore((s) => s.team);
  const loadTeam = useStore((s) => s.loadTeam);
  const setUserRole = useStore((s) => s.setUserRole);
  const user = useStore((s) => s.user);
  const isManager = user?.roleKey === "manager";
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);

  React.useEffect(() => { loadTeam(); }, [loadTeam]);

  const change = async (email, role) => {
    setBusy(email); setError(null);
    try { await setUserRole(email, role); }
    catch (e) { setError(e.message); }
    finally { setBusy(null); }
  };

  return (
    <>
      <Toolbar title="Team"
        hint="Who can sign off overrides. Everyone signs up as an analyst — manager access is granted here." />
      <div className="crm-overview">
        {!isManager && (
          <div className="role-notice">
            Only a manager can view and change team access.
          </div>
        )}
        {error && <div className="batch-error">{error}</div>}
        {isManager && (
          <div className="crm-table-wrap" style={{ margin: 0 }}>
          <table className="crm-table">
            <thead>
              <tr><th>Name</th><th>Email</th><th>Access</th><th /></tr>
            </thead>
            <tbody>
              {team.map((m) => (
                <tr key={m.email}>
                  <td>{m.name || "—"}</td>
                  <td>{m.email}</td>
                  <td>{m.role === "manager" ? "Manager — signs off overrides"
                                            : "Analyst — decides within policy"}</td>
                  <td>
                    {m.email !== user?.email && (
                      <button className="btn-ghost" disabled={busy === m.email}
                        onClick={() => change(m.email,
                          m.role === "manager" ? "analyst" : "manager")}>
                        {m.role === "manager" ? "Remove manager access" : "Make manager"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </>
  );
}

function AuditView() {
  const auditLog = useStore((s) => s.auditLog);
  const stats = useStore((s) => s.auditStats);
  const loadAuditLog = useStore((s) => s.loadAuditLog);
  const [filter, setFilter] = useState("officer");

  React.useEffect(() => { loadAuditLog(200); }, [loadAuditLog]);

  const rows = useMemo(
    () => (filter === "all" ? auditLog : auditLog.filter((d) => d.source === filter)),
    [auditLog, filter]
  );

  return (
    <>
      <Toolbar title="Audit log" hint="Every decision recorded, newest first — reproducible for compliance." />
      <div className="crm-overview">
        {stats && (
          <div className="kpis crm-overview-kpis">
            <div className="kpi"><div className="kpi-label">Decisions recorded</div><div className="kpi-value">{stats.total}</div></div>
            <div className="kpi"><div className="kpi-label">Approved</div><div className="kpi-value" style={{ color: CATEGORY_COLORS.Low }}>{stats.approved}</div></div>
            <div className="kpi"><div className="kpi-label">Declined</div><div className="kpi-value" style={{ color: CATEGORY_COLORS.High }}>{stats.declined}</div></div>
            <div className="kpi"><div className="kpi-label">Behavioral flips</div><div className="kpi-value" style={{ color: ACCENT }}>{stats.flips}</div></div>
          </div>
        )}

        <div className="audit-filters">
          {[["officer", "Officer decisions"], ["api", "Automated scoring"], ["csv", "CSV batches"], ["all", "Everything"]].map(([k, label]) => (
            <button key={k} className={`mini ${filter === k ? "primary" : ""}`} onClick={() => setFilter(k)}>{label}</button>
          ))}
          <button className="mini" onClick={() => loadAuditLog(200)}>Refresh</button>
        </div>

        <div className="crm-table-wrap" style={{ margin: 0 }}>
          <table className="crm-table">
            <thead>
              <tr><th>When</th><th>Applicant</th><th>Decision</th><th>Risk</th><th>By</th><th>Note</th></tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.id}>
                  <td className="mono">{new Date(d.created_at).toLocaleString()}</td>
                  <td className="mono">{d.applicant_id}</td>
                  <td>
                    <span className={`crm-pill ${d.decision === "approve" ? "ok" : "no"}`}>
                      {d.decision === "approve" ? "Approved" : "Declined"}
                    </span>
                    {d.flipped ? <span className="audit-flag">override</span> : null}
                  </td>
                  <td>{d.risk.toFixed(1)}%</td>
                  <td>{d.actor}</td>
                  <td className="audit-note">{d.note || "—"}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={6}>
                  <div className="empty-state">
                    <div className="empty-ico" aria-hidden="true">⎘</div>
                    <p>No {filter === "all" ? "" : filter} decisions recorded yet. Approve or decline an applicant to create the first entry.</p>
                  </div>
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

/* --------------------------- adverse-action notice --------------------------- */
function NoticeModal({ notice, onClose }) {
  return (
    <div className="crm-drawer-overlay" onClick={onClose}>
      <div className="notice-sheet" onClick={(e) => e.stopPropagation()}
        role="dialog" aria-label="Adverse action notice">
        <div className="notice-toolbar">
          <button className="mini primary" onClick={() => window.print()}>Print / Save PDF</button>
          <button className="mini" onClick={onClose}>Close</button>
        </div>

        <div className="notice-doc" id="notice-print">
          <h2>Notice of Action Taken</h2>
          <p className="notice-meta">
            {notice.creditor}<br />
            Application {notice.applicant_id} · {new Date(notice.date).toLocaleDateString()}
          </p>

          <p className="notice-action"><b>{notice.action_taken}</b></p>

          <h3>Principal reasons for our decision</h3>
          <ol className="notice-reasons">
            {notice.principal_reasons.map((r) => (
              <li key={r.code}>
                <b>{r.reason}</b>
                {r.what_you_can_do && <span> — {r.what_you_can_do}</span>}
              </li>
            ))}
          </ol>

          <h3>Use of a risk score</h3>
          <p>
            We used a statistical risk score in this decision. Your score was{" "}
            <b>{notice.score_disclosure.risk_score_pct}</b> on a scale of {notice.score_disclosure.scale}.
          </p>

          <h3>Your rights</h3>
          <p>{notice.appeal_rights}</p>
          <p className="notice-ecoa">{notice.ecoa_notice}</p>

          {notice.reviewed_by && (
            <p className="notice-meta">Reviewed and approved by: {notice.reviewed_by}</p>
          )}
          <p className="notice-disclaimer">{notice.disclaimer}</p>
        </div>
      </div>
    </div>
  );
}

/* ---------------------------- decision actions ------------------------------ */
function DecisionActions({ applicant, recommended }) {
  const recordDecision = useStore((s) => s.recordDecision);
  const loadReviews = useStore((s) => s.loadReviews);
  const recorded = useStore((s) => s.actions[applicant.id]);
  const source = useStore((s) => s.source);
  const fetchNotice = useStore((s) => s.fetchNotice);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [noticeBusy, setNoticeBusy] = useState(false);

  const openNotice = async () => {
    setNoticeBusy(true);
    setError(null);
    try {
      setNotice(await fetchNotice(recorded.id));
    } catch (e) {
      setError(e.message);
    } finally {
      setNoticeBusy(false);
    }
  };

  const commit = async (decision) => {
    setBusy(decision);
    setError(null);
    try {
      await recordDecision(applicant, decision, note);
      setNote("");
      loadReviews();   // an override may have just entered the approval queue
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  if (recorded) {
    const override = recorded.decision !== recommended;
    const pending = recorded.status === "pending_review";
    const rejected = recorded.status === "rejected";
    return (
      <div className={`recorded-box ${pending ? "wait" : rejected ? "no" : recorded.decision === "approve" ? "ok" : "no"}`}>
        <div className="recorded-head">
          <b>
            {pending ? "Awaiting manager approval"
              : rejected ? "Override rejected"
              : recorded.decision === "approve" ? "Approved" : "Declined"}
          </b>
          <span>by {recorded.actor}</span>
        </div>
        {pending && (
          <div className="recorded-override">
            {recorded.decision === "approve" ? "Approve" : "Decline"} override sent for sign-off.
          </div>
        )}
        {rejected && (
          <div className="recorded-override">
            Manager {recorded.reviewed_by} refused — model recommendation stands.
            {recorded.review_note && ` “${recorded.review_note}”`}
          </div>
        )}
        {!pending && !rejected && override && (
          <div className="recorded-override">
            Override — model recommended {recommended}
            {recorded.reviewed_by && ` · signed off by ${recorded.reviewed_by}`}
          </div>
        )}
        {recorded.note && <p className="recorded-note">“{recorded.note}”</p>}
        <div className="recorded-actions">
          <button className="mini" onClick={() => commit(recorded.decision === "approve" ? "decline" : "approve")}>
            Change decision
          </button>
          {recorded.decision === "decline" && recorded.status !== "pending_review" && (
            <button className="mini primary" disabled={noticeBusy} onClick={openNotice}>
              {noticeBusy ? "Preparing…" : "Decline notice"}
            </button>
          )}
        </div>
        {notice && <NoticeModal notice={notice} onClose={() => setNotice(null)} />}
        {error && <div className="batch-error">{error}</div>}
      </div>
    );
  }

  return (
    <div className="decide-box">
      <label className="decide-label" htmlFor={`note-${applicant.id}`}>
        Reason / note <span>(recorded in the audit trail)</span>
      </label>
      <textarea
        id={`note-${applicant.id}`}
        className="decide-note"
        rows={2}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="e.g. Verified payslips; long-standing customer."
      />
      <div className="decide-actions">
        <button className="btn-decide approve" disabled={!!busy || source !== "api"}
          onClick={() => commit("approve")}>
          {busy === "approve" ? "Saving…" : "✓ Approve"}
        </button>
        <button className="btn-decide decline" disabled={!!busy || source !== "api"}
          onClick={() => commit("decline")}>
          {busy === "decline" ? "Saving…" : "✕ Decline"}
        </button>
      </div>
      {source !== "api" && <div className="batch-note">Backend offline — decisions can't be saved.</div>}
      {error && <div className="batch-error">{error}</div>}
    </div>
  );
}

/* --------------------------------- drawer ----------------------------------- */
function ApplicantDrawer({ id, onClose }) {
  const applicantById = useStore((s) => s.applicantById);
  const features = useStore((s) => s.data.features);
  const base = useStore((s) => s.data.meta.base_risk);
  const threshold = useStore((s) => s.threshold);
  const a = applicantById(id);
  if (!a) return null;

  const contribs = features.map((f) => ({ label: f.label, v: a.shap[f.key] })).sort((x, y) => Math.abs(y.v) - Math.abs(x.v));
  const maxAbs = Math.max(...contribs.map((c) => Math.abs(c.v)), 1);
  const tradApprove = a.risk_traditional < threshold;
  const altApprove = a.risk < threshold;
  const flip = tradApprove !== altApprove;

  return (
    <div className="crm-drawer-overlay" onClick={onClose}>
      <aside className="crm-drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={`Applicant ${a.id}`}>
        <div className="crm-drawer-head">
          <div>
            <div className="mono crm-drawer-id">Applicant {a.id}</div>
            <div className="crm-drawer-sub">
              Credit score {a.credit_score} · ${Math.round(a.income).toLocaleString()}/yr
            </div>
          </div>
          <button className="mini" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {/* Verdict first — what the officer should actually do. */}
        <div className={`verdict-card ${altApprove ? "ok" : "no"}`}>
          <div className="verdict-line">
            <span className="verdict-word">{altApprove ? "Approve" : "Decline"}</span>
            <span className="verdict-conf">{a.risk.toFixed(0)}% chance of missed payments</span>
          </div>
          <p className="verdict-why">
            {altApprove
              ? `Out of 100 similar applicants, about ${Math.round(a.risk)} would fall behind — below your ${threshold}% limit.`
              : `Out of 100 similar applicants, about ${Math.round(a.risk)} would fall behind — above your ${threshold}% limit.`}
          </p>
        </div>

        {flip && (
          <div className={`flip ${altApprove ? "flip-up" : "flip-down"}`}>
            {altApprove
              ? "A traditional credit check would have rejected this person. Their payment behaviour shows they're reliable."
              : "A traditional credit check would have approved this person. Their recent behaviour suggests higher risk."}
          </div>
        )}

        <DecisionActions applicant={a} recommended={altApprove ? "approve" : "decline"} />

        <div className="reasons-head">Why — main factors</div>
        <ul className="reasons">
          {contribs.slice(0, 5).map((c) => {
            const good = c.v < 0;
            return (
              <li key={c.label} className={good ? "good" : "bad"}>
                <span className="reason-mark" aria-hidden="true">{good ? "✓" : "!"}</span>
                <span className="reason-text">{plainReason(c.label, good)}</span>
                <span className="reason-weight">{good ? "lowers" : "raises"} risk</span>
              </li>
            );
          })}
        </ul>

        <details className="tech-details">
          <summary>Technical detail</summary>
          <div className="compare-cards crm-drawer-compare">
            <div className="score-card">
              <div className="score-title">Credit score only</div>
              <div className="score-val" style={{ color: riskColor(a.risk_traditional) }}>{a.risk_traditional.toFixed(1)}%</div>
              <div className={`decision ${tradApprove ? "ok" : "no"}`}>{tradApprove ? "Approve" : "Decline"}</div>
            </div>
            <div className="score-card">
              <div className="score-title">+ Payment behaviour</div>
              <div className="score-val" style={{ color: riskColor(a.risk) }}>{a.risk.toFixed(1)}%</div>
              <div className={`decision ${altApprove ? "ok" : "no"}`}>{altApprove ? "Approve" : "Decline"}</div>
            </div>
          </div>
          <div className="shap-head crm-drawer-shap-head">
            <span>Model contributions (SHAP)</span><span>baseline {base.toFixed(0)}%</span>
          </div>
          {contribs.map((c) => (
            <div className="shap-row" key={c.label} title={`${c.v >= 0 ? "+" : ""}${c.v.toFixed(2)} pts`}>
              <span className="shap-label">{c.label}</span>
              <div className="shap-track">
                <div className="shap-bar" style={{
                  width: `${(Math.abs(c.v) / maxAbs) * 50}%`,
                  marginLeft: c.v >= 0 ? "50%" : `${50 - (Math.abs(c.v) / maxAbs) * 50}%`,
                  background: c.v >= 0 ? CATEGORY_COLORS.High : CATEGORY_COLORS.Low,
                }} />
              </div>
              <span className={`shap-val ${c.v >= 0 ? "pos" : "neg"}`}>{c.v >= 0 ? "+" : ""}{c.v.toFixed(1)}</span>
            </div>
          ))}
        </details>
      </aside>
    </div>
  );
}

/* --------------------------------- skeleton ---------------------------------- */
function CRMSkeleton() {
  return (
    <div className="app crm" aria-busy="true" aria-label="Loading dashboard">
      <nav className="nav crm-side">
        <div className="sk sk-brand" />
        <div className="sk-nav">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="sk sk-navitem" />)}</div>
      </nav>
      <div className="crm-main">
        <div className="sk sk-title" style={{ width: 220, height: 28, margin: "24px 0 24px 32px" }} />
        <div className="crm-table-wrap" style={{ margin: "0 32px" }}>
          {Array.from({ length: 6 }).map((_, i) => <div key={i} className="sk" style={{ height: 44, marginBottom: 8, borderRadius: 10 }} />)}
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------- root ------------------------------------- */
export default function Dashboard() {
  const load = useStore((s) => s.load);
  const loaded = useStore((s) => s.loaded);
  const user = useStore((s) => s.user);
  const [section, setSection] = useState("overview");
  const [openId, setOpenId] = useState(null);

  const loadActions = useStore((s) => s.loadActions);
  const loadReviews = useStore((s) => s.loadReviews);
  React.useEffect(() => {
    if (user) { load(); loadActions(); loadReviews(); }
  }, [load, loadActions, loadReviews, user]);

  if (!user) return <Login />;
  if (!loaded) return <CRMSkeleton />;

  return (
    <div className="app crm">
      <Sidebar section={section} setSection={setSection} />
      <main className="crm-main">
        {section === "overview" && <OverviewView goTo={setSection} onOpen={setOpenId} />}
        {section === "applicants" && <ApplicantsView onOpen={setOpenId} />}
        {section === "customers" && <CustomersView onOpen={setOpenId} />}
        {section === "pipeline" && <PipelineView onOpen={setOpenId} />}
        {section === "reports" && <ReportsView />}
        {section === "distribution" && <DistributionView onOpen={setOpenId} />}
        {section === "approvals" && <ApprovalsView />}
        {section === "audit" && <AuditView />}
        {section === "team" && <TeamView />}
      </main>
      {openId && <ApplicantDrawer id={openId} onClose={() => setOpenId(null)} />}
    </div>
  );
}
