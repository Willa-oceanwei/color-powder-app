"""Short-lived, signed browser tokens for the app's password gate."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


TOKEN_VERSION = 1


def create_remember_token(password: str, lifetime_seconds: int, *, now: int | None = None) -> str:
    """Create a tamper-evident token that expires after ``lifetime_seconds``."""
    issued_at = int(time.time() if now is None else now)
    payload = {"exp": issued_at + int(lifetime_seconds), "v": TOKEN_VERSION}
    encoded = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signature = hmac.new(password.encode(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{_encode(signature)}"


def validate_remember_token(token: str | None, password: str, *, now: int | None = None) -> bool:
    """Return whether a token has a valid signature, version, and future expiry."""
    if not token:
        return False
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = hmac.new(password.encode(), encoded.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_decode(supplied_signature), expected_signature):
            return False
        payload = json.loads(_decode(encoded))
        current_time = int(time.time() if now is None else now)
        return payload.get("v") == TOKEN_VERSION and int(payload["exp"]) > current_time
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
