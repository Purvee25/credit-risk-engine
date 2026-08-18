"""
Credit Risk Decision Engine — FastAPI backend.

Serves the trained models over HTTP so the front-ends can score applicants in
real time (traditional + alternative), explain them with SHAP, upload their own
CSV batches, and read the model-comparison metrics — instead of relying only on
the precomputed static data.json.

Run:  uvicorn server:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

import io
import logging
import os
import time
from collections import defaultdict, deque
from functools import lru_cache
from typing import Literal

import pandas as pd
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import auth
import db
import notices
import utils

# Structured logging (level via CR_LOG_LEVEL).
logging.basicConfig(
    level=os.getenv("CR_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("credit_risk.api")

# --- Config (all via env; safe local defaults) ------------------------------ #
MAX_UPLOAD_BYTES = int(os.getenv("CR_MAX_UPLOAD_BYTES", 2_000_000))  # 2 MB
MAX_ROWS = int(os.getenv("CR_MAX_ROWS", 10_000))
RATE_LIMIT = int(os.getenv("CR_RATE_LIMIT_PER_MIN", 60))  # requests/min/IP
DEFAULT_THRESHOLD = float(os.getenv("CR_DEFAULT_THRESHOLD", 25))  # approve-below %
API_KEY = os.getenv("CR_API_KEY")  # if unset, auth is disabled (dev default)

app = FastAPI(title="Credit Risk Decision Engine API", version="1.0.0")


@app.on_event("startup")
def _startup():
    """Create the decision audit store if it doesn't exist yet."""
    db.init_db()


# CORS: restrict to an env-configured allowlist (comma-separated).
_origins = os.getenv(
    "CR_ALLOWED_ORIGINS", "http://localhost:5175,http://localhost:5173"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


@app.middleware("http")
async def secure_headers(request: Request, call_next):
    """Attach standard hardening headers to every response."""
    response = await call_next(request)
    for k, v in _SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    return response


# In-memory sliding-window rate limiter (per process; per client IP).
_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _hits[ip]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= RATE_LIMIT:
        logger.warning("Rate limit exceeded for %s", ip)
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=429, content={"detail": "Too many requests."})
    window.append(now)
    return await call_next(request)


def require_api_key(x_api_key: str | None = Header(default=None)):
    """Optional auth: enforced only when CR_API_KEY is set in the environment."""
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


# --------------------------------------------------------------------------- #
# Cached model artifacts (loaded once)
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _artifacts():
    alt_model, alt_name, alt_cols = utils.load_best_model("alternative")
    trad_model, trad_name, trad_cols = utils.load_best_model("traditional")
    background = pd.read_csv(f"{utils.HERE}/data/applicants.csv")
    explain = utils.build_explainer(
        alt_model, background.sample(200, random_state=1), alt_cols)
    base = float(explain(background.head(1))[1]) * 100
    return {
        "alt": (alt_model, alt_name, alt_cols),
        "trad": (trad_model, trad_name, trad_cols),
        "explain": explain,
        "background": background,
        "base_risk": round(base, 2),
    }


def _score_frame(df: pd.DataFrame, with_shap: bool = True) -> list[dict]:
    """Score a dataframe of applicants and return front-end-shaped records."""
    art = _artifacts()
    alt_model, _, alt_cols = art["alt"]
    trad_model, _, trad_cols = art["trad"]

    missing, _ = utils.validate_columns(df, alt_cols)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required column(s): {', '.join(missing)}. "
                   f"Required: {', '.join(alt_cols)}.")
    df = df.dropna(subset=alt_cols).reset_index(drop=True)
    if df.empty:
        raise HTTPException(status_code=422, detail="No valid rows after dropping missing values.")

    if "id" not in df.columns:
        df = df.copy()
        df.insert(0, "id", [f"APP-{i:04d}" for i in range(1, len(df) + 1)])

    risk = utils.score(df, alt_model, alt_cols)
    risk_trad = utils.score(df, trad_model, trad_cols)
    shap_vals = art["explain"](df)[0] if with_shap else None

    records = []
    for i, row in df.iterrows():
        rec = {
            "id": str(row["id"]),
            "income": float(row["income"]),
            "credit_score": int(row["credit_score"]),
            "existing_debt": float(row["existing_debt"]),
            "loan_amount": float(row["loan_amount"]),
            "payment_consistency_pct": float(row["payment_consistency_pct"]),
            "income_volatility_score": float(row["income_volatility_score"]),
            "debt_trend": float(row["debt_trend"]),
            "risk": round(float(risk[i]), 2),
            "risk_traditional": round(float(risk_trad[i]), 2),
            "category": utils.risk_category(risk[i] / 100),
        }
        if with_shap:
            rec["shap"] = {c: round(float(shap_vals[i, j] * 100), 3)
                           for j, c in enumerate(alt_cols)}
        records.append(rec)
    return records


