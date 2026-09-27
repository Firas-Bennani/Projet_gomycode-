# n8n orchestration — how to bring it up

Owner: Engineer 1. Everything here is optional at runtime: **if n8n is not running, incident
detection is unaffected** and incidents keep the deterministic recommendations the backend
creates at detection time. The only visible difference is that the reasoning text is not
rewritten and no `recommendation_agent (n8n)` entries appear in the agent log.

---

## 1. Start n8n (host, no Docker)

Docker Desktop's engine would not start on the demo laptop and was quit to free RAM, so n8n
runs as a plain Node process. **Node 20.19+ / 22.9+ / 24.x** required (we use v24.15.0).

```powershell
$env:GENERIC_TIMEZONE="Europe/London"; $env:TZ="Europe/London"
$env:N8N_SECURE_COOKIE="false"; $env:N8N_DIAGNOSTICS_ENABLED="false"
$env:N8N_PERSONALIZATION_ENABLED="false"
$env:N8N_HOST="localhost"; $env:N8N_PORT="5678"; $env:N8N_PROTOCOL="http"
$env:WEBHOOK_URL="http://localhost:5678/"
npx --yes n8n@2.40.7
```

First run downloads ~1 GB into the npm cache and takes 10–15 min; afterwards it is cached.
n8n state (owner account, workflows, credentials, executions) lives in `C:\Users\<you>\.n8n`
and survives restarts, so the owner account and API key only need creating once.

Check it: <http://localhost:5678> should load, and

```powershell
curl http://localhost:5678/rest/settings
```

should return JSON.

### Docker alternative (more RAM, gives you pgvector too)

`docker-compose.yml` still declares `n8n` (5678) and `pgvector` (host port 5433). Use it on a
machine with RAM to spare: `docker compose up -d n8n pgvector`. Then set
`BACKEND_BASE_URL_FOR_N8N=http://host.docker.internal:8000` in `.env`.

## 2. One-time setup in the UI

1. <http://localhost:5678> → fill the **owner account** form (local only; no internet).
2. Avatar (bottom-left) → **Settings** → **n8n API** → **Create an API key**.
3. Put it in `.env` at the repo root (gitignored):

   ```
   N8N_API_KEY=eyJhbGciOi...
   ```

   The key is the raw JWT — it has **no** `n8n_api_` prefix.

## 3. Import and activate the workflows

Do not import by hand; use the script, which strips the fields the public API rejects and
fails loudly instead of leaving a half-configured workflow:

```powershell
..\.venv\Scripts\python.exe n8n\import_workflows.py n8n\workflows\incident_response_v1.json --activate
..\.venv\Scripts\python.exe n8n\import_workflows.py --list
```

**Import order and what to activate:**

| # | File | Activate? | Needs credentials |
|---|---|---|---|
| 1 | `incident_response_v1.json` | only as a fallback — **inactive** once v2 works | none |
| 2 | `rag_ingestion.json` *(Step 5)* | run manually once | embeddings model |
| 3 | `incident_response_v2.json` | ✅ **yes, this is the demo workflow** — deactivate v1 first | Gemini chat model ×2 + embeddings |
| 4 | `threat_watch.json` *(Step 10, cut)* | optional | chat model |

Only one of v1 / v2 may be active at a time: they share the webhook path `/webhook/incident`.

To pull UI edits back into the repo: `python n8n/export_workflows.py`.

## 4. Backend wiring

`.env` at the repo root (gitignored; see `.env.example` for all keys):

```
N8N_ENABLED=true
N8N_INCIDENT_WEBHOOK_URL=http://localhost:5678/webhook/incident
BACKEND_BASE_URL_FOR_N8N=http://127.0.0.1:8000
N8N_TIMEOUT_SECONDS=3
```

⚠️ **Use `127.0.0.1`, not `localhost`, for `BACKEND_BASE_URL_FOR_N8N`.** Node 18+ resolves
`localhost` to IPv6 `::1` first while uvicorn binds IPv4 `127.0.0.1` only, so n8n's HTTP
Request node fails with *"The service refused the connection - perhaps it is offline"*.

Set `N8N_ENABLED=false` to run the demo with no n8n at all (templates only).

## 4b. ⚠️ The vector store is IN MEMORY — re-run the ingestion after any n8n restart

The Simple Vector Store node states it plainly: *"For experimental use only: data is stored in
memory and will be lost if n8n restarts. Data may also be cleared if available memory gets low."*

So, **every time n8n restarts — and any time this laptop has been short of RAM — the RAG index is
empty until you re-run the ingestion.** It takes about 15 seconds:

