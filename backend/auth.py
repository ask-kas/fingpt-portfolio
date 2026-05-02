"""
auth.py — HMAC-signed session tokens and request authentication.

Token format:  base64url(payload).base64url(signature)
  payload    = "{user_id}|{expiry_unix_ts}"
  signature  = HMAC-SHA256(payload, SESSION_SECRET)

Tokens are stateless (no DB lookup), expire after SESSION_TTL_HOURS,
and are verified with constant-time comparison to defeat timing attacks.

Used by the verify_session() FastAPI dependency to close the IDOR gap
across all /api/db/* user-scoped endpoints.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

logger = logging.getLogger("veris.auth")

SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "24"))
_SECRET: bytes | None = None


def _secret() -> bytes:
    """Lazily load (or generate) the session secret."""
    global _SECRET
    if _SECRET is not None:
        return _SECRET
    raw = os.getenv("SESSION_SECRET", "").strip()
    if not raw:
        # Auto-generate so dev never fails, but warn the operator.
        raw = secrets.token_urlsafe(48)
        logger.warning(
            "SESSION_SECRET not set in env — generated an ephemeral one. "
            "Sessions will invalidate on restart. Set SESSION_SECRET in config/.env "
            "for persistent sessions."
        )
    _SECRET = raw.encode()
    return _SECRET


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def issue_token(user_id: str) -> str:
    """Create a signed token for the given user."""
    if not user_id:
        raise ValueError("user_id required")
    expiry = int(time.time()) + SESSION_TTL_HOURS * 3600
    payload = f"{user_id}|{expiry}".encode()
    sig = hmac.new(_secret(), payload, hashlib.sha256).digest()
    return f"{_b64(payload)}.{_b64(sig)}"


def _decode(token: str) -> str | None:
    """Verify a token and return the user_id, or None if invalid/expired."""
    try:
        payload_b64, sig_b64 = token.split(".", 1)
    except ValueError:
        return None
    try:
        payload = _b64decode(payload_b64)
        sig = _b64decode(sig_b64)
    except Exception:
        return None

    expected = hmac.new(_secret(), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return None

    try:
        user_id, expiry_str = payload.decode().split("|", 1)
        expiry = int(expiry_str)
    except (ValueError, UnicodeDecodeError):
        return None
    if time.time() > expiry:
        return None
    return user_id


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    # Allow ?token= as a fallback for browser links / WebSocket upgrades
    return request.query_params.get("token")


async def verify_session(request: Request) -> str:
    """FastAPI dependency: returns the authenticated user_id, or 401s."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(401, "Missing session token")
    user_id = _decode(token)
    if not user_id:
        raise HTTPException(401, "Invalid or expired session token")
    return user_id


async def verify_session_matches(request: Request, user_id: str) -> str:
    """Verify caller is authenticated AND owns the resource for path user_id."""
    auth_user = await verify_session(request)
    if auth_user != user_id:
        raise HTTPException(403, "Cannot access another user's resources")
    return auth_user


# ── Simple in-memory rate limiter (per-IP) ──────────────────────
# For production, replace with Redis-backed slowapi or nginx rate limiting.
_RATE_BUCKETS: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request, key: str, max_calls: int, window_seconds: int) -> None:
    """Raise 429 if (ip, key) exceeded max_calls in the rolling window."""
    ip = (request.client.host if request.client else "unknown") + ":" + key
    now = time.time()
    bucket = _RATE_BUCKETS[ip]
    while bucket and bucket[0] < now - window_seconds:
        bucket.popleft()
    if len(bucket) >= max_calls:
        raise HTTPException(429, "Too many requests — slow down and try again shortly.")
    bucket.append(now)
