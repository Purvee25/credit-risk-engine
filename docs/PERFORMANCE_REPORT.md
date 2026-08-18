# Performance Report — Phase 5

Methodology: **measure first, optimize only proven bottlenecks.** Backend timed
with `TestClient` (p50/p95 over N runs); SHAP isolated from scoring; frontend
already profiled via the production build in Phase 2.

## Backend — baseline (before)

| Endpoint / op | p50 | Note |
|---|---|---|
| `GET /api/health` | 1.1 ms | trivial |
| `GET /api/metrics` | 1.8 ms | CSV read + round |
| `POST /api/score` (1 row) | 4.4 ms | fine |
| **`GET /api/applicants` (n=250)** | **395 ms** | **bottleneck** |
| score-only (n=250) | **0.4 ms** | — |
| **shap-only (n=250)** | **389 ms** | ~99% of the endpoint |

**Diagnosis:** scoring is negligible; **SHAP dominates**. The linear model uses
the model-agnostic SHAP explainer (permutation over a 100-row background), which
calls `predict_proba` many times. Crucially, `/api/applicants` serves a
**deterministic** batch (`random_state=7`) yet recomputed SHAP on every request.

## Optimization applied

**Cache the deterministic demo batch** — `@lru_cache` on `_demo_scored(n)` in
`server.py`. Same output; SHAP now runs once per size instead of per request.
This is the whole endpoint's cost, so it's the only change that moves the needle.
No accuracy change; user-supplied `/api/score*` batches are unaffected (correctly
recomputed).

| `GET /api/applicants` (n=250) | Before | After |
|---|---|---|
| warm repeat call | 395 ms | **8.5 ms** (~46×) |

(First cold call still pays one SHAP + model-load cost; every subsequent call —
i.e. every page load / reload / concurrent user — is now ~8 ms.)

## Not optimized (deliberately)
- **SHAP explainer speed for user batches** — a real cost, but changing
  `utils.build_explainer` (e.g. shrinking the background sample) trades accuracy
  and touches the app's drill-down SHAP. Left as a documented tunable
  (`background sample` size) rather than a risky change. User batches are small
  in practice.
- **Model inference** — already 0.4 ms; nothing to do.
- **Artifacts loading** — already `lru_cache`d (loaded once).

## Frontend (from Phase 2, unchanged this phase)
- Initial bundle **1044 KB → 180 KB** via `React.lazy` code-splitting; Three.js
  in its own lazy chunk.
- `Scene` recolors instances **only on input change**, not every frame.
- Data fetch **shared** between HeroCloud and Dashboard (one request).

No further frontend bottleneck was measured that justifies change now.
Candidates for a future pass (not needed yet): `manualChunks` to split Three.js
from `store`, and virtualization if the applicant table grows large.

## Reproduce
```bash
python3 -m pytest -q         # 14 passed
# timing harness used above lives in the Phase 5 command log
```
