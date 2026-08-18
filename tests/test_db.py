"""Tests for the decision audit trail."""
import db


def _rec(applicant_id, risk, risk_trad):
    return {
        "id": applicant_id,
        "risk": risk,
        "risk_traditional": risk_trad,
        "category": "Low" if risk < 15 else "Medium" if risk < 40 else "High",
        "shap": {"credit_score": -5.0, "income": -2.0},
    }


def test_init_db_is_idempotent():
    db.init_db()
    db.init_db()  # must not raise on an existing schema


def test_log_and_read_back():
    db.init_db()
    written = db.log_decisions([_rec("T-LOG-1", 6.0, 16.0)], threshold=25, source="test")
    assert written == 1

    rows = db.recent_decisions(limit=50, applicant_id="T-LOG-1")
    assert len(rows) >= 1
    row = rows[0]
    assert row["decision"] == "approve"        # 6% < 25% threshold
    assert row["category"] == "Low"
    assert row["shap"]["credit_score"] == -5.0
    assert row["created_at"] is not None


def test_decline_and_flip_detection():
    db.init_db()
    # Traditional would decline (36 >= 25), behavioral approves (19 < 25) -> flip.
    db.log_decisions([_rec("T-FLIP-1", 19.0, 36.0)], threshold=25, source="test")
    row = db.recent_decisions(limit=10, applicant_id="T-FLIP-1")[0]
    assert row["decision"] == "approve"
    assert row["flipped"] is True

    # Both decline -> no flip.
    db.log_decisions([_rec("T-FLIP-2", 80.0, 90.0)], threshold=25, source="test")
    row2 = db.recent_decisions(limit=10, applicant_id="T-FLIP-2")[0]
    assert row2["decision"] == "decline"
    assert row2["flipped"] is False


def test_stats_are_consistent():
    db.init_db()
    stats = db.decision_stats()
    assert stats["total"] == stats["approved"] + stats["declined"]
    assert stats["flips"] <= stats["total"]


def test_log_failure_is_non_fatal():
    """A malformed record must not raise — scoring should never break on audit."""
    assert db.log_decisions([{"id": "bad"}], threshold=25) == 0