class Applicant(BaseModel):
    """A single applicant to score. Bounds mirror the training feature ranges."""
    id: str | None = None
    credit_score: int = Field(ge=300, le=850)
    income: float = Field(ge=0)
    existing_debt: float = Field(ge=0)
    loan_amount: float = Field(ge=0)
    payment_consistency_pct: float = Field(ge=0, le=100)
    income_volatility_score: float = Field(ge=0, le=100)
    debt_trend: float = Field(ge=-1, le=1)


class ApplicantBatch(BaseModel):
    applicants: list[Applicant] = Field(min_length=1, max_length=MAX_ROWS)


class ScoredApplicant(BaseModel):
    id: str
    income: float
    credit_score: int
    existing_debt: float
    loan_amount: float
    payment_consistency_pct: float
    income_volatility_score: float
    debt_trend: float
    risk: float
    risk_traditional: float
    category: str
    shap: dict[str, float] | None = None


class BatchResponse(BaseModel):
    applicants: list[ScoredApplicant]


class CsvResponse(BatchResponse):
    filename: str | None = None


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health():
    art = _artifacts()
    return {"status": "ok", "best_alternative": art["alt"][1],
            "best_traditional": art["trad"][1]}


def _meta_payload():
    """Model/feature metadata. Shared by /api/meta and /api/applicants."""
    art = _artifacts()
    bg = art["background"]
    return {
        "base_risk": art["base_risk"],
        "income_min": float(bg["income"].min()),
        "income_max": float(bg["income"].max()),
        "features": [{"key": c, "label": utils.FEATURE_LABELS[c]}
                     for c in art["alt"][2]],
        "best": utils.load_best_models(),
    }


@app.get("/api/meta")
def meta(user: dict = Depends(auth.current_user)):
    return _meta_payload()


@app.get("/api/metrics")
def metrics(user: dict = Depends(auth.current_user)):
    return utils.load_metrics().round(4).to_dict(orient="records")


@lru_cache(maxsize=8)
def _demo_scored(n: int):
    """Score the deterministic demo batch once per size (SHAP is the bottleneck)."""
    art = _artifacts()
    batch = (art["background"].drop(columns=[utils.TARGET])
             .sample(min(n, len(art["background"])), random_state=7)
             .reset_index(drop=True))
    batch.insert(0, "id", [f"APP-{i:04d}" for i in range(1, len(batch) + 1)])
    return _score_frame(batch)


@app.get("/api/applicants")
def demo_applicants(n: int = 250, user: dict = Depends(auth.current_user)):
    """A ready-scored demo batch (same shape the 3D app expects). Cached."""
    return {"meta": _meta_payload(), "applicants": _demo_scored(n)}


@app.post("/api/score", response_model=BatchResponse, dependencies=[Depends(require_api_key)])
def score(batch: ApplicantBatch, threshold: float = DEFAULT_THRESHOLD,
          user: dict = Depends(auth.current_user)):
    """Score a JSON batch of applicants supplied by the client."""
    df = pd.DataFrame([a.model_dump() for a in batch.applicants])
    logger.info("Scoring JSON batch of %d applicants", len(df))
    records = _score_frame(df)
    db.log_decisions(records, threshold, source="api",
                     model_version=_artifacts()["alt"][1])
    return {"applicants": records}


