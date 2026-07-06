"""
Validates Telegram Mini App `initData` per the official spec:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

This is the SINGLE most important security check in the whole project — without
it, anyone could forge requests claiming to be any Telegram user. Never skip it.

Also issues short-lived JWTs so the webapp frontend doesn't need to resend
raw initData on every API call.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

import jwt

from bot.config import BOT_TOKEN, JWT_SECRET

JWT_TTL_SECONDS = 3600 * 12


class InvalidInitData(Exception):
    pass


def validate_init_data(init_data: str, max_age_seconds: int = 86400) -> dict:
    """
    Verify the HMAC signature of Telegram WebApp initData and return the
    parsed user dict. Raises InvalidInitData on any failure.
    """
    if not init_data:
        raise InvalidInitData("empty init_data")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InvalidInitData("missing hash")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))

    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise InvalidInitData("hash mismatch — request did not originate from Telegram")

    auth_date = int(pairs.get("auth_date", "0"))
    if time.time() - auth_date > max_age_seconds:
        raise InvalidInitData("init_data expired")

    user_raw = pairs.get("user")
    if not user_raw:
        raise InvalidInitData("missing user field")

    return json.loads(user_raw)


def issue_session_token(user_id: int) -> str:
    payload = {"uid": user_id, "exp": int(time.time()) + JWT_TTL_SECONDS}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_session_token(token: str) -> int:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return int(payload["uid"])
    except jwt.PyJWTError as e:
        raise InvalidInitData(str(e))