1. <http://localhost:5678> → workflow **"RAG ingestion (procedures → Simple Vector Store)"**
2. click **Execute workflow** once, confirm it goes green and reports ~31 items.

Nothing breaks if you forget: the AI Agent also has `procedure_search`, an HTTP tool pointed at
the backend's keyword RAG, which needs no ingestion and cannot go stale. You would simply lose
semantic retrieval and keep keyword retrieval. That is exactly why the agent has both tools.

### Pre-demo checklist

Run through this before showing anything, in this order:

- [ ] Backend answers: `curl http://127.0.0.1:8000/health` → `{"status":"HEALTHY"}`
- [ ] n8n answers: <http://localhost:5678> loads
- [ ] `python n8n/import_workflows.py --list` shows **exactly one** active incident workflow
      (v2 for the LLM demo, v1 if you want the deterministic one)
- [ ] **Re-run the RAG ingestion** (above) — assume the store is empty
- [ ] `curl "http://127.0.0.1:8000/api/ai/n8n/rag?q=pressure%20limit&hazard=MACHINE_OVERHEATING"`
      returns hits, so the fallback retrieval is alive
- [ ] Frontend running: `cd frontend; npm run dev` → <http://localhost:5173>
- [ ] Gemini quota: the free tier allows **5 model calls per minute**. One incident costs about
      3. **Leave ~60 s between scenario runs**, or the agent hits HTTP 429 and silently falls
      back to the template (correct behaviour, but you lose the LLM wording on screen).
- [ ] Clear old n8n executions if you want an all-green Executions tab
- [ ] Close heavy applications — RAM pressure has killed background processes on this machine

## 5. Verify the whole round trip

```powershell
..\.venv\Scripts\python.exe n8n\e2e_test.py        # 15 checks, backend <-> n8n round trip
..\.venv\Scripts\python.exe n8n\gate1_verify.py    # 13 checks, live websocket + P5 + no re-open
..\.venv\Scripts\python.exe n8n\llm_roundtrip.py   # the LLM path, with latency
..\.venv\Scripts\python.exe n8n\llm_roundtrip.py --break    # prove the template fallback
```

15 checks, ~60 s: triggers `machine_overheating`, waits for the n8n execution, checks the
enrichment came back, authorises the pending actions through `/api/actions/{id}/authorize`
(the same call the dashboard button makes), then asserts the execution finished `success`,
verification passed and the incident resolved. Exit code 0 = acceptance met.

## 6. What the workflow does

`incident_response_v1.json` — 13 nodes, no LLM:

```
Webhook POST /webhook/incident   (responds immediately; the orchestrator never waits)
  -> Code: template recommendation   picks action ids from the payload's allowed_actions
  -> Code: validate against allowed_actions
  -> HTTP POST /api/ai/n8n/enrichment/{id}   includes {{ $execution.resumeUrl }}
  -> Wait (On Webhook Call, limit 10 min)    the owner's AUTHORIZE/CANCEL resumes this
  -> IF approved?
       yes -> Wait 15 s -> HTTP GET /api/ai/n8n/verify/{id}
                 -> IF verified? -> POST status RESOLVING
                                 -> POST status ESCALATED
       no  -> Code: cancel vs timeout -> POST status DISMISSED / ESCALATED
```

`incident_response_v2.json` — 22 nodes. Identical from "validate" onwards; the recommendation
comes from an **AI Agent** instead:

```
Webhook -> Code: build agent input (flattens the incident + the allowed_actions menu)
  -> AI Agent  (Gemini chat model, temperature 0.2, Structured Output Parser)
       tools: procedure_search       -> HTTP to /api/ai/n8n/rag   (always works)
              procedure_vector_search -> Simple Vector Store      (needs ingestion)
       on error -> Code: deterministic template  (v1's logic, byte for byte)
  -> Code: validate against allowed_actions -> ... identical to v1 ...
```

Three Gemini nodes need the credential: the agent's chat model, the **vector-store tool's own**
chat model (n8n flags the tool red without one), and the embeddings node. Models in use:
`models/gemini-3.8-flash` for chat, `models/gemini-embedding-001` for embeddings.
`models/gemini-2.5-flash` returns 404 *"no longer available to new users"* and
`models/text-embedding-004` was not available for this key.

Two safety properties worth stating to a jury:

- **The workflow can only propose actions from `backend/ai/actions_catalog.py`.** The backend
  re-validates every id and reads the risk level and the "needs a human" flag from the
  catalogue, so a model cannot invent an action or downgrade a HIGH-risk one.
- **Confidence is never set by the workflow.** It comes from sensor fusion at detection time;
  the enrichment only supplies wording.
