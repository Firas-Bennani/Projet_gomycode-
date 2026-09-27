"""Shared login helper for the verification scripts, now that the API requires a token.

Reads demo credentials from COPILOT_USER / COPILOT_PASSWORD, falling back to the owner account
documented in docs/ai/DEMO.md. Logs in once per process and caches the token.
"""

import json
import os
import urllib.request

BACKEND = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
USER = os.getenv("COPILOT_USER", "firas")
PASSWORD = os.getenv("COPILOT_PASSWORD", "Copilot#Owner2026")

_token = None


def token() -> str:
    global _token
    if _token:
        return _token
    body = json.dumps({"username": USER, "password": PASSWORD}).encode()
    req = urllib.request.Request(f"{BACKEND}/api/auth/login", data=body, method="POST",
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as response:
        _token = json.load(response)["token"]
    return _token


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {token()}"}