@app.post("/api/score-csv", response_model=CsvResponse, dependencies=[Depends(require_api_key)])
async def score_csv(file: UploadFile = File(...), threshold: float = DEFAULT_THRESHOLD,
                    user: dict = Depends(auth.current_user)):
    """Score an uploaded CSV of applicants (size- and row-capped)."""
    if file.content_type not in (None, "text/csv", "application/vnd.ms-excel",
                                 "application/octet-stream", "application/csv"):
        raise HTTPException(status_code=415, detail="Only CSV uploads are accepted.")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        logger.warning("Rejected upload %r: %d bytes", file.filename, len(content))
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_UPLOAD_BYTES // 1_000_000} MB).")
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {e}")
    if len(df) > MAX_ROWS:
        raise HTTPException(
            status_code=413, detail=f"Too many rows (max {MAX_ROWS}).")
    logger.info("Scoring CSV %r with %d rows", file.filename, len(df))
    records = _score_frame(df)
    db.log_decisions(records, threshold, source="csv",
                     model_version=_artifacts()["alt"][1])
    return {"filename": file.filename, "applicants": records}


# --------------------------------------------------------------------------- #
# Decision audit trail
# --------------------------------------------------------------------------- #
@app.get("/api/decisions")
def decisions(limit: int = 100, applicant_id: str | None = None,
              user: dict = Depends(auth.current_user)):
    """Recorded decisions, newest first — the reproducible audit trail."""
    limit = max(1, min(limit, 1000))
    return {
        "stats": db.decision_stats(),
        "decisions": db.recent_decisions(limit=limit, applicant_id=applicant_id),
    }


@app.get("/api/actions")
def actions(user: dict = Depends(auth.current_user)):
    """Latest officer decision per applicant (recorded status for the queue)."""
    return {"actions": db.latest_actions()}


class ActionRequest(BaseModel):
    """
    An officer committing a decision on an applicant.

    Note what is NOT accepted here: identity, role, and the risk score. Those
    are derived server-side — identity/role from the session token, risk by
    re-scoring the applicant's features with the model. Trusting any of them
    from the client would let a caller forge the audit trail or skip review.
    """
    applicant_id: str = Field(min_length=1, max_length=64)
    decision: Literal["approve", "decline"]
    note: str = Field(default="", max_length=2000)
    threshold: float = Field(default=DEFAULT_THRESHOLD, ge=1, le=90)
    # The applicant's features, so the server can score them authoritatively.
    applicant: Applicant | None = None


@app.post("/api/decisions")
def create_decision(req: ActionRequest, user: dict = Depends(auth.current_user)):
    """Record an officer's decision. This is the system-of-record write."""
    # --- authoritative risk: never taken from the caller -------------------- #
    if req.applicant is not None:
        scored = _score_frame(pd.DataFrame([req.applicant.model_dump()]))[0]
    else:
        # Fall back to the cached demo batch when only an id is supplied.
        scored = next((a for a in _demo_scored(250)
                       if a["id"] == req.applicant_id), None)
        if scored is None:
            raise HTTPException(
                status_code=422,
                detail="Unknown applicant — send the applicant's details so the "
                       "decision can be scored.")

    risk = scored["risk"]
    model_recommends = "approve" if risk < req.threshold else "decline"
    override = req.decision != model_recommends

    # Maker-checker: an analyst overriding the model needs manager sign-off.
    # A manager's own decision is final immediately.
    actor_role = user.get("role", "analyst")
    needs_review = override and actor_role != "manager"
    status = "pending_review" if needs_review else "final"

    row = db.record_action(
        applicant_id=req.applicant_id,
        decision=req.decision,
        note=req.note,
        actor=user.get("name") or user.get("email"),
        actor_role=actor_role,
        status=status,
        risk=risk,
        risk_traditional=scored["risk_traditional"],
        category=scored["category"],
        threshold=req.threshold,
        shap=scored.get("shap", {}),
        model_version=_artifacts()["alt"][1],
        flipped=override,
    )
    if row is None:
        raise HTTPException(status_code=500, detail="Could not record decision.")

    logger.info("%s (%s) recorded %s for %s%s%s",
                user.get("email"), actor_role, req.decision, req.applicant_id,
                " [OVERRIDE]" if override else "",
                " -> pending manager review" if needs_review else "")
    return {"recorded": row, "override": override, "needs_review": needs_review,
            "model_recommended": model_recommends}


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=200)
    name: str = Field(default="", max_length=120)
    # No role field on purpose: a signer-off must be appointed, not self-declared.


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)


