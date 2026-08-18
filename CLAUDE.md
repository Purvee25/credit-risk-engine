# CLAUDE.md — Credit Risk Decision Engine

Guidance for AI agents (and humans) working in this repository. Read this first.

## Project Overview

**Purpose.** Predict loan-default risk using **traditional + alternative
(behavioral)** features to widen fair credit access for thin-file borrowers.
The thesis artifact is the *decision flip*: applicants a traditional model
rejects but behavioral data approves.

**Prototype only — synthetic data, not validated for production lending.**

### Folder structure
```
credit-risk-engine/
├── generate_data.py     # synthetic dataset (honest latent-risk design)
├── train.py             # train + eval 3 models × 2 feature sets → joblib
├── utils.py             # shared: load models, score, risk bands, SHAP explainer
├── export_web_data.py   # precompute scores + SHAP → web/public/data.json
├── server.py            # FastAPI backend (live scoring / SHAP / CSV)
├── app.py               # Streamlit analyst app (6 tabs)
├── requirements.txt · README.md · CLAUDE.md
├── data/applicants.csv
├── models/              # *.joblib, metrics.csv, feature_sets.json, best_models.json
└── web/                 # React + Vite + Three.js site (see web/README.md)
    └── src/{App,Site,Dashboard,Scene,Panels,HeroCloud,Login,store}.jsx · *.css
```

### Tech stack
- **ML/Data:** Python 3.13, pandas, NumPy, scikit-learn, XGBoost, SHAP, joblib
- **Backend:** FastAPI, Uvicorn, Pydantic
- **Frontend:** React 18, Vite, React Router, Three.js / R3F, Zustand
- **Analyst app:** Streamlit, Altair
- **Storage:** SQLAlchemy + SQLite (`CR_DATABASE_URL`; Postgres-ready) for the
  decision audit trail and user accounts; CSV + joblib for model artifacts.

### Architecture
`generate_data → train → models/*.joblib` is the core. `utils.py` is the single
source of scoring/SHAP logic, imported by **both** `server.py` and `app.py`
(never duplicate scoring). `export_web_data.py` snapshots output to
`web/public/data.json`. The React app calls `server.py` at `/api/*` and **falls
back** to the static snapshot when the backend is offline.

### Explainability (SHAP)
Probability-space contributions (a value reads directly as "+12% risk").
Built once and cached; TreeExplainer for tree models, model-agnostic for the
linear pipeline. Live in `utils.build_explainer` — reuse it, don't reimplement.

### Deployment architecture
Frontend → static host (Vercel/Netlify), works standalone via `data.json`.
Backend (`server.py`) → any ASGI host for live scoring. Streamlit → separate.

## Engineering Rules
- Search before reading; **never scan the whole repo**; load only relevant files.
- Respect existing architecture. **Prefer minimal diffs; never rewrite working code.**
- Reuse `utils.py` for anything scoring/SHAP. No duplicate functionality.
- Explain only when asked. Optimize token usage.

## Backend Standards (FastAPI)
- Typed **Pydantic** models for request/response bodies (not bare `dict`).
- Validate all inputs; cap upload size; validate content type on file endpoints.
- Use `Depends` for shared resources; artifacts already cached via `lru_cache`.
- Structured `logging` (no `print`); consistent `HTTPException` error shapes.
- `async def` for I/O-bound endpoints; keep CPU-bound scoring sync/threaded.

## Frontend Standards (React)
- Small, single-purpose components; keep scoring/data logic in `store.js`.
- Zustand for state; select narrowly to avoid re-renders.
- Gate per-frame work in R3F (`useFrame`) on dirty state; instance meshes.
- Lazy-load the heavy 3D route (`/app`) so marketing pages stay light.
- Accessibility: interactive elements are focusable (`button`/role+tabindex),
  emoji decorative icons get `aria-hidden`, inputs use `htmlFor`/`id`.
- Responsive: verify ≤820px breakpoint.

## AI/ML Standards
- **Reproducibility:** fixed seeds; pin versions; deterministic data gen.
- **No leakage:** fit scalers/encoders on train only (use `Pipeline`).
- **Split:** train / validation / test — validation for tuning, test untouched.
- **Imbalance:** class weighting (documented); report **AUC-PR/PR-curve**, not accuracy.
- **Calibration:** if scores are shown as probabilities, calibrate (Platt/isotonic).
- **Versioning:** persist model + metrics + data hash together.
- **Explainability:** SHAP via `utils`, probability space.

## Security Standards (OWASP)
- Validate/limit all inputs and uploads (size, type, row count).
- Restrict CORS to known origins in any non-local deploy.
- No secrets in code/repo; use env vars; never log secrets.
- **Auth is server-side** (`auth.py`): HMAC-signed session tokens; every `/api/*`
  route except `/api/health` and `/api/auth/*` requires one. Never take identity,
  role, or risk from a request body — derive identity/role from the token and
  recompute risk from the applicant's features.
- Manager (override sign-off) is **granted by a manager**, never self-selected at
  sign-up; a maker may not review their own override.
- Run `pip-audit` / `npm audit` before releases.

## Performance Standards
- Measure before optimizing. Cache model artifacts (done).
- Trim/lazy-load the Three.js bundle (~1 MB) off the marketing path.
- Avoid unnecessary per-frame recomputation and full-list React re-renders.

## Testing Standards
- Unit: `utils` scoring + risk bands; data-gen invariants.
- Integration: `train.py` produces expected artifacts/metrics ranges.
- API: FastAPI `TestClient` — happy path + 422 on bad columns + oversized upload.
- ML eval: assert AUC-PR(behavioral) > AUC-PR(traditional) as a regression guard.
- Never reduce existing coverage.

## Documentation Standards
- Keep `README.md`, `web/README.md`, and this file in sync with changes.
- Document new endpoints (FastAPI `/docs` + README table) and env vars.
- Update the deployment guide when the deploy flow changes.

## Git Workflow
- **Conventional Commits** (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `perf:`, `chore:`).
- Feature branches off the default branch; small logical commits.
- PR checklist: builds, lint/typecheck, tests pass, docs updated, minimal diff.
- **Never push or commit without explicit instruction.**
