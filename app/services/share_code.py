from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Optional


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")


def _b64d(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def make_share_code(collection_id: int, owner_id: int, secret: str) -> str:
    payload = {"cid": int(collection_id), "oid": int(owner_id)}
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).digest()[:6]
    return _b64e(raw + sig)


def parse_share_code(code: str, secret: str) -> Optional[tuple[int, int]]:
    try:
        blob = _b64d(code.strip())
        raw, sig = blob[:-6], blob[-6:]
        expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).digest()[:6]
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(raw.decode("utf-8"))
        return int(data["cid"]), int(data["oid"])
    except Exception:
        return None
