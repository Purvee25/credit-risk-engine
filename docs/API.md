# API Reference

FastAPI backend (`server.py`). Base URL `http://localhost:8000`. Interactive
docs at `/docs` (OpenAPI). Config via env — see [`.env.example`](../.env.example).

## Authentication

All endpoints except `GET /api/health`, `POST /api/auth/register` and
`POST /api/auth/login` require a session token:

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@lender.com","password":"..."}' | jq -r .token)
curl localhost:8000/api/applicants -H "Authorization: Bearer $TOKEN"
```

Identity, role and risk are **never** read from a request body — identity and
role come from the token, risk is recomputed from the applicant's features.

## Endpoints

| Method | Path | Auth¹ | Rate-limited | Description |
|--------|------|-------|--------------|-------------|
| GET | `/api/health` | no | yes | Liveness + best model per feature set |
| GET | `/api/meta` | no | yes | Base risk, income range, feature list, best models |
| GET | `/api/metrics` | no | yes | Model comparison table (6 rows) |
| GET | `/api/applicants?n=250` | no | yes | Cached, ready-scored demo batch (with SHAP) |
| POST | `/api/score` | optional | yes | Score a JSON batch of applicants |
| POST | `/api/score-csv` | optional | yes | Score an uploaded CSV |

¹ Auth enforced only when `CR_API_KEY` is set (header `X-API-Key`).

## Models

**Applicant** (request) — bounded fields:
`credit_score` 300–850, `income` ≥0, `existing_debt` ≥0, `loan_amount` ≥0,
`payment_consistency_pct` 0–100, `income_volatility_score` 0–100,
`debt_trend` −1..1, optional `id`.

**ScoredApplicant** (response) — the applicant fields plus `risk`,
`risk_traditional`, `category` (Low/Medium/High), and `shap` (per-feature
contribution, percentage points).

## Examples

```bash
# Score a batch
curl -X POST localhost:8000/api/score -H 'Content-Type: application/json' -d '{
  "applicants":[{"credit_score":780,"income":80000,"existing_debt":14000,
    "loan_amount":28000,"payment_consistency_pct":79,
    "income_volatility_score":12,"debt_trend":0.1}]}'

# Score a CSV
curl -X POST localhost:8000/api/score-csv -F file=@applicants.csv

# With auth enabled
curl -X POST localhost:8000/api/score -H 'X-API-Key: <key>' ...
```

## Status codes

| Code | When |
|------|------|
| 200 | Success |
| 401 | API key required/invalid (when `CR_API_KEY` set) |
| 413 | Upload too large / too many rows |
| 415 | Non-CSV upload |
| 422 | Validation failed / missing required columns / no valid rows |
| 429 | Rate limit exceeded |
