"""Record the n8n decision flow for the demo video, unattended.

Two phases, either of which can be run alone:

**setup** drives the backend through one clean approved run: reset, trigger
``machine_overheating``, wait for the incident and its n8n enrichment, authorise STOP_MACHINE as
the owner, then wait until the incident is RESOLVED *and* the n8n execution has finished SUCCESS.
That last condition matters: the interesting path only exists in an execution that went
``Approved? true -> Wait 15 s -> GET verify -> Verified? true -> POST status RESOLVING``, so the
script waits for the real thing rather than recording whatever execution happens to be newest.

**record** opens that execution in a real browser with Playwright and walks it: fit the view, open
the AI agent's output, open the wait node, trail the mouse down to the resolving call. Every step
is wrapped: a selector that changed in an n8n version must not cost the whole recording, so a
failed step is reported and skipped while the video keeps rolling.

Credentials are read from the environment and never written to the repo:

    N8N_EMAIL / N8N_PASSWORD      the n8n owner login (the UI needs a browser session; the
                                  public API key cannot open the executions view). Not needed
                                  with --use-chrome-profile, which reuses the session already in
                                  your Chrome profile and asks for no password at all.
    N8N_API_KEY                   read from .env if unset, as the other n8n scripts do
    COPILOT_USER / COPILOT_PASSWORD   the backend owner, via n8n/_auth.py

Usage:
    python scripts/video/record_n8n.py                     # setup, then record, then convert
    python scripts/video/record_n8n.py --execution-id 123   # skip setup, record that execution
    python scripts/video/record_n8n.py --setup-only
    python scripts/video/record_n8n.py --no-caption
    python scripts/video/record_n8n.py --execution-id 114 --use-chrome-profile   # no password
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "n8n"))

OUT_DIR = REPO / "docs" / "video"
FINAL_MP4 = OUT_DIR / "n8n_clip.mp4"
CAPTION = "n8n: traceable AI decision · human approval built in"

BACKEND = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
N8N = os.getenv("N8N_BASE_URL", "http://localhost:5678").rstrip("/")

#: The workflow that owns the approval path. v1 is the deterministic one and has no AI agent.
WORKFLOW_NAME_HINT = "v2"


def log(message: str) -> None:
    print(f"[record_n8n] {message}", flush=True)


# --------------------------------------------------------------------- the two APIs

def _json(request, timeout=30):
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as error:
        return {"_error": error.code, "_body": error.read().decode()[:200]}
    except Exception as exc:  # noqa: BLE001
        return {"_error": 0, "_body": f"{type(exc).__name__}: {exc}"}


def backend(method: str, path: str, body=None):
    from _auth import auth_headers

    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        BACKEND + path, data=data, method=method,
        headers={"Content-Type": "application/json", **auth_headers()})
    return _json(request)


def n8n_api_key() -> str:
    key = os.getenv("N8N_API_KEY", "").strip()
    if key:
        return key
    env_file = REPO / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("N8N_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("N8N_API_KEY not set and not found in .env")


def n8n_get(path: str):
    return _json(urllib.request.Request(f"{N8N}/api/v1{path}",
                                        headers={"X-N8N-API-KEY": n8n_api_key()}))


# --------------------------------------------------------------------- phase 1: the execution

def newest_execution_id() -> int:
    """Highest execution id right now, so the setup can tell its own run from the old ones."""
    data = n8n_get("/executions?limit=1")
    items = data.get("data") or []
    return int(items[0]["id"]) if items else 0


def approved_execution(after_id: int, workflow_id: str, deadline: float):
    """An execution newer than ``after_id`` that finished SUCCESS on the approved path."""
    while time.time() < deadline:
        data = n8n_get(f"/executions?workflowId={workflow_id}&status=success&limit=20")
        for item in data.get("data") or []:
            if int(item["id"]) > after_id:
                return item
        time.sleep(3)
    return None


def find_workflow() -> tuple:
    data = n8n_get("/workflows?limit=50")
    workflows = data.get("data") or []
    if not workflows:
        sys.exit(f"no workflows returned by the n8n API: {data}")
    preferred = [w for w in workflows if WORKFLOW_NAME_HINT in w.get("name", "")
                 and w.get("active")]
    chosen = (preferred or [w for w in workflows if w.get("active")] or workflows)[0]
    return chosen["id"], chosen.get("name", "?")


def wait_for(predicate, what: str, timeout: float, interval: float = 2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    log(f"gave up waiting for {what} after {timeout:.0f}s")
    return None


def setup_execution(workflow_id: str) -> str:
    """Drive one clean approved run and return its n8n execution id."""
    before = newest_execution_id()
    log(f"newest execution before the run: {before or 'none'}")

    backend("POST", "/api/demo/reset", {})
    time.sleep(2)
    backend("POST", "/api/demo/scenario", {"scenario": "machine_overheating"})
    log("machine_overheating triggered; waiting for the incident")

    incident = wait_for(
        lambda: next((i for i in (backend("GET", "/api/incidents").get("incidents") or [])
                      if i.get("type") == "MACHINE_OVERHEATING"), None),
        "the overheating incident", timeout=60)
    if not incident:
        sys.exit("no incident was created; is the simulator running?")
    incident_id = incident["id"]
    log(f"incident {incident_id}")

    # The enrichment is what makes the AI agent node worth opening in the video.
    enriched = wait_for(
        lambda: "enriched by" in (backend("GET", f"/api/incidents/{incident_id}")
                                  .get("ai_reasoning") or ""),
        "the n8n enrichment", timeout=90, interval=3)
    log("enrichment arrived" if enriched else "no enrichment (recording the flow anyway)")

    stop = wait_for(
        lambda: next((a for a in (backend("GET", "/api/actions").get("actions") or [])
                      if a.get("incident_id") == incident_id
                      and a.get("action_type") == "STOP_MACHINE"), None),
        "a STOP_MACHINE action", timeout=45)
    if not stop:
        sys.exit("no STOP_MACHINE action to authorise")

    log(f"authorising {stop['id']} as firas")
    backend("POST", f"/api/actions/{stop['id']}/authorize", {"authorized_by": "firas"})

    resolved = wait_for(
        lambda: backend("GET", f"/api/incidents/{incident_id}").get("status") == "RESOLVED",
        "the incident to reach RESOLVED", timeout=120, interval=3)
    log("incident RESOLVED" if resolved else "incident did not reach RESOLVED in time")

    execution = approved_execution(before, workflow_id, deadline=time.time() + 90)
    if not execution:
        sys.exit("no new SUCCESS execution appeared for this run")
    log(f"execution {execution['id']} finished {execution.get('status')}")
    return str(execution["id"])


# --------------------------------------------------------------------- phase 2: the recording

def chrome_profile_dir() -> str:
    local = os.getenv("LOCALAPPDATA") or str(pathlib.Path.home() / "AppData" / "Local")
    path = pathlib.Path(local) / "Google" / "Chrome" / "User Data"
    if not path.is_dir():
        sys.exit(f"no Chrome profile at {path}")
    return str(path)


def record(workflow_id: str, execution_id: str, use_chrome_profile: bool = False) -> pathlib.Path:
    from playwright.sync_api import sync_playwright

    email = os.getenv("N8N_EMAIL", "").strip()
    password = os.getenv("N8N_PASSWORD", "").strip()
    # Two ways in. Reusing the Chrome profile you are already signed in with needs no password at
    # all, which is the better option when the only alternative is typing one into a shell that
    # keeps history. It requires Chrome to be fully closed, because Chrome locks its profile.
    if not (email and password) and not use_chrome_profile:
        sys.exit("either set N8N_EMAIL and N8N_PASSWORD, or pass --use-chrome-profile "
                 "(with Chrome closed) to reuse the session you already have")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    before = set(OUT_DIR.glob("*.webm"))

    def step(description: str, action):
        """Never let one changed selector cost the whole recording."""
        try:
            action()
            log(f"  ok: {description}")
        except Exception as exc:  # noqa: BLE001
            log(f"  SKIPPED {description}: {type(exc).__name__}: {str(exc)[:120]}")

    video = {"record_video_dir": str(OUT_DIR),
             "record_video_size": {"width": 1920, "height": 1080}}
    shape = {"viewport": {"width": 1920, "height": 1080}, "device_scale_factor": 1.25}

    with sync_playwright() as p:
        launch = {"headless": False, "slow_mo": 400, "args": ["--start-maximized"]}
        browser = None

        if use_chrome_profile:
            log("reusing your Chrome profile — Chrome must be closed or this will fail")
            context = p.chromium.launch_persistent_context(
                chrome_profile_dir(), channel="chrome", **launch, **shape, **video)
        else:
            try:
                browser = p.chromium.launch(**launch)
                log("launched bundled chromium")
            except Exception:
                browser = p.chromium.launch(channel="chrome", **launch)
                log("launched installed Chrome")
            context = browser.new_context(**shape, **video)

        page = context.pages[0] if context.pages else context.new_page()

        try:
            if use_chrome_profile:
                log("skipping the login form: the profile should already hold a session")
            else:
                log("signing in to n8n")
                page.goto(f"{N8N}/signin", wait_until="domcontentloaded")
                step("fill the login form", lambda: (
                    page.fill("input[type='email'], input[name='email']", email),
                    page.fill("input[type='password'], input[name='password']", password),
                    page.keyboard.press("Enter"),
                    page.wait_for_load_state("networkidle", timeout=30000),
                ))

            url = f"{N8N}/workflow/{workflow_id}/executions/{execution_id}"
            log(f"opening {url}")
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            # Fit the whole path into frame. The keyboard shortcut is stable across versions;
            # the zoom-to-fit button is the fallback.
            def fit():
                page.mouse.move(960, 540)
                page.keyboard.press("1")
                page.wait_for_timeout(600)
            step("fit view", fit)
            step("hold on the green path", lambda: page.wait_for_timeout(3000))

            def open_node(label: str, hold_ms: int):
                node = page.locator(f"[data-test-id='canvas-node']:has-text('{label}')").first
                node.dblclick(timeout=8000)
                page.wait_for_timeout(hold_ms)
                page.keyboard.press("Escape")
                page.wait_for_timeout(700)

            step("open Recommendation AI Agent (output: what / why / sources)",
                 lambda: open_node("Recommendation AI Agent", 3500))
            step("open Wait for owner decision",
                 lambda: open_node("Wait for owner decision", 2200))

            # Trail the mouse down the path to the resolving call, then rest on it.
            def trail():
                for x, y in [(620, 430), (900, 500), (1180, 560), (1420, 610)]:
                    page.mouse.move(x, y, steps=25)
                    page.wait_for_timeout(350)
                target = page.locator(
                    "[data-test-id='canvas-node']:has-text('RESOLVING')").first
                box = target.bounding_box(timeout=5000)
                if box:
                    page.mouse.move(box["x"] + box["width"] / 2,
                                    box["y"] + box["height"] / 2, steps=30)
                page.wait_for_timeout(2200)
            step("trail the mouse to POST status RESOLVING", trail)
        finally:
            context.close()   # flushes the video file
            if browser:
                browser.close()

    produced = sorted(set(OUT_DIR.glob("*.webm")) - before,
                      key=lambda p: p.stat().st_mtime)
    if not produced:
        sys.exit("playwright produced no video file")
    return produced[-1]


# --------------------------------------------------------------------- phase 3: ffmpeg

def ffmpeg_binary() -> str:
    for candidate in ("ffmpeg",):
        try:
            subprocess.run([candidate, "-version"], capture_output=True, check=True)
            return candidate
        except Exception:  # noqa: BLE001
            pass
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        sys.exit("no ffmpeg: pip install imageio-ffmpeg")


def convert(source: pathlib.Path, caption: bool) -> None:
    ffmpeg = ffmpeg_binary()
    filters = ["scale=1920:1080:force_original_aspect_ratio=decrease",
               "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black"]
    if caption:
        text = CAPTION.replace(":", r"\:").replace("'", "")
        filters.append(
            f"drawtext=text='{text}':fontcolor=white:fontsize=34:"
            f"box=1:boxcolor=black@0.65:boxborderw=18:x=(w-text_w)/2:y=h-110")
    command = [ffmpeg, "-y", "-i", str(source), "-vf", ",".join(filters),
               "-c:v", "libx264", "-preset", "medium", "-crf", "20",
               "-pix_fmt", "yuv420p", "-an", str(FINAL_MP4)]
    log("converting to H.264")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not FINAL_MP4.exists():
        log(result.stderr[-800:])
        sys.exit("ffmpeg failed")


def duration_of(path: pathlib.Path) -> str:
    ffmpeg = ffmpeg_binary()
    result = subprocess.run([ffmpeg, "-i", str(path)], capture_output=True, text=True)
    for line in result.stderr.splitlines():
        if "Duration:" in line:
            return line.strip().split("Duration:")[1].split(",")[0].strip()
    return "unknown"


# --------------------------------------------------------------------- entry point

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-id", help="record this execution instead of creating one")
    parser.add_argument("--workflow-id", help="override the workflow id")
    parser.add_argument("--setup-only", action="store_true")
    parser.add_argument("--no-caption", action="store_true")
    parser.add_argument("--use-chrome-profile", action="store_true",
                        help="reuse the Chrome profile already signed in to n8n (Chrome must be "
                             "closed); no password needed")
    args = parser.parse_args()

    workflow_id = args.workflow_id
    if not workflow_id:
        workflow_id, name = find_workflow()
        log(f"workflow {workflow_id} ({name})")

    execution_id = args.execution_id
    if not execution_id:
        execution_id = setup_execution(workflow_id)
    if args.setup_only:
        log(f"execution id: {execution_id}")
        return 0

    raw = record(workflow_id, execution_id, use_chrome_profile=args.use_chrome_profile)
    log(f"raw video: {raw.name} ({duration_of(raw)})")
    convert(raw, caption=not args.no_caption)
    log(f"done: {FINAL_MP4}  duration {duration_of(FINAL_MP4)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
