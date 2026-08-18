"""Integration tests for the FastAPI backend (auth + hardening)."""
import io

from fastapi.testclient import TestClient

import auth
import server

client = TestClient(server.app)

# --- identities ------------------------------------------------------------ #
# Identity and authority come from a signed token, never from the request body,
# so tests mint tokens the same way the login endpoint does.
def _hdr(name, role="analyst", email=None):
    token = auth.issue_token(
        {"id": 1, "email": email or f"{name}@bank.test", "name": name, "role": role})
    return {"Authorization": f"Bearer {token}"}


ANALYST = _hdr("a.jones")
MANAGER = _hdr("m.patel", role="manager")

# Scores under the production models: LOW -> 6.0%, HIGH -> ~100%.
LOW = {
    "id": "T-1", "credit_score": 780, "income": 80000, "existing_debt": 14000,
    "loan_amount": 28000, "payment_consistency_pct": 79,
    "income_volatility_score": 12, "debt_trend": 0.1,
}
HIGH = {
    "id": "T-2", "credit_score": 520, "income": 26000, "existing_debt": 21000,
    "loan_amount": 30000, "payment_consistency_pct": 34,
    "income_volatility_score": 78, "debt_trend": 0.8,
}
VALID = LOW

REQUIRED = [
    "credit_score", "income", "existing_debt", "loan_amount",
    "payment_consistency_pct", "income_volatility_score", "debt_trend",
]


# --- auth ------------------------------------------------------------------ #
def test_health_is_public():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_data_endpoints_require_a_token():
    for path in ("/api/applicants", "/api/metrics", "/api/meta",
                 "/api/decisions", "/api/actions", "/api/reviews"):
        assert client.get(path).status_code == 401, path
    assert client.post("/api/score", json={"applicants": [LOW]}).status_code == 401