@app.post("/api/auth/register")
def register(req: RegisterRequest):
    """
    Create an account. Email must be unique; password is stored hashed.

    Everyone signs up as an analyst. Manager (override sign-off) authority is
    granted by an existing manager via /api/users/role — otherwise maker-checker
    would be defeated by simply ticking a box at sign-up. The very first account
    is a manager so the instance has someone who can appoint the rest.
    """
    if "@" not in req.email:
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    role = "manager" if db.user_count() == 0 else "analyst"
    user = db.create_user(req.email, req.password, name=req.name, role=role)
    if user is None:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    return {"user": user, "token": auth.issue_token(user)}


@app.post("/api/auth/login")
def login(req: LoginRequest):
    """Verify credentials and return the user profile plus a session token."""
    user = db.authenticate(req.email, req.password)
    if user is None:
        logger.warning("Failed sign-in for %s", req.email)
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    return {"user": user, "token": auth.issue_token(user)}


@app.get("/api/auth/me")
def me(user: dict = Depends(auth.current_user)):
    """Who the current token belongs to — used to restore a session."""
    return {"user": {"email": user["email"], "name": user["name"], "role": user["role"]}}


class RoleRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: Literal["analyst", "manager"]


@app.get("/api/users")
def users(user: dict = Depends(auth.current_user)):
    """Team roster. Managers only — it lists who can sign off overrides."""
    auth.require_manager(user)
    return {"users": [{"email": u["email"], "name": u["name"], "role": u["role"]}
                      for u in db.list_users()]}


@app.post("/api/users/role")
def set_user_role(req: RoleRequest, user: dict = Depends(auth.current_user)):
    """Appoint or stand down a manager. Managers only."""
    auth.require_manager(user)
    if req.email.strip().lower() == user["email"] and req.role != "manager":
        raise HTTPException(
            status_code=400,
            detail="You cannot remove your own manager access — ask another manager.")
    updated = db.set_role(req.email, req.role)
    if updated is None:
        raise HTTPException(status_code=404, detail="No account with that email.")
    return {"user": {"email": updated["email"], "name": updated["name"],
                     "role": updated["role"]}}


@app.get("/api/notices/{decision_id}")
def notice(decision_id: int, user: dict = Depends(auth.current_user)):
    """
    Adverse-action notice for a declined application (ECOA / Reg B).

    Only issued for declines — an approval has no adverse reasons to state.
    """
    decision = db.get_decision(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found.")
    if decision["decision"] != "decline":
        raise HTTPException(
            status_code=400,
            detail="An adverse-action notice applies only to declined applications.")
    return {"notice": notices.build_notice(decision)}


@app.get("/api/reviews")
def reviews(user: dict = Depends(auth.current_user)):
    """Overrides awaiting manager sign-off."""
    return {"pending": db.pending_reviews()}


class ReviewRequest(BaseModel):
    """Reviewer identity comes from the session token, not this body."""
    approve: bool
    note: str = Field(default="", max_length=2000)


@app.post("/api/reviews/{decision_id}")
def review(decision_id: int, req: ReviewRequest,
           user: dict = Depends(auth.current_user)):
    """Manager approves or refuses an analyst's override."""
    auth.require_manager(user)
    reviewer = user.get("name") or user.get("email")

    pending = db.get_decision(decision_id)
    if pending is None or pending["status"] != "pending_review":
        raise HTTPException(
            status_code=404,
            detail="Decision not found, or it is not awaiting review.")

    # Four-eyes: the person who made the decision cannot approve it.
    if pending["actor"] == reviewer:
        raise HTTPException(
            status_code=403,
            detail="You cannot sign off your own override — another manager must review it.")

    row = db.review_decision(decision_id, approve=req.approve,
                             reviewer=reviewer, note=req.note)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Decision not found, or it is not awaiting review.")
    logger.info("Manager %s %s override on %s",
                reviewer, "approved" if req.approve else "rejected",
                row["applicant_id"])
    return {"reviewed": row}
