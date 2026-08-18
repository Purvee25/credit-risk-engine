# Credit Risk Decision Engine — 3D Web Front-End

An immersive WebGL front-end for the Credit Risk Decision Engine, built with
React, Vite, and React Three Fiber. Every loan applicant is a point in a 3D
"risk field" (height = default risk, colour = verdict); the panels explain
individual decisions with SHAP and contrast traditional vs. behavioural scoring.

The app calls the **FastAPI backend** (`../server.py`) at `/api/*` for live
scoring, and **falls back to the static `public/data.json`** snapshot if the
backend is offline. A badge in the sidebar shows which source is active.

## Run

```bash
# 1. (optional) start the backend for live scoring, from the project root:
uvicorn server:app --port 8000

# 2. start the front-end:
cd web
npm install
npm run dev          # http://localhost:5175  (Vite proxies /api -> :8000)
```

Without step 1 the app still runs — it uses the bundled `public/data.json`.

Build for production:

```bash
npm run build        # outputs to web/dist
npm run preview
```

## Regenerating the data

The 3D app reads `public/data.json`. To refresh it after retraining the models:

```bash
cd ..                # project root
python3 export_web_data.py   # rewrites web/public/data.json
```

## Structure

| File | Responsibility |
|------|----------------|
| `src/main.jsx` | React entry point |
| `src/App.jsx` | Layout shell, sidebar nav, demo auth gate, user menu |
| `src/Login.jsx` | Demo login screen (no real credentials) |
| `src/Scene.jsx` | The R3F canvas: instanced applicant cloud, threshold plane, camera rig |
| `src/Panels.jsx` | HTML overlay panels for each view (Portfolio, Applicant/SHAP, Compare, Fairness, Performance) |
| `src/store.js` | Zustand store: data, view, threshold, selection, demo auth |
| `src/styles.css` | Dark "Lumina" spatial styling |
| `public/data.json` | Precomputed scores + SHAP for 250 demo applicants |

## Live CSV scoring

On the **Portfolio** view (when the backend is connected), you can:

- **Download a template** CSV (correct columns, seeded from the current batch),
- **Upload a CSV** of your own applicants — it is scored by the live backend
  (`POST /api/score-csv`) and the entire 3D field + all views re-render from the
  results,
- **Reset** back to the demo batch.

Required columns: `credit_score, income, existing_debt, loan_amount,
payment_consistency_pct, income_volatility_score, debt_trend` (an `id` column is
optional). Missing required columns return a clear 422 error in the UI.

## Notes

- **Demo auth only.** The login is a UI gate persisted to `localStorage` — it does
  not authenticate against any server and stores no credentials.
- **Performance.** The applicant cloud uses a single instanced mesh; the demo set
  is 250 points. The scene caps device pixel ratio and drops to a horizontal
  top-nav layout below 860px.
- This is a **prototype for demonstration**, not a validated production lending tool.
