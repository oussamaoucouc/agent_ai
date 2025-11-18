import os
import time
import uuid
import hmac
import json
import base64
from hashlib import sha256
from typing import Optional, Dict, Any


APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
secret_str = os.environ.get("APP_AUTH_SECRET")
if APP_ENV == "production" and not secret_str:
    raise RuntimeError("APP_AUTH_SECRET must be set in production")
AUTH_SECRET = (secret_str or "dev-secret-key").encode("utf-8")

# Token TTLs configurable via environment variables
def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default

ACCESS_TTL_SECONDS = _env_int("AUTH_ACCESS_TTL_SECONDS", 15 * 60)
REFRESH_TTL_SECONDS = _env_int("AUTH_REFRESH_TTL_SECONDS", 7 * 24 * 3600)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    # Pad base64 string
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def issue_token(user_id: str, role: str, ttl_seconds: int = 24 * 3600) -> str:
    """
    Issue a lightweight HMAC-signed token. Format: base64url(payload).base64url(signature)
    payload = {"uid": user_id, "role": role, "exp": epoch_seconds}
    """
    now = int(time.time())
    payload = {"uid": user_id, "role": role, "exp": now + ttl_seconds, "iat": now, "jti": uuid.uuid4().hex}
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(AUTH_SECRET, payload_bytes, sha256).digest()
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(sig)}"


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig_b64 = parts
        payload_bytes = _b64url_decode(payload_b64)
        expected_sig = hmac.new(AUTH_SECRET, payload_bytes, sha256).digest()
        provided_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None
        payload = json.loads(payload_bytes.decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        uid = payload.get("uid")
        role = payload.get("role")
        if not uid or not role:
            return None
        return payload
    except Exception:
        return None


def get_user_from_auth_header(authorization_header: Optional[str]) -> Optional[Dict[str, Any]]:
    if not authorization_header:
        return None
    try:
        scheme, _, token = authorization_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        payload = verify_token(token)
        return payload
    except Exception:
        return None
def issue_access_token(user_id: str, role: str, ttl_seconds: Optional[int] = None) -> str:
    now = int(time.time())
    ttl = ttl_seconds if isinstance(ttl_seconds, int) and ttl_seconds > 0 else ACCESS_TTL_SECONDS
    payload = {"uid": user_id, "role": role, "exp": now + ttl, "iat": now, "jti": uuid.uuid4().hex, "typ": "access"}
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(AUTH_SECRET, payload_bytes, sha256).digest()
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(sig)}"

def issue_refresh_token(user_id: str, role: str, ttl_seconds: Optional[int] = None) -> str:
    now = int(time.time())
    ttl = ttl_seconds if isinstance(ttl_seconds, int) and ttl_seconds > 0 else REFRESH_TTL_SECONDS
    payload = {"uid": user_id, "role": role, "exp": now + ttl, "iat": now, "jti": uuid.uuid4().hex, "typ": "refresh"}
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(AUTH_SECRET, payload_bytes, sha256).digest()
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(sig)}"

def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    payload = verify_token(token)
    if not payload or payload.get("typ") != "access":
        return None
    return payload

def verify_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    payload = verify_token(token)
    if not payload or payload.get("typ") != "refresh":
        return None
    return payload