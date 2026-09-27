"""Step 3 acceptance test: backend -> n8n -> owner approval -> verification -> status.

Drives the real thing end to end with no stubs:

1. trigger the machine_overheating scenario on the backend
2. the orchestrator fire-and-forgets the incident to n8n's production webhook
3. n8n runs the deterministic recommendation, POSTs enrichment back, and parks on its Wait node
4. we authorise the pending actions through the normal /api/actions API, exactly as the
   dashboard button does; command_engine POSTs the decision to n8n's resume URL
5. n8n resumes, waits 15 s, GETs /verify, and POSTs the final status
6. we assert the n8n execution finished successfully and the incident ended up resolved

Usage:  python n8n/e2e_test.py
Exit code 0 = acceptance met.
"""

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
BACKEND = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
N8N = os.getenv("N8N_BASE_URL", "http://localhost:5678")

failures: list = []
steps: list = []


def api_key() -> str:
    key = os.getenv("N8N_API_KEY", "").strip()
    if not key and (REPO / ".env").exists():
        for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("N8N_API_KEY="):
                key = line.split("=", 1)[1].strip()
    return key


def request(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json", **auth_headers(), **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()[:400]
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


def n8n_api(path):
    return request("GET", f"{N8N}/api/v1{path}", headers={"X-N8N-API-KEY": api_key()})


def check(label, condition, detail=""):
    steps.append((label, bool(condition), detail))
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        failures.append(label)


def wait_for(predicate, timeout=40, interval=1.0):
    """Poll until predicate returns a truthy value. Returns it, or None on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
    return None


def main() -> int:
    print("=" * 78)
    print("STEP 3 ACCEPTANCE — backend <-> n8n round trip")
    print("=" * 78)

    print("\n1. preconditions")
    status, _ = request("GET", f"{BACKEND}/health")
    check("backend is up", status == 200, f"HTTP {status}")
    status, workflows = n8n_api("/workflows?limit=50")
    active = [w for w in (workflows.get("data", []) if isinstance(workflows, dict) else [])
              if w.get("active")]
    check("an n8n workflow is ACTIVE", bool(active),
          ", ".join(w["name"] for w in active) or "none active")
    status, bridge = request("GET", f"{BACKEND}/api/ai/n8n/state")
    check("bridge is enabled", isinstance(bridge, dict) and bridge.get("enabled") is True,
          isinstance(bridge, dict) and bridge.get("incident_webhook_url", ""))

    before = n8n_api("/executions?limit=100")[1]
    before_ids = {e["id"] for e in before.get("data", [])} if isinstance(before, dict) else set()

    print("\n2. trigger the machine_overheating scenario")
    request("POST", f"{BACKEND}/api/demo/reset", {})
    time.sleep(1)
    request("POST", f"{BACKEND}/api/demo/scenario", {"scenario": "machine_overheating"})

    incident = wait_for(lambda: (request("GET", f"{BACKEND}/api/incidents")[1] or {}).get("incidents") or None,
                        timeout=30)
    check("an incident was created", bool(incident))
    if not incident:
        return report()
    incident = incident[0]
    incident_id = incident["id"]
    print(f"      {incident_id}  {incident['type']}  severity={incident['severity']}  "
          f"confidence={incident['confidence']}")
    check("incident type is MACHINE_OVERHEATING", incident["type"] == "MACHINE_OVERHEATING",
          incident["type"])

    print("\n3. n8n received it and started an execution")
    execution = wait_for(lambda: next(
        (e for e in (n8n_api("/executions?limit=100")[1].get("data", []) or [])
         if e["id"] not in before_ids), None), timeout=25)
    check("a new n8n execution exists", bool(execution),
          f"id={execution['id']} status={execution['status']}" if execution else "none appeared")
    if not execution:
        _, state = request("GET", f"{BACKEND}/api/ai/n8n/state")
        print("      bridge last_exchange:", json.dumps(state.get("last_exchange", {}))[:300])
        return report()
    execution_id = execution["id"]

    print("\n4. n8n posted its enrichment back to the backend")
    enriched = wait_for(lambda: "enriched by" in
                        (request("GET", f"{BACKEND}/api/incidents/{incident_id}")[1] or {}).get("ai_reasoning", ""),
                        timeout=25)
    check("incident reasoning was rewritten by n8n", bool(enriched))
    _, state = request("GET", f"{BACKEND}/api/ai/n8n/state/{incident_id}")
    resume_url = state.get("resume_url") if isinstance(state, dict) else None
    check("resume URL was registered", bool(resume_url), resume_url or "missing")

    _, current = request("GET", f"{BACKEND}/api/incidents/{incident_id}")
    print("      --- reasoning now shown in the dashboard ---")
    for line in (current.get("ai_reasoning") or "").splitlines():
        print("      " + line[:150])

    print("\n5. n8n execution is parked on its Wait node")
    waiting = wait_for(lambda: n8n_api(f"/executions/{execution_id}")[1].get("status") == "waiting",
                       timeout=20)
    _, execution_now = n8n_api(f"/executions/{execution_id}")
    check("execution is waiting for the owner", waiting or execution_now.get("status") == "waiting",
          f"status={execution_now.get('status')}")

    print("\n6. owner authorises the pending actions (same API the dashboard button calls)")
    _, actions = request("GET", f"{BACKEND}/api/actions")
    pending = [a for a in actions.get("actions", [])
               if a["incident_id"] == incident_id and a["status"] == "AWAITING_APPROVAL"]
    check("there are actions awaiting approval", bool(pending),
          ", ".join(f"{a['action_type']}({a['risk_level']})" for a in pending))
    for action in pending:
        status, _ = request("POST", f"{BACKEND}/api/actions/{action['id']}/authorize",
                            {"authorized_by": "owner_01"})
        print(f"      authorize {action['id']} {action['action_type']} -> HTTP {status}")

    print("\n7. n8n resumed, verified, and reported a final status (Wait 15 s + checks)")
    finished = wait_for(lambda: n8n_api(f"/executions/{execution_id}")[1].get("status")
                        not in ("waiting", "running", None), timeout=90, interval=3)
    _, execution_final = n8n_api(f"/executions/{execution_id}")
    final_status = execution_final.get("status")
    check("n8n execution finished", bool(finished), f"status={final_status}")
    check("n8n execution succeeded", final_status == "success", f"status={final_status}")

    # Actuators take ~2 s each; poll rather than sampling once.
    wait_for(lambda: request("GET", f"{BACKEND}/api/ai/n8n/verify/{incident_id}")[1].get("verified") is True,
             timeout=30, interval=2)
    _, verify = request("GET", f"{BACKEND}/api/ai/n8n/verify/{incident_id}")
    check("verification passed", verify.get("verified") is True)
    for item in verify.get("details", []):
        print(f"      [{'PASS' if item['passed'] else 'FAIL'}] {item['check']}")
    print(f"      telemetry_consistent={verify.get('telemetry_consistent')} "
          f"(simulator keeps driving the scenario — informational only)")

    # Poll: the three authorisations execute concurrently with a 2 s actuator delay each, so a
    # single sample can land before the last one finishes. Observed once as a false failure.
    wait_for(lambda: request("GET", f"{BACKEND}/api/incidents/{incident_id}")[1]
             .get("status") in ("RESOLVED", "RESOLVING"), timeout=30, interval=2)
    _, final_incident = request("GET", f"{BACKEND}/api/incidents/{incident_id}")
    check("incident reached a resolved state",
          final_incident.get("status") in ("RESOLVED", "RESOLVING"),
          f"status={final_incident.get('status')}")

    print("\n8. the agent log shows n8n's contribution")
    _, logs = request("GET", f"{BACKEND}/api/ai/logs")
    n8n_entries = [l for l in logs.get("logs", []) if "n8n" in l.get("agent_id", "")]
    check("agent log has n8n entries", bool(n8n_entries), f"{len(n8n_entries)} entries")
    for entry in n8n_entries[:4]:
        print(f"      [{entry['agent_id']}] {entry['decision'][:120]}")

    request("POST", f"{BACKEND}/api/demo/reset", {})
    return report()


def report() -> int:
    print("\n" + "=" * 78)
    passed = sum(1 for _, ok, _ in steps if ok)
    print(f"RESULT: {passed}/{len(steps)} checks passed")
    if failures:
        print("FAILED: " + "; ".join(failures))
    else:
        print("STEP 3 ACCEPTANCE MET")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
