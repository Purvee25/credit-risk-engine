"""
Session authentication.

Identity and authority must come from a token the server signed — never from
the request body. Before this module, a caller could simply claim
`actor_role: "manager"` and bypass maker-checker.

Tokens are HMAC-SHA256 signed (stdlib, no dependency): base64(payload).signature
Set CR_SECRET_KEY in any real deployment; otherwise a random per-process key is
generated, which invalidates sessions on restart.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time

from fastapi import Header, HTTPException

logger = logging.getLogger("credit_risk.auth")

SECRET = os.getenv("CR_SECRET_KEY")
if not SECRET:
    SECRET = secrets.token_hex(32)
    logger.warning(
        "CR_SECRET_KEY is not set — using an ephemeral key. "
        "Sessions will not survive a restart. Set it in production.")

TOKEN_TTL_SECONDS = int(os.getenv("CR_TOKEN_TTL", 8 * 3600))  # a working day


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_token(user: dict) -> str:
    """Mint a signed session token for an authenticated user."""
    payload = {
        "uid": user["id"],
        "email": user["email"],
        "name": user.get("name", ""),
        "role": user.get("role", "analyst"),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_token(token: str) -> dict | None:
    """Return the payload if the signature is valid and unexpired, else None."""
    try:
        body, sig = token.split(".")
        expected = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):      # constant-time
            return None
        payload = json.loads(_b64d(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def _extract(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()


def current_user(authorization: str | None = Header(default=None)) -> dict:
    """
    FastAPI dependency: the authenticated user, or 401.

    Everything downstream must take identity and role from *this*, never from
    the request body.
    """
    payload = verify_token(_extract(authorization) or "")
    if payload is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return payload


def require_manager(user: dict) -> None:
    """Guard actions only a manager may perform."""
    if user.get("role") != "manager":
        raise HTTPException(
            status_code=403,
            detail="Only a manager can sign off an override.")
