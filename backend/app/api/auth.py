"""Authentication for Industrial_Copilot.

Deliberately small and dependency-free: HMAC-SHA256 signed tokens built with `hmac` +
`hashlib` + `base64`, and PBKDF2-SHA256 password hashes. No new package to install 90 minutes
before a submission, and nothing stored in plaintext.

* Passwords live in `backend/app/data/seed/users.json` as `pbkdf2_sha256` salt + hash.
  The demo passwords themselves are documented in `docs/ai/DEMO.md` and `.env.example`, which is
  the right place for demo credentials — they are not in the frontend and not in the code.
* Tokens carry `sub`, `role`, `iat`, `exp` and are signed with `AUTH_SECRET` from the environment.
  Expiry is 30 minutes.
* Two roles: **owner** may authorise and cancel actions and write Events/Clients; **operator** is
  read-only. The check is enforced server-side, never only in the UI.

Machine-to-machine traffic (n8n → backend) does not use these tokens: it presents a shared secret
header instead, see `service_token_ok()` and `n8n/README.md`.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import pathlib
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])

USERS_PATH = pathlib.Path(__file__).resolve().parents[1] / "data" / "seed" / "users.json"

TOKEN_TTL_SECONDS = 30 * 60          # 30 minutes, as specified
PBKDF2_ROUNDS = 200_000

ROLE_OWNER = "owner"
ROLE_OPERATOR = "operator"


# --------------------------------------------------------------------- config

def auth_secret() -> str:
    """Signing secret. A generated per-process fallback keeps dev working but invalidates
    tokens on restart, which is the safe direction for a missing secret."""
    secret = os.getenv("AUTH_SECRET", "").strip()
    if secret:
        return secret
    global _EPHEMERAL
    try:
        return _EPHEMERAL
    except NameError:
        _EPHEMERAL = base64.urlsafe_b64encode(os.urandom(32)).decode()
        logger.warning("AUTH_SECRET is not set; using a per-process secret. "
                       "Tokens will not survive a restart. Set AUTH_SECRET in .env.")
        return _EPHEMERAL


def service_token() -> str:
    """Shared secret for machine-to-machine callers (n8n → backend)."""
    return os.getenv("N8N_SERVICE_TOKEN", "").strip()


def service_token_ok(provided: Optional[str]) -> bool:
    expected = service_token()
    if not expected:
        # Not configured: allow, so an existing deployment does not break on upgrade. The n8n
        # README tells the operator to set it.
        return True
    return bool(provided) and hmac.compare_digest(provided, expected)


# --------------------------------------------------------------------- passwords

def hash_password(password: str, salt: Optional[bytes] = None) -> Dict[str, str]:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return {"algorithm": "pbkdf2_sha256", "rounds": PBKDF2_ROUNDS,
            "salt": salt.hex(), "hash": digest.hex()}


def verify_password(password: str, record: Dict[str, Any]) -> bool:
    try:
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(record["salt"]),
            int(record.get("rounds", PBKDF2_ROUNDS)))
        return hmac.compare_digest(digest.hex(), record["hash"])
    except Exception:
        return False


_users: Optional[Dict[str, Any]] = None


def users() -> Dict[str, Any]:
    global _users
    if _users is None:
        try:
            _users = {u["username"]: u for u in
                      json.loads(USERS_PATH.read_text(encoding="utf-8"))["users"]}
            logger.info("Loaded %d users from %s", len(_users), USERS_PATH.name)
        except Exception as exc:  # noqa: BLE001
            logger.error("Could not load %s (%s); nobody will be able to log in.", USERS_PATH, exc)
            _users = {}
    return _users


def reset_users_cache() -> None:
    global _users
    _users = None


# --------------------------------------------------------------------- tokens

def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue_token(username: str, role: str, ttl: int = TOKEN_TTL_SECONDS) -> Dict[str, Any]:
    now = int(time.time())
    payload = {"sub": username, "role": role, "iat": now, "exp": now + ttl}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64(hmac.new(auth_secret().encode(), body.encode(), hashlib.sha256).digest())
    return {"token": f"{body}.{signature}", "expires_at": payload["exp"],
            "expires_in": ttl, "username": username, "role": role}


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Verified payload, or ``None`` when the token is malformed, forged or expired."""
    if not token or token.count(".") != 1:
        return None
    body, signature = token.split(".", 1)
    expected = _b64(hmac.new(auth_secret().encode(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_unb64(body))
    except Exception:
        return None
    if int(payload.get("exp", 0)) <= int(time.time()):
        return None
    return payload


def token_from_request(request: Request) -> Optional[str]:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    # WebSockets cannot set headers in the browser, so a query parameter is accepted too.
    return request.query_params.get("token")


def current_user(request: Request) -> Dict[str, Any]:
    payload = decode_token(token_from_request(request) or "")
    if not payload:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return payload


def require_owner(request: Request) -> Dict[str, Any]:
    """FastAPI dependency: the owner role, for anything that changes the plant or the records."""
    user = current_user(request)
    if user.get("role") != ROLE_OWNER:
        raise HTTPException(
            status_code=403,
            detail="This action requires the owner role; you are signed in as "
                   f"{user.get('role', 'unknown')} (read-only).")
    return user


# --------------------------------------------------------------------- endpoints

class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest):
    record = users().get(body.username.strip())
    # Same message and no timing shortcut whether the user exists or the password is wrong.
    if not record or not verify_password(body.password, record.get("password", {})):
        logger.info("Failed login for %r", body.username)
        raise HTTPException(status_code=401, detail="Invalid username or password")
    issued = issue_token(record["username"], record.get("role", ROLE_OPERATOR))
    logger.info("Login: %s (%s)", record["username"], record.get("role"))
    return {
        **issued,
        "display_name": record.get("display_name", record["username"]),
        "job_title": record.get("job_title", ""),
        "permissions": {"can_authorize_actions": record.get("role") == ROLE_OWNER,
                        "can_edit_records": record.get("role") == ROLE_OWNER},
    }


@router.get("/me")
def me(request: Request):
    user = current_user(request)
    record = users().get(user["sub"], {})
    return {
        "username": user["sub"],
        "role": user.get("role"),
        "expires_at": user.get("exp"),
        "seconds_remaining": max(0, int(user.get("exp", 0)) - int(time.time())),
        "display_name": record.get("display_name", user["sub"]),
        "job_title": record.get("job_title", ""),
        "permissions": {"can_authorize_actions": user.get("role") == ROLE_OWNER,
                        "can_edit_records": user.get("role") == ROLE_OWNER},
    }


@router.post("/logout")
def logout(request: Request):
    """Stateless tokens, so this is the client dropping its token.

    Said plainly rather than implying server-side revocation that does not exist: the token stays
    valid until it expires, which is why the TTL is 30 minutes and the UI signs out on inactivity.
    """
    try:
        user = current_user(request)
        logger.info("Logout: %s", user["sub"])
    except HTTPException:
        pass
    return {"status": "SIGNED_OUT",
            "note": "Discard the token on the client; it expires on its own within 30 minutes."}
