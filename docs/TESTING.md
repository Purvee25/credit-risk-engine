# Testing & Coverage — Phase 6

## Suite

22 tests, all passing (`python3 -m pytest -q`).

| File | Kind | Covers |
|------|------|--------|
| `tests/test_utils.py` | unit | risk bands, `validate_columns`, `score` range, loaders, SHAP additivity, ML thesis guard (AUC-PR alt > trad) |
| `tests/test_api.py` | integration (FastAPI `TestClient`) | health, meta, metrics, JSON scoring (happy / out-of-range 422 / empty 422), CSV scoring (happy / missing-cols 422 / unreadable 400 / all-missing 422 / non-CSV 415 / oversized 413), security (secure headers, API-key 401, rate-limit 429) |

## Coverage (runtime-critical modules)

Measured with the stdlib `trace` module (no external coverage dep available in
this environment):

| Module | Executable lines | Covered | % |
|--------|------------------|---------|---|
| `server.py` | 178 | 178 | **100%** |
| `utils.py`  | 64  | 64  | **100%** |

Target was **80%+**; the API surface and shared scoring/SHAP logic are fully
exercised.

**Out of scope (offline scripts, not runtime):** `generate_data.py`, `train.py`,
`train_cv.py`, `evaluate.py`, `export_web_data.py` are one-shot pipeline scripts;
their correctness is guarded indirectly by `test_loaders_shapes`,
`test_behavioral_beats_traditional_auc_pr`, and the artifacts they produce.
`app.py` (Streamlit) has no headless test harness.

**Frontend:** no JS test framework is installed. Optional future add: Vitest +
tests for `store.js` selectors and risk-band logic (adds devDependencies).

## Run

```bash
python3 -m pytest -q                 # 22 passed

# Coverage (stdlib trace):
python3 -m trace --count --coverdir=/tmp/cov -m pytest
#   then inspect /tmp/cov/*.server.cover and *.utils.cover
```
