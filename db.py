"""
Persistence layer — decision audit trail.

Every scored applicant is recorded so a decision can be reproduced later:
what the models predicted, which threshold was in force, what the resulting
approve/decline call was, and the SHAP contributions that explain it.

Storage is chosen by `CR_DATABASE_URL`:
  - default  sqlite:///<repo>/data/decisions.db   (zero-config, local/dev)
  - prod     postgresql+psycopg://user:pass@host/db

Failures here must never break scoring — callers log and continue.
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timezone

from sqlalchemy import (
    Float, Integer, String, Text, create_engine, desc, func, select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

logger = logging.getLogger("credit_risk.db")

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_URL = f"sqlite:///{os.path.join(HERE, 'data', 'decisions.db')}"
DATABASE_URL = os.getenv("CR_DATABASE_URL", DEFAULT_URL)

# check_same_thread is a SQLite-only concern (FastAPI serves across threads).
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)


class Base(DeclarativeBase):
    pass


class Decision(Base):
    """One scoring decision for one applicant, at one point in time."""

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    applicant_id: Mapped[str] = mapped_column(String(64), index=True)

    risk: Mapped[float] = mapped_column(Float)              # behavioral model, %
    risk_traditional: Mapped[float] = mapped_column(Float)  # traditional model, %
    category: Mapped[str] = mapped_column(String(16))       # Low / Medium / High

    threshold: Mapped[float] = mapped_column(Float)         # approve-below %, at decision time
    decision: Mapped[str] = mapped_column(String(16))       # approve / decline
    flipped: Mapped[int] = mapped_column(Integer, default=0)  # behavioral changed the call

    model_version: Mapped[str] = mapped_column(String(64), default="")
    source: Mapped[str] = mapped_column(String(16), default="api")  # api / csv / demo
    actor: Mapped[str] = mapped_column(String(64), default="system")

    shap_json: Mapped[str] = mapped_column(Text, default="{}")
    note: Mapped[str] = mapped_column(Text, default="")  # officer's rationale
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    # --- maker-checker ---------------------------------------------------- #
    # final          : within policy, effective immediately
    # pending_review : an override, awaiting manager sign-off
    # rejected       : manager refused the override
    status: Mapped[str] = mapped_column(String(20), default="final")
    actor_role: Mapped[str] = mapped_column(String(20), default="analyst")
    reviewed_by: Mapped[str] = mapped_column(String(64), default="")
    review_note: Mapped[str] = mapped_column(Text, default="")

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "applicant_id": self.applicant_id,
            "risk": self.risk,
            "risk_traditional": self.risk_traditional,
            "category": self.category,
            "threshold": self.threshold,
            "decision": self.decision,
            "flipped": bool(self.flipped),
            "model_version": self.model_version,
            "source": self.source,
            "actor": self.actor,
            "shap": json.loads(self.shap_json or "{}"),
            "note": self.note or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "status": self.status or "final",
            "actor_role": self.actor_role or "analyst",
            "reviewed_by": self.reviewed_by or "",
            "review_note": self.review_note or "",
        }


class User(Base):
    """A person who signs in to the console."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    role: Mapped[str] = mapped_column(String(20), default="analyst")  # analyst | manager
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict:
        """Public shape — never exposes the password hash."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# --- password hashing (PBKDF2-HMAC-SHA256, stdlib) ------------------------- #
_PBKDF2_ROUNDS = 240_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt, expected = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                 bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(dk.hex(), expected)   # constant-time
    except Exception:
        return False


def create_user(email, password, name="", role="analyst") -> dict | None:
    """Register a new user. Returns None if the email is already taken."""
    email = (email or "").strip().lower()
    try:
        with Session(engine) as s:
            if s.scalar(select(User).where(User.email == email)):
                return None
            u = User(email=email, name=name or email.split("@")[0].title(),
                     role=role, password_hash=hash_password(password))
            s.add(u)
            s.commit()
            s.refresh(u)
            logger.info("Registered user %s (%s)", email, role)
            return u.as_dict()
    except Exception:
        logger.exception("Failed to create user %s", email)
        return None


def user_count() -> int:
    """How many accounts exist. Used to bootstrap the first manager."""
    with Session(engine) as s:
        return int(s.scalar(select(func.count()).select_from(User)) or 0)


def list_users() -> list[dict]:
    with Session(engine) as s:
        return [u.as_dict() for u in s.scalars(select(User).order_by(User.created_at))]


def set_role(email: str, role: str) -> dict | None:
    """Promote/demote an account. Only a manager may call this (enforced in the API)."""
    email = (email or "").strip().lower()
    with Session(engine) as s:
        u = s.scalar(select(User).where(User.email == email))
        if u is None:
            return None
        u.role = role
        s.commit()
        logger.info("Role for %s set to %s", email, role)
        return u.as_dict()


def authenticate(email, password) -> dict | None:
    """Return the user if the credentials are valid, else None."""
    email = (email or "").strip().lower()
    try:
        with Session(engine) as s:
            u = s.scalar(select(User).where(User.email == email))
            if u and verify_password(password, u.password_hash):
                return u.as_dict()
            return None
    except Exception:
        logger.exception("Authentication failed for %s", email)
        return None


def init_db() -> None:
    """Create tables if they don't exist, and apply small forward migrations."""
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    Base.metadata.create_all(engine)
    _ensure_column("decisions", "note", "TEXT DEFAULT ''")
    _ensure_column("decisions", "status", "VARCHAR(20) DEFAULT 'final'")
    _ensure_column("decisions", "actor_role", "VARCHAR(20) DEFAULT 'analyst'")
    _ensure_column("decisions", "reviewed_by", "VARCHAR(64) DEFAULT ''")
    _ensure_column("decisions", "review_note", "TEXT DEFAULT ''")
    logger.info("Decision store ready (%s)", engine.url.render_as_string(hide_password=True))


