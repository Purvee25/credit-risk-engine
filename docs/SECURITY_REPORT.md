# Security Report — Phase 4

OWASP Top-10 review of the FastAPI backend, with fixes applied. This is a
prototype on synthetic data; controls are sized accordingly and configured via
environment variables (see `.env.example`).

## Controls implemented (`server.py`)

| Area | Control | Detail |
|------|---------|--------|
| Rate limiting | In-memory sliding window | `CR_RATE_LIMIT_PER_MIN` (default 60) per client IP → **429** when exceeded. |
| Secure headers | Response middleware | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, restrictive `Content-Security-Policy`. |
| Authentication | Signed session tokens (`auth.py`) | HMAC-SHA256 over a base64 payload, `CR_SECRET_KEY`, `CR_TOKEN_TTL` (8 h). Every `/api/*` route except `/api/health` and `/api/auth/*` requires `Authorization: Bearer` → **401** otherwise. |
| Passwords | PBKDF2-HMAC-SHA256 | 240 000 rounds, per-user salt; never logged or returned. |
| Authorization | Role from the token | `require_manager` gates review sign-off and team administration → **403**. Roles are granted by a manager, not chosen at sign-up. |
| Decision integrity | Server-side re-scoring | `/api/decisions` ignores any client-supplied `risk`/`actor`/`role` and recomputes risk from the applicant's features. |
| Segregation of duties | Four-eyes check | A maker cannot sign off their own override (**403**), even as a manager. |
| API key | Optional extra gate | `X-API-Key` on `/api/score*` when `CR_API_KEY` is set — layered on top of session auth. |
| Input validation | Pydantic `Applicant` (Phase 1) | Bounded numeric fields; batch `min_length=1`, `max_length=MAX_ROWS`. |
| File upload | Content-type + size + row caps | Non-CSV → **415**; > `CR_MAX_UPLOAD_BYTES` → **413**; > `CR_MAX_ROWS` → **413**. |
| CORS | Env allowlist (Phase 1) | `CR_ALLOWED_ORIGINS`; methods limited to GET/POST. |
| Secrets | Env only | No secrets in code/repo; `.env.example` documents all vars; `.env` git-ignored. |
| Logging | Structured (Phase 1) | Scoring events + rejected uploads + rate-limit/auth failures; no secrets logged. |

## OWASP Top-10 (2021) status

| # | Category | Status |
|---|----------|--------|
| A01 Broken Access Control | Session token required on all data routes; role checks server-side; maker≠checker enforced. **Addressed.** |
| A02 Cryptographic Failures | Passwords hashed (PBKDF2, 240k rounds); token secret from `CR_SECRET_KEY`; deploy behind TLS (host-terminated). **Addressed.** |
| A03 Injection | SQLAlchemy ORM (parameterised) for all DB access; inputs typed/validated before pandas; no `eval`/shell. **Low.** |
| A04 Insecure Design | Threat model documented; upload + rate limits by design. **Addressed.** |
| A05 Security Misconfiguration | Secure headers, env-driven config, non-wildcard CORS. **Addressed.** |
| A06 Vulnerable Components | `pip-audit` + `npm audit` run — see below. **Patched.** |
| A07 Auth Failures | Real server-side sessions: PBKDF2 password hashing, signed tokens with expiry, constant-time signature compare, no identity accepted from request bodies. **Addressed.** |
| A08 Integrity Failures | Deps pinned; no untrusted deserialization (`joblib` loads first-party models only). **Low.** |
| A09 Logging/Monitoring | Structured logging on key events. **Addressed** (metrics/alerting = deploy-time). |
| A10 SSRF | No server-side outbound fetches from user input. **N/A.** |

## Dependency audit

**Python (`pip-audit`)** — found & fixed:
- `python-multipart 0.0.20` → 6 CVEs (PYSEC-2026-3040, -3039, -3038, -3037, -3036, -1852).
  **Fixed:** pinned to `0.0.32` (≥0.0.31).

**JS (`npm audit`, prod deps):**
- `react-router` / `react-router-dom` — 2 moderate advisories.
  **Recommendation:** bump `react-router-dom` to the patched 6.30.x+ in a
  frontend chore (no code change needed). Not applied here to keep this phase
  backend-scoped.

## Known limitations (prototype)
- Rate limiter is **per-process, in-memory** — for multi-instance deploys use a
  shared store (Redis) or an edge/CDN limiter.
- API key is a single shared secret (no rotation/scopes) — sufficient for a demo,
  not for multi-tenant production.
- No TLS in app — terminate at the host/proxy (Render/Vercel/nginx).

## Verify
```bash
python3 -m pytest -q          # 14 passed (incl. 429, 401, 415, secure-headers)
python3 -m pip_audit -r requirements.txt
cd web && npm audit --omit=dev
```

## Hardening sprint (post-audit)

A project-management review probed the running service and found six defects,
all since closed and covered by tests in `tests/test_api.py`:

| # | Defect | Fix |
|---|--------|-----|
| 1 | Every `/api/*` route was unauthenticated | Session tokens; `Depends(auth.current_user)` on all data routes |
| 2 | `actor`/`actor_role` taken from the request body | Derived from the token; body fields removed from the schema |
| 3 | `risk` accepted from the client (a 99.8%-risk applicant could be filed as 1%) | Recomputed server-side before the row is written |
| 4 | A maker could sign off their own override | **403** when `reviewer == maker` |
| 5 | Container DB lived on the writable layer and `data/` was copied into the image | Named volume `api-data:/data`; `data/*.db` in `.dockerignore` |
| 6 | Anyone could self-register as a manager | Sign-up is always analyst; managers are appointed via `POST /api/users/role` (first account bootstraps) |
