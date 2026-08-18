# Developer Guide

## Prerequisites
- Python 3.11+ (tested on 3.13), Node 18+.
- macOS + XGBoost: `brew install libomp`.

## Setup
```bash
pip install -r requirements.txt
cd web && npm ci && cd ..
```

## Run everything (3 terminals)
```bash
# 1. Backend (live scoring)
uvicorn server:app --reload --port 8000        # docs at /docs

# 2. Frontend
cd web && npm run dev                           # http://localhost:5175

# 3. Streamlit analyst app (optional)
streamlit run app.py                            # http://localhost:8501
```
The frontend runs without the backend (static `data.json` fallback).

## Regenerate data / models
```bash
python3 generate_data.py       # data/applicants.csv
python3 train.py               # models/*.joblib, metrics.csv
python3 export_web_data.py      # web/public/data.json
```

## Tests
```bash
python3 -m pytest -q            # 22 passed
```

## Project conventions
See [`CLAUDE.md`](../CLAUDE.md): search-before-read, minimal diffs, reuse
`utils.py` for scoring/SHAP, typed FastAPI models, Conventional Commits.

## Layout
```
generate_data.py train.py train_cv.py utils.py export_web_data.py
server.py app.py evaluate.py requirements.txt .env.example
data/  models/  reports/  tests/  docs/  web/src/
```

## Key files to know
- `utils.py` — scoring + SHAP (the shared core).
- `server.py` — API, security middleware, caching.
- `web/src/store.js` — frontend state + data fetch.
- `web/src/Scene.jsx` — the 3D risk field.
