"""Step 5 acceptance: does the LLM path actually produce grounded recommendations, and does the
deterministic fallback take over when the model is unavailable?

Run it three ways:

    python n8n/llm_roundtrip.py            # measure the live path (whatever is active)
    python n8n/llm_roundtrip.py --break    # temporarily break the model node, prove the fallback
    python n8n/llm_roundtrip.py --restore  # put the workflow back from n8n/workflows/*.json

``--break`` points the active v2 workflow's chat-model node at a model id that does not exist.
The credential is left in place on purpose — n8n refuses to publish a workflow with a missing
required credential, so that cannot be tested. Nothing touches the stored credential, and the
workflow is always restored from the committed export afterwards.
"""

import argparse
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _auth import auth_headers  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]
BACKEND = "http://127.0.0.1:8000"
N8N = "http://localhost:5678"
V2_FILE = REPO / "n8n" / "workflows" / "incident_response_v2.json"
V2_NAME = "Incident Response v2 (Gemini + RAG)"
CHAT_NODE = "Google Gemini Chat Model"
CREATE_FIELDS = ("name", "nodes", "connections", "settings")


def api_key() -> str:
    key = os.getenv("N8N_API_KEY", "").strip()
    if not key and (REPO / ".env").exists():
        for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("N8N_API_KEY="):
                key = line.split("=", 1)[1].strip()
    return key


def call(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", **auth_headers(), **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()[:400]
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


def n8n_api(method, path, body=None):
    return call(method, f"{N8N}/api/v1{path}", body, {"X-N8N-API-KEY": api_key()})


def workflow_id(name=V2_NAME):
    _, body = n8n_api("GET", "/workflows?limit=100")
    for workflow in (body.get("data", []) if isinstance(body, dict) else []):
        if workflow.get("name") == name:
            return workflow["id"]
    return None


def push_workflow(definition, activate=True):
    wid = workflow_id(definition["name"])
    payload = {f: definition[f] for f in CREATE_FIELDS if f in definition}
    n8n_api("POST", f"/workflows/{wid}/deactivate")
    status, body = n8n_api("PUT", f"/workflows/{wid}", payload)
    if status != 200:
        sys.exit(f"could not update the workflow: HTTP {status} {body}")
    if activate:
        status, body = n8n_api("POST", f"/workflows/{wid}/activate")
        if status != 200:
            sys.exit(f"could not activate: HTTP {status} {body}")
    return wid


def restore():
    definition = json.loads(V2_FILE.read_text(encoding="utf-8"))
    push_workflow(definition, activate=True)
    print(f"restored {V2_NAME} from {V2_FILE.name} and re-activated it")


def break_model():
    """Point the chat model at a model id that does not exist.

    The credential is deliberately LEFT IN PLACE: n8n refuses to publish a workflow whose node
    is missing a required credential ("Cannot publish workflow: Missing required credential"),
    so removing it cannot be activated and therefore cannot be tested. An unreachable model
    reproduces the real failure we hit in the wild, when models/gemini-2.5-flash started
    returning 404 "no longer available to new users".
    """
    definition = json.loads(V2_FILE.read_text(encoding="utf-8"))
    touched = False
    for node in definition["nodes"]:
        if node["name"] == CHAT_NODE:
            node.setdefault("parameters", {})["modelName"] = "models/this-model-does-not-exist"
            touched = True
    if not touched:
        sys.exit(f"node {CHAT_NODE!r} not found")
    push_workflow(definition, activate=True)
    print(f"broke {CHAT_NODE!r}: model set to a non-existent id (credential left intact)")


def wait_for(predicate, timeout, interval=1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return None


def run_scenario(label):
    """Trigger machine_overheating and time the enrichment. Returns a result dict."""
    print(f"\n--- {label} ---")
    call("POST", f"{BACKEND}/api/demo/reset", {})
    time.sleep(1.5)

    _, before = n8n_api("GET", "/executions?limit=50")
    before_ids = {e["id"] for e in before.get("data", [])} if isinstance(before, dict) else set()

    call("POST", f"{BACKEND}/api/demo/scenario", {"scenario": "machine_overheating"})

    incidents = wait_for(
        lambda: (call("GET", f"{BACKEND}/api/incidents")[1] or {}).get("incidents") or None, 30)
    if not incidents:
        return {"ok": False, "why": "no incident was created"}
    incident_id = incidents[0]["id"]
    detected_at = time.time()
    print(f"  incident {incident_id} {incidents[0]['type']} conf={incidents[0]['confidence']}")

    enriched = wait_for(
        lambda: "enriched by" in (call("GET", f"{BACKEND}/api/incidents/{incident_id}")[1] or {})
        .get("ai_reasoning", ""), 90, interval=1.0)
    latency = time.time() - detected_at if enriched else None

    _, incident = call("GET", f"{BACKEND}/api/incidents/{incident_id}")
    reasoning = incident.get("ai_reasoning", "")

    execution = wait_for(lambda: next(
        (e for e in (n8n_api("GET", "/executions?limit=50")[1].get("data", []) or [])
         if e["id"] not in before_ids), None), 20)

    print(f"  enrichment arrived: {'yes' if enriched else 'NO'}"
          + (f" after {latency:.1f}s" if latency else ""))
    if execution:
        print(f"  n8n execution {execution['id']} status={execution['status']}")
    print("  --- reasoning on the incident card ---")
    for line in reasoning.splitlines():
        print("    " + line[:160])

    # Authorise the hazard-resolving action and confirm the approval flow still works.
    _, actions = call("GET", f"{BACKEND}/api/actions")
    stop = next((a for a in actions.get("actions", [])
                 if a["incident_id"] == incident_id and a["action_type"] == "STOP_MACHINE"
                 and a["status"] == "AWAITING_APPROVAL"), None)
    resolved = False
    if stop:
        call("POST", f"{BACKEND}/api/actions/{stop['id']}/authorize", {"authorized_by": "owner_01"})
        resolved = bool(wait_for(
            lambda: (call("GET", f"{BACKEND}/api/incidents/{incident_id}")[1] or {})
            .get("status") in ("RESOLVED", "RESOLVING"), 25, 2))
    print(f"  STOP_MACHINE authorised: {'yes' if stop else 'NOT FOUND'} | incident resolved: {resolved}")

    citations = [tok for tok in reasoning.split() if "§" in tok]
    return {
        "ok": bool(enriched),
        "incident_id": incident_id,
        "latency_s": round(latency, 1) if latency else None,
        "reasoning": reasoning,
        "has_citation": "§" in reasoning,
        "citations": citations[:6],
        "produced_by": reasoning.split("— enriched by")[-1].strip() if "— enriched by" in reasoning else "",
        "execution_status": execution.get("status") if execution else None,
        "actions_present": bool(stop),
        "resolved": resolved,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--break", dest="do_break", action="store_true")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()

    if args.restore:
        restore()
        return 0

    if args.do_break:
        break_model()
        try:
            result = run_scenario("LLM BROKEN — expecting the deterministic template fallback")
        finally:
            restore()
        print("\n" + json.dumps({k: v for k, v in result.items() if k != "reasoning"}, indent=2))
        return 0 if result["ok"] else 1

    result = run_scenario("LLM LIVE — Gemini via the n8n AI Agent")
    print("\n" + json.dumps({k: v for k, v in result.items() if k != "reasoning"}, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
