"""Warm the LLM answer cache: capture one real Gemini answer per hazard type.

Why: on the free tier only 1 of 5 live attempts succeeded (docs/ai/METRICS.md §2). The cache
turns that into a demo that always shows LLM-quality wording — a live answer when Google
cooperates, a clearly-labelled cached one when it does not.

Respects the 5-requests-per-minute quota by waiting between attempts, and retries each hazard
type until it gets a genuinely live answer or runs out of attempts.

Usage:
    python n8n/warm_llm_cache.py
    python n8n/warm_llm_cache.py --attempts 4 --gap 70
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

BACKEND = "http://127.0.0.1:8000"

SCENARIOS = [
    ("machine_overheating", "MACHINE_OVERHEATING", 14),
    ("fire", "INDUSTRIAL_FIRE", 14),
    ("cybersecurity", "CYBER_INTRUSION", 9),
]


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BACKEND + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()[:200]
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


def cached_types():
    return set(call("GET", "/api/ai/n8n/llm-cache")[1].get("types_cached", []))


def attempt(scenario, wait):
    call("POST", "/api/demo/reset", {})
    time.sleep(1.5)
    call("POST", "/api/demo/scenario", {"scenario": scenario})
    time.sleep(wait)

    incidents = call("GET", "/api/incidents")[1].get("incidents") or []
    if not incidents:
        return None, "no incident was created"
    incident = incidents[0]

    # Give the agent time: a live Gemini answer took ~38 s end to end when it worked.
    deadline = time.time() + 75
    while time.time() < deadline:
        current = call("GET", f"/api/incidents/{incident['id']}")[1]
        reasoning = current.get("ai_reasoning", "")
        if "— enriched by" in reasoning:
            tail = reasoning.split("— enriched by")[-1]
            if "template fallback" in tail:
                return False, tail.strip()[:90]
            if "cached" in tail:
                return False, "replayed from cache (not a new live answer)"
            return True, tail.strip()[:90]
        time.sleep(3)
    return None, "no enrichment arrived within 75 s"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--gap", type=int, default=70, help="seconds between attempts (quota)")
    args = parser.parse_args()

    if call("GET", "/health")[0] != 200:
        print("backend is not running")
        return 1

    print(f"already cached: {sorted(cached_types()) or 'nothing'}\n")

    for scenario, incident_type, wait in SCENARIOS:
        if incident_type in cached_types():
            print(f"{incident_type}: already cached, skipping")
            continue
        for number in range(1, args.attempts + 1):
            print(f"{incident_type}: attempt {number}/{args.attempts} ...", flush=True)
            live, detail = attempt(scenario, wait)
            if live:
                print(f"  LIVE answer captured -> {detail}")
                break
            print(f"  not live ({detail})")
            if number < args.attempts:
                print(f"  waiting {args.gap}s for the quota window", flush=True)
                time.sleep(args.gap)
        else:
            print(f"  {incident_type}: gave up after {args.attempts} attempts")

    call("POST", "/api/demo/reset", {})
    status = call("GET", "/api/ai/n8n/llm-cache")[1]
    print("\n=== cache contents ===")
    for key, entry in status.get("entries", {}).items():
        print(f"  {key:<22} {entry.get('produced_by')} at {entry.get('cached_at')}")
        print(f"                         actions={entry.get('action_ids')} sources={entry.get('sources')}")
    missing = {t for _, t, _ in SCENARIOS} - set(status.get("types_cached", []))
    print(f"\nwarmed: {len(status.get('types_cached', []))}/3" +
          (f"  still missing: {sorted(missing)}" if missing else "  (all three)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
