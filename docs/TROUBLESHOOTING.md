# Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `XGBoostError: libxgboost.dylib could not be loaded` (macOS) | Missing OpenMP runtime | `brew install libomp` |
| Backend import error on models | Artifacts missing | Run `python3 train.py` (creates `models/*.joblib`) |
| Frontend shows **"Static snapshot"** badge | Backend not reachable at `/api/*` | Start `uvicorn server:app --port 8000`; check Vite proxy / origin |
| CSV upload button disabled | Backend offline (static mode) | Start the backend; upload needs the live API |
| `422` on upload | Missing required columns or all-empty rows | Use the template; ensure the 7 required columns are present |
| `413` on upload | File too large / too many rows | Under `CR_MAX_UPLOAD_BYTES` (2 MB) and `CR_MAX_ROWS` (10k) |
| `415` on upload | Not a CSV | Upload a `.csv` file |
| `429 Too many requests` | Rate limit hit | Wait a minute or raise `CR_RATE_LIMIT_PER_MIN` |
| `401` on `/api/score*` | `CR_API_KEY` is set | Send header `X-API-Key: <key>` |
| CORS error in browser | Origin not allowlisted | Add it to `CR_ALLOWED_ORIGINS` |
| 3D field blank | WebGL/context issue | Reload; the `ErrorBoundary` shows a fallback instead of a blank page |
| First `/api/applicants` slow (~5 s cold) | Model load + SHAP on first call | Expected once; subsequent calls are cached (~8 ms) |
| `npm run dev` port in use | 5175 taken | Vite picks the next port; check its console output |

More: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md), [DEPLOYMENT.md](DEPLOYMENT.md).
