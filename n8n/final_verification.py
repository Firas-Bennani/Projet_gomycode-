"""Feature-freeze verification: every scenario, three times, through the live stack.

Asserts what the demo depends on, per scenario:
  * the right incident type, and exactly one of it
  * severity and a fused confidence in a plausible band
  * the evidence a jury will be told about (machine evidence, smoke evidence, cyber rules)
  * the normal scenario stays silent
and reports which LLM path each incident took (Groq / Gemini / cached / template).

Usage:  python n8n/final_verification.py [--rounds 3]
Exit code 0 = everything passed all rounds.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _auth import auth_headers  # noqa: E402

BACKEND = "http://127.0.0.1:8000"

EXPECTED = {
    "machine_overheating": {
        "type": "MACHINE_OVERHEATING", "wait": 14,
        "severities": ("HIGH", "CRITICAL"), "evidence_from": "machine_agent",
        "must_contain": "M-04",
    },
    "fire": {
        "type": "INDUSTRIAL_FIRE", "wait": 14,
        "severities": ("HIGH", "CRITICAL"), "evidence_from": "temperature_agent",
        "must_contain": "SMOKE-B-01",
    },
    "cybersecurity": {
        "type": "CYBER_INTRUSION", "wait": 9,
        "severities": ("HIGH", "CRITICAL"), "evidence_from": "cyber_agent",
        "must_contain": "UNKNOWN-DEVICE-07",
    },
    "normal": {"type": None, "wait": 20},
}

failures = []
llm_paths = []


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BACKEND + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", **auth_headers()})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()[:200]
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


def check(label, ok, detail=""):
    print(f"    [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(label)
    return ok


def llm_path_of(reasoning: str) -> str:
    tail = reasoning.split("— enriched by")[-1] if "— enriched by" in reasoning else ""
    if "on Groq" in tail:
        return "groq"
    if "cached" in tail:
        return "cached"
    if "Gemini" in tail:
        return "gemini"
    if "template" in tail:
        return "template"
    return "none"


def run_scenario(name, spec, round_number):
    print(f"  {name} (round {round_number})")
    call("POST", "/api/demo/reset", {})
    time.sleep(2)
    call("POST", "/api/demo/scenario", {"scenario": name})
    time.sleep(spec["wait"])

    incidents = call("GET", "/api/incidents")[1].get("incidents", [])

    if spec["type"] is None:
        check("a quiet plant stays quiet", not incidents,
              ", ".join(i["type"] for i in incidents) or "none")
        return

    if not check(f"exactly one {spec['type']}", len(incidents) == 1,
                 f"{len(incidents)}: {[i['type'] for i in incidents]}"):
        return
    incident = incidents[0]
    check("correct type", incident["type"] == spec["type"], incident["type"])
    check("plausible severity", incident["severity"] in spec["severities"], incident["severity"])
    check("confidence is fused, not a literal",
          0.5 < incident["confidence"] < 0.99, str(incident["confidence"]))
    sources = {e["source"] for e in incident["evidence"]}
    check(f"evidence includes {spec['evidence_from']}", spec["evidence_from"] in sources,
          ", ".join(sorted(sources)))
    details = " ".join(e["detail"] for e in incident["evidence"])
    check(f"evidence names {spec['must_contain']}", spec["must_contain"] in details)

    path = llm_path_of(incident.get("ai_reasoning", ""))
    llm_paths.append((name, path))
    print(f"      llm path: {path} | severity {incident['severity']} | "
          f"confidence {incident['confidence']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()

    if call("GET", "/health")[0] != 200:
        print("backend is not running")
        return 1

    print("=" * 78)
    print(f"FEATURE-FREEZE VERIFICATION — {args.rounds} rounds of all four scenarios")
    print("=" * 78)

    for round_number in range(1, args.rounds + 1):
        print(f"\n--- round {round_number}/{args.rounds} ---")
        for name, spec in EXPECTED.items():
            run_scenario(name, spec, round_number)

    call("POST", "/api/demo/reset", {})

    print("\n" + "=" * 78)
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for label in sorted(set(failures)):
            print(f"  - {label}")
    else:
        print("ALL CHECKS PASSED IN EVERY ROUND")
    counts = {}
    for _, path in llm_paths:
        counts[path] = counts.get(path, 0) + 1
    print(f"LLM paths taken across {len(llm_paths)} incidents: {counts}")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
