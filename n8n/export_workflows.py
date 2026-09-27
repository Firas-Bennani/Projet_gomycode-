"""Export workflows from the running n8n back into n8n/workflows/.

The n8n UI is the authoritative editor, so after any change there this pulls the definition
back into the repo. Output is trimmed to the fields the public API accepts on import
(name/nodes/connections/settings), so an exported file can be re-imported unchanged.

Usage:
    python n8n/export_workflows.py                  # every workflow
    python n8n/export_workflows.py "Incident Response v1 (deterministic, no LLM)"
"""

import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "n8n" / "workflows"
BASE = os.getenv("N8N_BASE_URL", "http://localhost:5678").rstrip("/")

KEEP = ("name", "nodes", "connections", "settings")


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


def get(path):
    request = urllib.request.Request(
        f"{BASE}/api/v1{path}", headers={"X-N8N-API-KEY": api_key()})
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        sys.exit(f"HTTP {error.code}: {error.read().decode()[:300]}")


def filename_for(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    # Keep the names the repo already uses.
    if slug.startswith("incident_response_v1"):
        return "incident_response_v1.json"
    if slug.startswith("incident_response_v2"):
        return "incident_response_v2.json"
    if "rag" in slug and "ingest" in slug:
        return "rag_ingestion.json"
    if "threat" in slug:
        return "threat_watch.json"
    return f"{slug}.json"


def main() -> None:
    wanted = set(sys.argv[1:])
    workflows = get("/workflows?limit=250").get("data", [])
    if not workflows:
        sys.exit("no workflows in n8n")

    for summary in workflows:
        if wanted and summary["name"] not in wanted:
            continue
        full = get(f"/workflows/{summary['id']}")
        trimmed = {field: full[field] for field in KEEP if field in full}
        target = OUT_DIR / filename_for(full["name"])
        target.write_text(json.dumps(trimmed, indent=2) + "\n", encoding="utf-8")
        print(f"  exported {full['name']!r}"
              f" ({len(trimmed.get('nodes', []))} nodes, active={summary.get('active')})"
              f" -> {target.relative_to(REPO)}")


if __name__ == "__main__":
    main()
