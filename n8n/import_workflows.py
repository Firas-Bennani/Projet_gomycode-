"""Import and activate workflows in a running n8n through its public API.

Beats importing by hand: repeatable, and it fails loudly instead of leaving a half-configured
workflow. Reads the API key from N8N_API_KEY (or the repo's .env, which is gitignored).

Usage:
    python n8n/import_workflows.py n8n/workflows/incident_response_v1.json [--activate]
    python n8n/import_workflows.py --list
"""

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[1]
BASE = os.getenv("N8N_BASE_URL", "http://localhost:5678").rstrip("/")

# Fields the public API accepts when creating a workflow. Anything else (pinData, meta, id,
# active, tags, versionId) is rejected with "must NOT have additional properties".
CREATE_FIELDS = ("name", "nodes", "connections", "settings")


def api_key() -> str:
    key = os.getenv("N8N_API_KEY", "").strip()
    if key:
        return key
    env_file = REPO / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("N8N_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("N8N_API_KEY not set and not found in .env")


def call(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{BASE}/api/v1{path}", data=data, method=method,
        headers={"X-N8N-API-KEY": api_key(), "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()[:600]


def existing_by_name(name: str):
    status, body = call("GET", "/workflows?limit=250")
    if status != 200 or not isinstance(body, dict):
        sys.exit(f"could not list workflows: HTTP {status} {body}")
    for workflow in body.get("data", []):
        if workflow.get("name") == name:
            return workflow
    return None


def import_workflow(path: pathlib.Path, activate: bool) -> dict:
    definition = json.loads(path.read_text(encoding="utf-8"))
    name = definition["name"]
    payload = {field: definition[field] for field in CREATE_FIELDS if field in definition}

    current = existing_by_name(name)
    if current:
        workflow_id = current["id"]
        # A workflow must be inactive to be updated.
        if current.get("active"):
            call("POST", f"/workflows/{workflow_id}/deactivate")
        status, body = call("PUT", f"/workflows/{workflow_id}", payload)
        action = "updated"
    else:
        status, body = call("POST", "/workflows", payload)
        action = "created"

    if status not in (200, 201):
        sys.exit(f"{action} failed for {name}: HTTP {status}\n{body}")

    workflow_id = body.get("id") or (current or {}).get("id")
    print(f"  {action}: {name}  (id={workflow_id}, {len(payload.get('nodes', []))} nodes)")

    if activate:
        status, body = call("POST", f"/workflows/{workflow_id}/activate")
        if status != 200:
            sys.exit(f"activation failed for {name}: HTTP {status}\n{body}")
        print(f"  activated: {name}")

    return {"id": workflow_id, "name": name, "active": bool(activate)}


def list_workflows() -> None:
    status, body = call("GET", "/workflows?limit=250")
    if status != 200:
        sys.exit(f"HTTP {status} {body}")
    rows = body.get("data", [])
    if not rows:
        print("  (no workflows)")
    for workflow in rows:
        flag = "ACTIVE  " if workflow.get("active") else "inactive"
        print(f"  [{flag}] {workflow['id']}  {workflow['name']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", type=pathlib.Path)
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        list_workflows()
        return
    if not args.files:
        parser.error("give at least one workflow JSON file, or --list")

    print(f"n8n at {BASE}")
    for path in args.files:
        import_workflow(path, args.activate)
    print("\ncurrent workflows:")
    list_workflows()


if __name__ == "__main__":
    main()