def test_forged_token_rejected():
    body, _sig = auth.issue_token(
        {"id": 1, "email": "x@y.z", "name": "x", "role": "manager"}).split(".")
    bad = f"{body}.{'0' * 64}"
    r = client.get("/api/metrics", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401


def test_expired_token_rejected(monkeypatch):
    monkeypatch.setattr(auth, "TOKEN_TTL_SECONDS", -1)
    stale = _hdr("ghost")
    assert client.get("/api/metrics", headers=stale).status_code == 401


def test_register_then_login_returns_token():
    body = {"email": "new.user@bank.test", "password": "correct horse 42",
            "name": "New User"}
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 200
    assert r.json()["token"]

    r = client.post("/api/auth/login",
                    json={"email": body["email"], "password": body["password"]})
    assert r.status_code == 200
    token = r.json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["user"]["email"] == body["email"]


def test_manager_role_cannot_be_self_assigned():
    r = client.post("/api/auth/register", json={
        "email": "climber@bank.test", "password": "correct horse 42",
        "name": "Climber", "role": "manager"})
    assert r.status_code == 200
    # The extra field is ignored; only the bootstrap first account is a manager.
    assert r.json()["user"]["role"] == "analyst"


def test_only_a_manager_can_grant_roles():
    email = "promote.me@bank.test"
    client.post("/api/auth/register",
                json={"email": email, "password": "correct horse 42", "name": "P"})
    assert client.post("/api/users/role", json={"email": email, "role": "manager"},
                       headers=ANALYST).status_code == 403
    r = client.post("/api/users/role", json={"email": email, "role": "manager"},
                    headers=MANAGER)
    assert r.status_code == 200 and r.json()["user"]["role"] == "manager"


# --- scoring --------------------------------------------------------------- #
def test_metrics_returns_rows():
    r = client.get("/api/metrics", headers=ANALYST)
    assert r.status_code == 200
    assert len(r.json()) == 6


def test_score_happy_path():
    r = client.post("/api/score", json={"applicants": [LOW]}, headers=ANALYST)
    assert r.status_code == 200
    a = r.json()["applicants"][0]
    assert 0 <= a["risk"] <= 100
    assert a["category"] in {"Low", "Medium", "High"}
    assert set(a["shap"]) == set(REQUIRED)


def test_score_rejects_out_of_range():
    bad = {**LOW, "credit_score": 9999}
    r = client.post("/api/score", json={"applicants": [bad]}, headers=ANALYST)
    assert r.status_code == 422


def test_score_rejects_empty_batch():
    r = client.post("/api/score", json={"applicants": []}, headers=ANALYST)
    assert r.status_code == 422


def _csv(rows):
    header = ",".join(["id"] + REQUIRED)
    lines = [header] + [",".join(str(r[c]) for c in ["id"] + REQUIRED) for r in rows]
    return "\n".join(lines).encode()


def _upload(payload, name="a.csv", mime="text/csv"):
    return client.post("/api/score-csv", headers=ANALYST,
                       files={"file": (name, io.BytesIO(payload), mime)})


def test_score_csv_happy_path():
    r = _upload(_csv([LOW]))
    assert r.status_code == 200
    assert r.json()["applicants"][0]["category"] in {"Low", "Medium", "High"}


def test_score_csv_missing_columns_422():
    assert _upload(b"income,credit_score\n80000,780\n", "bad.csv").status_code == 422


def test_score_csv_oversized_413(monkeypatch):
    monkeypatch.setattr(server, "MAX_UPLOAD_BYTES", 50)
    assert _upload(_csv([LOW, LOW, LOW]), "big.csv").status_code == 413


def test_score_csv_rejects_non_csv_415():
    assert _upload(b"\x89PNG", "x.png", "image/png").status_code == 415


def test_score_csv_unreadable_400():
    assert _upload(b"\x00\x01\x02notacsv", "junk.csv").status_code in (400, 422)


def test_score_csv_all_missing_values_422():
    body = ("id," + ",".join(REQUIRED) + "\nX," + ",".join([""] * len(REQUIRED)) + "\n")
    assert _upload(body.encode(), "empty.csv").status_code == 422


def test_secure_headers_present():
    r = client.get("/api/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"


def test_api_key_enforced_when_set(monkeypatch):
    monkeypatch.setattr(server, "API_KEY", "secret")
    r = client.post("/api/score", json={"applicants": [LOW]}, headers=ANALYST)
    assert r.status_code == 401
    r = client.post("/api/score", json={"applicants": [LOW]},
                    headers={**ANALYST, "X-API-Key": "secret"})
    assert r.status_code == 200


# --- decisions ------------------------------------------------------------- #
def _decide(applicant_id, decision, features, headers, note=""):
    return client.post("/api/decisions", headers=headers, json={
        "applicant_id": applicant_id, "decision": decision, "note": note,
        "threshold": 25, "applicant": {**features, "id": applicant_id}})


def test_record_decision_and_audit_trail():
    r = _decide("T-API-1", "approve", LOW, ANALYST, note="Verified income.")
    assert r.status_code == 200
    out = r.json()
    assert out["override"] is False              # model also recommended approve
    assert out["recorded"]["note"] == "Verified income."

    log = client.get("/api/decisions?applicant_id=T-API-1", headers=ANALYST).json()
    assert len(log["decisions"]) >= 1
    assert log["decisions"][0]["actor"] == "a.jones"   # from the token, not the body


def test_risk_is_recomputed_not_taken_from_the_client():
    """A caller claiming a 1% risk on a ~100%-risk applicant must not be believed."""
    r = client.post("/api/decisions", headers=ANALYST, json={
        "applicant_id": "T-FORGE", "decision": "approve", "threshold": 25,
        "risk": 1.0, "actor": "ceo", "actor_role": "manager",   # all ignored
        "applicant": {**HIGH, "id": "T-FORGE"}})
    assert r.status_code == 200
    out = r.json()
    assert out["recorded"]["risk"] > 90
    assert out["recorded"]["actor"] == "a.jones"
    assert out["override"] is True
    assert out["recorded"]["status"] == "pending_review"


def test_unknown_applicant_without_features_422():
    r = client.post("/api/decisions", headers=ANALYST, json={
        "applicant_id": "NOPE-999", "decision": "approve"})
    assert r.status_code == 422


def test_invalid_decision_rejected():
    r = client.post("/api/decisions", headers=ANALYST,
                    json={"applicant_id": "X", "decision": "maybe"})
    assert r.status_code == 422


def test_actions_endpoint_returns_latest_per_applicant():
    _decide("T-API-3", "decline", HIGH, ANALYST)
    actions = client.get("/api/actions", headers=ANALYST).json()["actions"]
    assert actions["T-API-3"]["decision"] == "decline"


# --- maker-checker --------------------------------------------------------- #
def test_analyst_override_requires_manager_signoff():
    r = _decide("T-MC-1", "approve", HIGH, ANALYST)
    assert r.json()["needs_review"] is True
    assert r.json()["recorded"]["status"] == "pending_review"

    pending = client.get("/api/reviews", headers=MANAGER).json()["pending"]
    assert "T-MC-1" in [p["applicant_id"] for p in pending]


def test_manager_decision_is_final_without_review():
    r = _decide("T-MC-2", "approve", HIGH, MANAGER)
    assert r.json()["needs_review"] is False
    assert r.json()["recorded"]["status"] == "final"


def test_in_policy_decision_needs_no_review():
    r = _decide("T-MC-3", "decline", HIGH, ANALYST)
    assert r.json()["needs_review"] is False
    assert r.json()["recorded"]["status"] == "final"


def test_manager_signoff_finalises_override():
    did = _decide("T-MC-4", "approve", HIGH, ANALYST).json()["recorded"]["id"]
    rv = client.post(f"/api/reviews/{did}", headers=MANAGER,
                     json={"approve": True, "note": "Verified."})
    assert rv.status_code == 200
    assert rv.json()["reviewed"]["status"] == "final"
    assert rv.json()["reviewed"]["reviewed_by"] == "m.patel"

    # Already reviewed -> cannot be reviewed again.
    assert client.post(f"/api/reviews/{did}", headers=MANAGER,
                       json={"approve": False}).status_code == 404


def test_manager_can_reject_override():
    did = _decide("T-MC-5", "approve", HIGH, ANALYST).json()["recorded"]["id"]
    rv = client.post(f"/api/reviews/{did}", headers=MANAGER, json={"approve": False})
    assert rv.json()["reviewed"]["status"] == "rejected"


def test_analyst_cannot_sign_off_a_review():
    did = _decide("T-MC-6", "approve", HIGH, ANALYST).json()["recorded"]["id"]
    rv = client.post(f"/api/reviews/{did}", headers=ANALYST, json={"approve": True})
    assert rv.status_code == 403


def test_maker_cannot_review_their_own_override():
    """Four eyes: even a manager may not sign off a decision they made."""
    did = _decide("T-MC-7", "approve", HIGH, ANALYST).json()["recorded"]["id"]
    same_person_promoted = _hdr("a.jones", role="manager")
    rv = client.post(f"/api/reviews/{did}", headers=same_person_promoted,
                     json={"approve": True})
    assert rv.status_code == 403


def test_review_unknown_decision_404():
    assert client.post("/api/reviews/99999999", headers=MANAGER,
                       json={"approve": True}).status_code == 404


# --- adverse-action notices ------------------------------------------------ #
def _make_decline(applicant_id="T-AA-1"):
    return _decide(applicant_id, "decline", HIGH, ANALYST).json()["recorded"]["id"]


def test_notice_lists_only_adverse_reasons_worst_first():
    n = client.get(f"/api/notices/{_make_decline()}",
                   headers=ANALYST).json()["notice"]
    reasons = n["principal_reasons"]
    assert len(reasons) == 4                           # Reg B convention: up to four
    assert all(r["impact_pct"] > 0 for r in reasons)   # helpful factors excluded
    impacts = [r["impact_pct"] for r in reasons]
    assert impacts == sorted(impacts, reverse=True)    # worst first
    assert reasons[0]["code"] == "payment_consistency_pct"
    assert reasons[0]["what_you_can_do"]               # actionable remedy present


def test_notice_includes_required_disclosures():
    n = client.get(f"/api/notices/{_make_decline('T-AA-2')}",
                   headers=ANALYST).json()["notice"]
    assert n["action_taken"] == "Credit application declined"
    assert n["score_disclosure"]["used"] is True
    assert n["score_disclosure"]["risk_score_pct"] > 90
    assert "Equal Credit Opportunity Act" in n["ecoa_notice"]
    assert n["appeal_rights"]
    assert "PROTOTYPE" in n["disclaimer"]


def test_no_notice_for_approved_application():
    did = _decide("T-AA-3", "approve", LOW, ANALYST).json()["recorded"]["id"]
    assert client.get(f"/api/notices/{did}", headers=ANALYST).status_code == 400


def test_notice_unknown_decision_404():
    assert client.get("/api/notices/99999999", headers=ANALYST).status_code == 404


def test_rate_limit_429(monkeypatch):
    monkeypatch.setattr(server, "RATE_LIMIT", 3)
    server._hits.clear()
    codes = [client.get("/api/health").status_code for _ in range(5)]
    assert 429 in codes


def test_meta_shape():
    r = client.get("/api/meta", headers=ANALYST)
    assert r.status_code == 200
    body = r.json()
    assert "base_risk" in body and len(body["features"]) == 7
    assert set(body["best"]) == {"traditional", "alternative"}
