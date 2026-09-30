import base64
import hashlib
import hmac
import secrets
from collections import OrderedDict, deque
from time import monotonic

from fastapi import Header, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import get_settings

COOKIE_NAME = "themisto_session"
login_attempts: OrderedDict[str, deque] = OrderedDict()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
    return f"pbkdf2_sha256$600000${salt}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, iterations, salt, expected = encoded.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
        return hmac.compare_digest(base64.b64encode(digest).decode(), expected)
    except (ValueError, TypeError):
        return False


def serializer():
    return URLSafeTimedSerializer(get_settings().session_secret, salt="themisto-admin-v1")


def read_session(request: Request) -> dict | None:
    try:
        data = serializer().loads(
            request.cookies.get(COOKIE_NAME, ""), max_age=get_settings().session_seconds
        )
        if data.get("username") != get_settings().admin_username:
            return None
        return data
    except (BadSignature, SignatureExpired):
        return None


def check_origin(request: Request):
    if request.headers.get("origin") != get_settings().public_origin:
        raise HTTPException(403, "Invalid request origin")


def require_admin(request: Request):
    data = read_session(request)
    if not data:
        raise HTTPException(401, "Admin login required")
    check_origin(request)
    if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), data["csrf"]):
        raise HTTPException(403, "Invalid CSRF token")
    return data


def require_ingest(authorization: str = Header(default="")):
    if not hmac.compare_digest(authorization, f"Bearer {get_settings().ingest_token}"):
        raise HTTPException(401, "Invalid ingestion credential")


def throttle_login(request: Request):
    # Caddy overwrites this header; the backend has no published host port.
    address = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
    now = monotonic()
    attempts = login_attempts.setdefault(address, deque())
    login_attempts.move_to_end(address)
    while attempts and now - attempts[0] > 300:
        attempts.popleft()
    if len(attempts) >= 5:
        raise HTTPException(429, "Too many login attempts; retry in five minutes")
    attempts.append(now)
    if len(login_attempts) > 10000:
        login_attempts.popitem(last=False)