def _ensure_column(table: str, column: str, ddl_type: str) -> None:
    """Add a column to an existing table if it's missing (idempotent)."""
    from sqlalchemy import inspect, text
    try:
        cols = {c["name"] for c in inspect(engine).get_columns(table)}
        if column in cols:
            return
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
        logger.info("Migrated %s: added column %r", table, column)
    except Exception:
        logger.exception("Could not ensure column %s.%s", table, column)


def record_action(*, applicant_id, decision, note="", actor="system",
                  risk=0.0, risk_traditional=0.0, category="", threshold=0.0,
                  shap=None, model_version="", flipped=False,
                  actor_role="analyst", status="final") -> dict | None:
    """
    Persist an officer's explicit decision (approve / decline / override).

    This is the human counterpart to `log_decisions`, which records automated
    scoring. Returns the stored row, or None if the write failed.
    """
    try:
        row = Decision(
            status=status,
            actor_role=actor_role,
            applicant_id=str(applicant_id),
            risk=float(risk),
            risk_traditional=float(risk_traditional),
            category=category or "",
            threshold=float(threshold),
            decision=decision,
            flipped=int(bool(flipped)),
            model_version=model_version,
            source="officer",
            actor=actor or "system",
            shap_json=json.dumps(shap or {}),
            note=note or "",
        )
        with Session(engine) as s:
            s.add(row)
            s.commit()
            s.refresh(row)
            return row.as_dict()
    except Exception:
        logger.exception("Failed to record officer decision")
        return None


def pending_reviews(limit=200) -> list[dict]:
    """Overrides awaiting manager sign-off, oldest first (FIFO queue)."""
    try:
        stmt = (select(Decision)
                .where(Decision.status == "pending_review")
                .order_by(Decision.created_at, Decision.id)
                .limit(limit))
        with Session(engine) as s:
            return [d.as_dict() for d in s.scalars(stmt)]
    except Exception:
        logger.exception("Failed to read pending reviews")
        return []


