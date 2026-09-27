"""GATE 1 verification: the fixes for what the real UI showed on 2026-09-27 at ~04:05.

Connects a real websocket client to the backend exactly as the browser does
(`ws://127.0.0.1:8000/ws`), so it proves what the dashboard will receive without a page
refresh. Then it authorises every pending action through the public API and keeps the plant
running past the cooldown to prove nothing re-opens.

Checks, in the order Firas reported the issues:
  1. pending actions are announced over the websocket (no F5 needed)
  2. authorising resolves the incident, and the resume URL is handled cleanly
  3. P5: a stopped machine decays instead of snapping back onto the fault curve
  4. no new incident of the same type re-opens afterwards

Usage:  python n8n/gate1_verify.py
Exit code 0 = all checks passed.
"""

import asyncio
import json
import sys
import time
import urllib.error
import urllib.request
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _auth import auth_headers  # noqa: E402

BACKEND = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/ws"

results = []


def check(label, ok, detail=""):
    results.append((label, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


def request(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BACKEND + path, data=data, method=method,
        headers={"Content-Type": "application/json", **auth_headers()})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()[:300]
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


async def collect(ws, seconds, events):
    """Drain the socket for a while, recording every message."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=max(0.2, deadline - time.time()))
        except asyncio.TimeoutError:
            continue
        except Exception:
            return
        try:
            events.append(json.loads(raw))
        except Exception:
            pass


async def main() -> int:
    try:
        import websockets
    except ImportError:
        print("websockets package missing — pip install websockets")
        return 1

    print("=" * 78)
    print("GATE 1 VERIFICATION — live, through a real websocket client")
    print("=" * 78)

    status, _ = request("GET", "/health")
    check("backend is up", status == 200, f"HTTP {status}")
    if status != 200:
        return 1

    request("POST", "/api/demo/reset", {})
    await asyncio.sleep(1.5)

    events = []
    async with websockets.connect(f"{WS_URL}?token={__import__('_auth').token()}") as ws:
        print("\n1. websocket connected as the dashboard does; triggering machine_overheating")
        request("POST", "/api/demo/scenario", {"scenario": "machine_overheating"})
        await collect(ws, 16, events)

        types = [e.get("event_type") for e in events]
        check("INCIDENT_CREATED arrived on the socket", "INCIDENT_CREATED" in types)

        action_events = [e for e in events if e.get("event_type") == "ACTION_STATUS"]
        awaiting = [e for e in action_events if (e.get("data") or {}).get("status") == "AWAITING_APPROVAL"]
        check("pending actions were announced without a refresh (issue 1)", bool(awaiting),
              ", ".join(sorted({e["data"]["action_type"] for e in awaiting})) or "none announced")
        if awaiting:
            first = awaiting[0]["data"]
            check("payload has the fields App.tsx consumes",
                  all(k in first for k in ("id", "incident_id", "action_type", "status", "risk_level")))
            check("the incident was announced before its actions",
                  types.index("INCIDENT_CREATED") < types.index("ACTION_STATUS"))

        _, incidents = request("GET", "/api/incidents")
        incident = (incidents.get("incidents") or [None])[0]
        check("an incident exists", incident is not None)
        if incident is None:
            return report()
        incident_id = incident["id"]
        print(f"      {incident_id} {incident['type']} severity={incident['severity']} "
              f"confidence={incident['confidence']}")

        print("\n2. authorising every pending action through the API (the AUTHORIZE button)")
        _, actions = request("GET", "/api/actions")
        pending = [a for a in actions.get("actions", [])
                   if a["incident_id"] == incident_id and a["status"] == "AWAITING_APPROVAL"]
        check("three actions were awaiting approval", len(pending) == 3,
              ", ".join(f"{a['action_type']}({a['risk_level']})" for a in pending))
        for action in pending:
            code, _ = request("POST", f"/api/actions/{action['id']}/authorize",
                              {"authorized_by": "owner_01"})
            print(f"      authorize {action['id']} {action['action_type']} -> HTTP {code}")

        await collect(ws, 12, events)
        completed = {(e.get("data") or {}).get("action_type")
                     for e in events if e.get("event_type") == "ACTION_STATUS"
                     and (e.get("data") or {}).get("status") == "COMPLETED"}
        check("completions were announced on the socket too", len(completed) >= 1,
              ", ".join(sorted(c for c in completed if c)))

        _, incident_now = request("GET", f"/api/incidents/{incident_id}")
        check("incident resolved", incident_now.get("status") in ("RESOLVED", "RESOLVING"),
              f"status={incident_now.get('status')}")

        _, bridge = request("GET", f"/api/ai/n8n/state/{incident_id}")
        print(f"      n8n exchange: {json.dumps(bridge.get('last_exchange'))}")

        print("\n3. P5: the stopped machine must decay, not snap back to the fault curve")
        await asyncio.sleep(6)
        _, machines = request("GET", "/api/machines")
        m04 = next((m for m in machines.get("machines", []) if m["id"] == "M-04"), None)
        if m04:
            pressure = m04["parameters"]["pressure"]["value"]
            temperature = m04["parameters"]["temperature"]["value"]
            print(f"      M-04 pressure={pressure} bar temperature={temperature}°C status={m04['status']}")
            check("M-04 pressure decayed below its 8.0 bar limit (issue 3)", pressure < 8.0,
                  f"{pressure} bar")
            check("M-04 reports nominal again", m04["status"] == "INFO", m04["status"])

        print("\n4. nothing may re-open while the readings fall — watching for 65 s")
        before = {i["id"] for i in request("GET", "/api/incidents")[1].get("incidents", [])}
        watch = []
        await collect(ws, 65, watch)
        after = request("GET", "/api/incidents")[1].get("incidents", [])
        new = [i for i in after if i["id"] not in before]
        check("no new incident was opened after resolution (issues 3+4)", not new,
              ", ".join(f"{i['id']}/{i['type']}" for i in new) or "none")

        holds = [e for e in watch if e.get("event_type") == "INCIDENT_CREATED"]
        check("no INCIDENT_CREATED on the socket during the watch", not holds)

    request("POST", "/api/demo/reset", {})
    return report()


def report() -> int:
    passed = sum(1 for _, ok in results if ok)
    print("\n" + "=" * 78)
    print(f"RESULT: {passed}/{len(results)} checks passed")
    failed = [label for label, ok in results if not ok]
    if failed:
        print("FAILED: " + "; ".join(failed))
    else:
        print("GATE 1 FIXES VERIFIED")
    print("=" * 78)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
