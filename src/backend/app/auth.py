"""Minimal drug-owner authentication.

Hackathon-scale, but real enforcement: a username/password login issues a
signed token that embeds the user's owned `protocol_id`s, a FastAPI
dependency verifies it on every request, and `require_protocol_access`
403s any request for a protocol_id the caller doesn't own. This replaces
docs/05_api_contracts.md's original "single shared X-API-Key, don't spend
time on real auth" note now that the dashboard serves 10 separate drug
owners who must not see each other's data.

Deliberately stdlib-only (hashlib/hmac, no passlib/python-jose): trying
passlib[bcrypt] here hit a real, current version-skew crash --
passlib 1.7.4's bcrypt backend calls a `bcrypt.__about__` attribute that
bcrypt >= 4.0 removed, so `pip install passlib[bcrypt]` on a fresh
environment today reliably breaks the very first password hash. PBKDF2 via
`hashlib.pbkdf2_hmac` and a plain HMAC-signed token give the same
practical security for a demo without that dependency risk.

Users are seeded in-process (`SEED_USERS`) rather than self-registered --
there's no product requirement for sign-up, just a fixed set of drug-owner
accounts for the demo. All seeded accounts share the password
"changeme123"; this is demo-only and must not be reused for a real
deployment.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass

from fastapi import Header

from .errors import ApiError

# A real deployment must set TOKEN_SECRET; the fallback keeps `uvicorn --reload`
# working out of the box for the demo without a mandatory new env var.
TOKEN_SECRET = os.environ.get("TOKEN_SECRET", "dev-only-insecure-secret-change-me").encode()
TOKEN_TTL_SECONDS = 12 * 60 * 60  # 12h

PBKDF2_ITERATIONS = 200_000
PBKDF2_ALGO = "sha256"

# All 10 protocols from the multi-drug synthetic dataset (see
# src/data/generate_synthetic_data.py DRUG_CONFIGS) -- kept here as the
# single source of truth for which protocol_ids exist, so seeded ownership
# doesn't silently drift from what the generator actually produces.
ALL_PROTOCOL_IDS = [f"TRIAL-2026-ONC-{n:02d}" for n in range(4, 14)]


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(PBKDF2_ALGO, password.encode(), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    candidate = hashlib.pbkdf2_hmac(PBKDF2_ALGO, password.encode(), salt, PBKDF2_ITERATIONS)
    return hmac.compare_digest(candidate.hex(), digest_hex)


_SEED_PASSWORD_HASH = _hash_password("changeme123")


def _seed_users() -> dict[str, dict]:
    users: dict[str, dict] = {}
    for i, protocol_id in enumerate(ALL_PROTOCOL_IDS, start=1):
        username = "owner_" + "".join(protocol_id.split("-")[-2:]).lower()  # e.g. "owner_onc04"
        users[username] = {
            "user_id": f"USR-{i:02d}",
            "password_hash": _SEED_PASSWORD_HASH,
            "protocol_ids": [protocol_id],
        }
    users["owner_portfolio"] = {
        "user_id": "USR-99",
        "password_hash": _SEED_PASSWORD_HASH,
        "protocol_ids": list(ALL_PROTOCOL_IDS),
    }
    return users


# {username: {user_id, password_hash, protocol_ids}}
SEED_USERS: dict[str, dict] = _seed_users()


@dataclass
class User:
    user_id: str
    username: str
    protocol_ids: list[str]


def authenticate(username: str, password: str) -> User | None:
    record = SEED_USERS.get(username)
    if record is None or not _verify_password(password, record["password_hash"]):
        return None
    return User(record["user_id"], username, record["protocol_ids"])


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def create_access_token(user: User) -> str:
    """A minimal signed token: base64url(payload_json) + "." +
    base64url(HMAC-SHA256(payload_json)) -- functionally the same
    tamper-evident, expiring credential a JWT would give, without pulling
    in a JWT library."""
    payload = {
        "sub": user.user_id,
        "username": user.username,
        "protocol_ids": user.protocol_ids,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(TOKEN_SECRET, payload_bytes, hashlib.sha256).digest()
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(signature)}"


def _decode_access_token(token: str) -> dict:
    try:
        payload_b64, signature_b64 = token.split(".", 1)
        payload_bytes = _b64url_decode(payload_b64)
        signature = _b64url_decode(signature_b64)
    except Exception:
        raise ApiError(401, "UNAUTHORIZED", "invalid or expired token")
    expected_signature = hmac.new(TOKEN_SECRET, payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise ApiError(401, "UNAUTHORIZED", "invalid or expired token")
    payload = json.loads(payload_bytes)
    if payload.get("exp", 0) < time.time():
        raise ApiError(401, "UNAUTHORIZED", "invalid or expired token")
    return payload


def get_current_user(authorization: str | None = Header(default=None)) -> User:
    """FastAPI dependency: verify the bearer token, or 401."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, "UNAUTHORIZED", "missing bearer token")
    token = authorization.split(" ", 1)[1]
    payload = _decode_access_token(token)
    return User(payload["sub"], payload["username"], payload["protocol_ids"])


def require_protocol_access(user: User, protocol_id: str) -> None:
    """403 if `user` doesn't own `protocol_id`."""
    if protocol_id not in user.protocol_ids:
        raise ApiError(403, "FORBIDDEN", f"you do not have access to protocol '{protocol_id}'")