def review_decision(decision_id, *, approve, reviewer, note="") -> dict | None:
    """
    Manager signs off (or refuses) an override.

    Approving makes the analyst's decision effective; refusing marks it
    rejected so the model's original recommendation stands.
    """
    try:
        with Session(engine) as s:
            row = s.get(Decision, decision_id)
            if row is None:
                return None
            if row.status != "pending_review":
                logger.warning("Decision %s is not pending review (status=%s)",
                               decision_id, row.status)
                return None
            row.status = "final" if approve else "rejected"
            row.reviewed_by = reviewer or "manager"
            row.review_note = note or ""
            s.commit()
            s.refresh(row)
            return row.as_dict()
    except Exception:
        logger.exception("Failed to review decision %s", decision_id)
        return None


def get_decision(decision_id) -> dict | None:
    """Fetch a single decision by id."""
    try:
        with Session(engine) as s:
            row = s.get(Decision, decision_id)
            return row.as_dict() if row else None
    except Exception:
        logger.exception("Failed to read decision %s", decision_id)
        return None


def latest_actions(applicant_ids=None) -> dict[str, dict]:
    """
    Most recent *officer* decision per applicant, keyed by applicant id.
    Used to show recorded status alongside model recommendations.
    """
    try:
        stmt = (select(Decision)
                .where(Decision.source == "officer")
                .order_by(desc(Decision.created_at), desc(Decision.id)))
        if applicant_ids:
            stmt = stmt.where(Decision.applicant_id.in_(list(applicant_ids)))
        out: dict[str, dict] = {}
        with Session(engine) as s:
            for d in s.scalars(stmt):
                out.setdefault(d.applicant_id, d.as_dict())
        return out
    except Exception:
        logger.exception("Failed to read officer decisions")
        return {}


def log_decisions(records, threshold, *, source="api", actor="system",
                  model_version="") -> int:
    """
    Persist scored applicants as audit rows. Returns the number written.

    `records` are the front-end-shaped dicts produced by the scoring path.
    Never raises — a failed write must not fail a scoring request.
    """
    try:
        rows = []
        for r in records:
            approve = r["risk"] < threshold
            trad_approve = r["risk_traditional"] < threshold
            rows.append(Decision(
                applicant_id=str(r.get("id", "")),
                risk=float(r["risk"]),
                risk_traditional=float(r["risk_traditional"]),
                category=r["category"],
                threshold=float(threshold),
                decision="approve" if approve else "decline",
                flipped=int(approve != trad_approve),
                model_version=model_version,
                source=source,
                actor=actor,
                shap_json=json.dumps(r.get("shap", {})),
            ))
        with Session(engine) as s:
            s.add_all(rows)
            s.commit()
        return len(rows)
    except Exception:
        logger.exception("Failed to write decision audit rows")
        return 0


def recent_decisions(limit=100, applicant_id=None) -> list[dict]:
    """Most recent decisions, newest first; optionally for one applicant."""
    try:
        stmt = select(Decision).order_by(desc(Decision.created_at), desc(Decision.id))
        if applicant_id:
            stmt = stmt.where(Decision.applicant_id == applicant_id)
        with Session(engine) as s:
            return [d.as_dict() for d in s.scalars(stmt.limit(limit))]
    except Exception:
        logger.exception("Failed to read decision audit rows")
        return []


def decision_stats() -> dict:
    """Aggregate counts for the audit dashboard."""
    try:
        with Session(engine) as s:
            rows = s.scalars(select(Decision)).all()
            total = len(rows)
            approved = sum(1 for r in rows if r.decision == "approve")
            flips = sum(1 for r in rows if r.flipped)
            return {
                "total": total,
                "approved": approved,
                "declined": total - approved,
                "flips": flips,
            }
    except Exception:
        logger.exception("Failed to aggregate decision stats")
        return {"total": 0, "approved": 0, "declined": 0, "flips": 0}
