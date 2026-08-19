# Credit Risk Decision Engine

**[▶ Live demo](https://purvee25.github.io/credit-risk-engine/)** — click *Launch demo* → *View demo (read-only)*. Shows a precomputed batch with SHAP explanations; recording decisions needs the backend running locally.

A credit-risk scoring prototype that predicts loan-default risk using **both
traditional and alternative (behavioral) features**, to explore fairer credit
access for **thin-file borrowers** — creditworthy people whom a conventional
score can't rate.

The project ships three surfaces over one modelling core:

- a **Python** pipeline (synthetic data → models → SHAP),
- a **Streamlit** analyst app (`app.py`), and
- an immersive **React + Three.js** 3D web app (`web/`).

> ⚠️ **Prototype for demonstration only.** Trained on synthetic data and **not
> validated for production lending decisions.** Do not use it to approve, deny,
> or price real credit.

---

## The thesis

Tens of millions of people are *thin-file*: little or no traditional credit
history, so a conventional score rejects them or can't rate them. Yet many show
strong **behavioral** signals of reliability — paying on time, stable debt,
responsibly managed variable income. This tool tests whether adding those
signals produces fairer, more accurate decisions than a traditional score alone.

The central artifact is the **decision flip**: applicants a traditional model
rejects but the behavioral model approves.

---

## Results

Best model per feature set, on a held-out 25% test split (default rate ≈ 22%):

| Feature set | Best model | Precision | Recall | F1 | **AUC-PR** |
|---|---|---|---|---|---|
| Traditional | Logistic Regression | 0.393 | 0.690 | 0.501 | **0.520** |
| Traditional + Behavioral | Logistic Regression | 0.517 | 0.823 | 0.635 | **0.668** |

Adding behavioral features lifts the headline **AUC-PR from 0.52 → 0.67 (+0.15)**,
with recall rising 0.69 → 0.82 — the improvement concentrated among thin-file
applicants by design. Full comparison across all 3 models × 2 feature sets is in
`models/metrics.csv`.

**Why AUC-PR, not accuracy?** Defaults are the rare class; accuracy is a vanity
metric here (a "reject everyone" model looks ~78% accurate). AUC-PR (average
precision) measures how well the model separates defaulters from non-defaulters.

---

## Methodology & dataset (read this)

The 5,000 applicants are **synthetic and generated** by `generate_data.py`. The
generator is deliberately designed so the "behavioral data helps" result is
*earned, not rigged*:

1. A latent **true creditworthiness** is drawn from both traditional drivers
   (income, debt-to-income) **and** behavioral drivers (payment consistency,
   income volatility, debt trend).
2. `default` is sampled from that latent state — **not** directly from the
   observed features.
3. Observed traditional features (especially `credit_score`) are **noisy,
   lagging proxies** of the latent state, and the noise is **larger for thin-file
   borrowers** (short employment / little history).
4. The behavioral signal is **amplified for thin files** — exactly the
   financial-inclusion story the app is about.

Because the model must recover the behavioral signal from noisy inputs, its win
is a real result. The *magnitude* of improvement is illustrative (synthetic),
not a market estimate.

Columns: `income, employment_length, existing_debt, loan_amount, credit_score,
payment_consistency_pct, income_volatility_score, debt_trend, default`.

**Feature sets**
- **Traditional:** `credit_score, income, existing_debt, loan_amount`
- **Traditional + Alternative:** adds `payment_consistency_pct,
  income_volatility_score, debt_trend`

**Modeling**
- Logistic Regression, Random Forest, XGBoost on both feature sets.
- Class imbalance handled with **class weighting** (`class_weight="balanced"` /
  `scale_pos_weight`) rather than SMOTE — simpler and better-calibrated on
  mixed-scale tabular data.
- **SHAP** explains individual predictions in probability space (contributions
  read directly as "+/- risk %").

---

## Project layout

```
credit-risk-engine/
├── generate_data.py       # synthetic dataset (honest latent-risk design)
├── train.py               # train + evaluate 3 models × 2 feature sets, save with joblib
├── utils.py               # shared: load models, score, risk categories, SHAP explainer
├── export_web_data.py     # precompute scores + SHAP -> web/public/data.json
├── app.py                 # Streamlit analyst app (6 tabs)
├── requirements.txt
├── data/applicants.csv    # generated dataset
├── models/                # *.joblib models, metrics.csv, feature_sets.json, best_models.json
└── web/                   # React + Three.js 3D front-end (see web/README.md)
```

---

## Quickstart

### 1. Python pipeline

```bash
python3 -m pip install -r requirements.txt   # macOS: also `brew install libomp` for xgboost
python3 generate_data.py       # -> data/applicants.csv  (+ correlation sanity report)
python3 train.py               # -> models/*.joblib, metrics.csv, best_models.json
python3 export_web_data.py      # -> web/public/data.json  (for the 3D app)
```

### 2. Streamlit analyst app

```bash
streamlit run app.py           # http://localhost:8501
```

Six tabs: **Overview**, **Batch Assessment** (CSV upload + demo batch, live
approval-threshold slider, risk histogram, exportable results), **Applicant
Drill-Down** (per-applicant SHAP), **Traditional vs Alternative** (decision
flips), **Fairness Check** (approval by income bracket), **Model Performance &
Limitations**.

### 3. Backend API (optional — enables live scoring)

```bash
uvicorn server:app --reload --port 8000    # docs at http://localhost:8000/docs
```

`server.py` (FastAPI) serves the trained models over HTTP. Every endpoint
except `/api/health` and `/api/auth/{register,login}` requires a session token:
sign in, then send `Authorization: Bearer <token>`.

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/health` | — | liveness + best model per feature set |
| `POST /api/auth/register` | — | create an account (always an analyst; the very first account is a manager) |
| `POST /api/auth/login` | — | exchange credentials for a session token |
| `GET /api/auth/me` | any | who the current token belongs to |
| `GET /api/meta` | any | base risk, income range, feature list, best models |
| `GET /api/metrics` | any | full model-comparison table |
| `GET /api/applicants?n=250` | any | ready-scored demo batch (with SHAP) |
| `POST /api/score` | any | score a JSON batch of applicants |
| `POST /api/score-csv` | any | score an uploaded CSV |
| `GET/POST /api/decisions` | any | audit trail; record an officer decision |
| `GET /api/actions` | any | latest decision per applicant |
| `GET /api/reviews` | any | overrides awaiting manager sign-off |
| `POST /api/reviews/{id}` | manager | sign off or refuse an override (never your own) |
| `GET /api/notices/{id}` | any | adverse-action notice for a decline (ECOA/Reg B) |
| `GET /api/users` | manager | team roster |
| `POST /api/users/role` | manager | grant or withdraw manager access |

**Trust boundary.** The client never supplies identity, role, or risk. Identity
and role come from the signed token; risk is recomputed server-side from the
applicant's features before any decision is written.

Key environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `CR_SECRET_KEY` | random per process | signs session tokens — **set this in any deployment** |
| `CR_TOKEN_TTL` | `28800` (8 h) | session lifetime, seconds |
| `CR_DATABASE_URL` | `sqlite:///data/decisions.db` | audit-trail + accounts store |
| `CR_ALLOWED_ORIGINS` | localhost dev ports | CORS allowlist |
| `CR_RATE_LIMIT_PER_MIN` | `60` | per-IP request cap |
| `CR_API_KEY` | unset | extra `X-API-Key` gate on scoring routes |

### 4. 3D web app

```bash
cd web && npm install && npm run dev    # http://localhost:5175
```

See [`web/README.md`](web/README.md). The app calls the backend at `/api/*`
(Vite proxies to `:8000`; override with `VITE_API_PORT`) and **falls back to the static `public/data.json`** if
the backend is offline — a "Live API" / "Static snapshot" badge in the sidebar
shows which source is active.

---

## Design system

The UI direction — **"Lumina" spatial glassmorphism** (deep navy, cyan accent,
semantic green/amber/red for risk, Inter type) — was prototyped in
[Google Stitch](https://stitch.withgoogle.com) and imported into Figma as an
editable design file with bound color variables. Both the Streamlit and 3D apps
follow the same palette and hierarchy.

---

## Limitations

- **Synthetic data** — magnitudes are illustrative, not market estimates.
- **No temporal validation** — a single static split; real credit models must be
  validated across time and economic cycles.
- **Partial fairness lens** — income-bracket *access* only (income is not a
  protected attribute). A real audit needs protected attributes, disparate-impact
  testing, and legal review.
- **Not calibrated for pricing** — scores rank risk; they are not calibrated
  probabilities for setting rates or reserves.

**This is a prototype for demonstration purposes, not validated for production
lending decisions.**
