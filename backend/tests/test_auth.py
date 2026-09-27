"""Authentication tests: login ok/ko, expired token rejected, operator cannot authorize."""

import time
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.api.auth import decode_token, hash_password, issue_token, verify_password
from app.main import app
from app.models.schemas import Action, ActionStatus, RiskLevel
from app.services.state_store import state

client = TestClient(app)

OWNER = {"username": "firas", "password": "Copilot#Owner2026"}
OPERATOR = {"username": "operator", "password": "Copilot#Operator2026"}


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def login(creds):
    return client.post("/api/auth/login", json=creds)


# --------------------------------------------------------------------- passwords

def test_passwords_are_hashed_not_stored():
    record = hash_password("Copilot#Owner2026")
    assert record["algorithm"] == "pbkdf2_sha256"
    assert "Copilot#Owner2026" not in str(record), "the password must not appear in the record"
    assert verify_password("Copilot#Owner2026", record)
    assert not verify_password("copilot#owner2026", record), "case matters"
    assert not verify_password("", record)


def test_the_seed_file_holds_no_plaintext_password():
    from app.api.auth import USERS_PATH
    raw = USERS_PATH.read_text(encoding="utf-8")
    for secret in ("Copilot#Owner2026", "Copilot#Operator2026", "Copilot#Auditor2026"):
        assert secret not in raw, f"{secret} is stored in plaintext"


# --------------------------------------------------------------------- login

def test_login_succeeds_and_returns_a_usable_token():
    response = login(OWNER)
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "owner"
    assert body["expires_in"] == 30 * 60, "30-minute expiry as specified"
    assert body["permissions"]["can_authorize_actions"] is True
    assert client.get("/api/incidents", headers=bearer(body["token"])).status_code == 200


def test_login_fails_on_a_wrong_password_and_on_an_unknown_user():
    bad_password = client.post("/api/auth/login",
                               json={"username": "firas", "password": "wrong"})
    unknown_user = client.post("/api/auth/login",
                               json={"username": "nobody", "password": "whatever"})
    assert bad_password.status_code == 401
    assert unknown_user.status_code == 401
    # Identical message, so the response does not reveal which usernames exist.
    assert bad_password.json()["detail"] == unknown_user.json()["detail"]


def test_the_api_is_closed_without_a_token():
    assert client.get("/api/incidents").status_code == 401
    assert client.get("/api/actions").status_code == 401
    assert client.get("/api/machines").status_code == 401


def test_health_stays_public_so_probes_keep_working():
    assert client.get("/health").status_code == 200


def test_a_forged_token_is_rejected():
    good = login(OWNER).json()["token"]
    body, signature = good.split(".")
    forged = f"{body}.{'x' * len(signature)}"
    assert decode_token(forged) is None
    assert client.get("/api/incidents", headers=bearer(forged)).status_code == 401


def test_a_token_whose_payload_was_tampered_with_is_rejected():
    """Swap the role to owner in the payload and the signature no longer matches."""
    import base64, json
    token = login(OPERATOR).json()["token"]
    body, signature = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    payload["role"] = "owner"
    forged_body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    assert decode_token(f"{forged_body}.{signature}") is None


# --------------------------------------------------------------------- expiry

def test_an_expired_token_is_rejected():
    expired = issue_token("firas", "owner", ttl=-1)["token"]
    assert decode_token(expired) is None
    assert client.get("/api/incidents", headers=bearer(expired)).status_code == 401


def test_a_token_about_to_expire_still_works():
    nearly = issue_token("firas", "owner", ttl=5)["token"]
    assert decode_token(nearly) is not None
    assert client.get("/api/incidents", headers=bearer(nearly)).status_code == 200


def test_me_reports_the_remaining_seconds():
    token = login(OWNER).json()["token"]
    body = client.get("/api/auth/me", headers=bearer(token)).json()
    assert body["username"] == "firas"
    assert 0 < body["seconds_remaining"] <= 30 * 60


# --------------------------------------------------------------------- roles

def _pending_action():
    state.initialize_state()
    action = Action(
        id="ACT-AUTH", incident_id=None, action_type="STOP_MACHINE", target="M-04",
        reason="test", risk_level=RiskLevel.HIGH, status=ActionStatus.AWAITING_APPROVAL,
        created_at=datetime.utcnow(),
    )
    state.actions[action.id] = action
    return action


def test_an_operator_cannot_authorize_an_action():
    """The gate is server-side: a read-only role gets 403 even if the UI is bypassed."""
    action = _pending_action()
    token = login(OPERATOR).json()["token"]
    response = client.post(f"/api/actions/{action.id}/authorize",
                           json={"authorized_by": "operator"}, headers=bearer(token))
    assert response.status_code == 403
    assert "owner role" in response.json()["detail"]
    assert state.actions[action.id].status == ActionStatus.AWAITING_APPROVAL, "nothing happened"
    state.initialize_state()


def test_an_operator_cannot_cancel_an_action_either():
    action = _pending_action()
    token = login(OPERATOR).json()["token"]
    assert client.post(f"/api/actions/{action.id}/cancel", json={"cancelled_by": "operator"},
                       headers=bearer(token)).status_code == 403
    state.initialize_state()


def test_an_operator_can_still_read():
    token = login(OPERATOR).json()["token"]
    assert client.get("/api/incidents", headers=bearer(token)).status_code == 200
    assert client.get("/api/machines", headers=bearer(token)).status_code == 200
    me = client.get("/api/auth/me", headers=bearer(token)).json()
    assert me["permissions"]["can_authorize_actions"] is False


def test_the_owner_can_authorize():
    action = _pending_action()
    token = login(OWNER).json()["token"]
    response = client.post(f"/api/actions/{action.id}/authorize",
                           json={"authorized_by": "firas"}, headers=bearer(token))
    assert response.status_code == 200
    assert state.actions[action.id].status != ActionStatus.AWAITING_APPROVAL
    state.initialize_state()


# --------------------------------------------------------------------- service token

def test_the_n8n_bridge_accepts_the_service_secret_without_a_user(monkeypatch):
    monkeypatch.setenv("N8N_SERVICE_TOKEN", "unit-test-secret")
    assert client.get("/api/ai/n8n/state").status_code == 401
    ok = client.get("/api/ai/n8n/state", headers={"X-Copilot-Service-Token": "unit-test-secret"})
    assert ok.status_code == 200
    wrong = client.get("/api/ai/n8n/state", headers={"X-Copilot-Service-Token": "nope"})
    assert wrong.status_code == 401


def test_the_service_token_also_works_as_a_query_parameter(monkeypatch):
    monkeypatch.setenv("N8N_SERVICE_TOKEN", "unit-test-secret")
    assert client.get("/api/ai/n8n/state?service_token=unit-test-secret").status_code == 200
    assert client.get("/api/ai/n8n/state?service_token=wrong").status_code == 401
