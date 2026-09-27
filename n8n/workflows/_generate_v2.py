"""Generate the Step 5 workflows: incident_response_v2.json and rag_ingestion.json.

v2 replaces v1's deterministic Code node with an **AI Agent** (Google Gemini chat model +
Structured Output Parser), given two retrieval tools:

* ``procedure_search`` — an HTTP Request Tool calling the backend's ``/api/ai/n8n/rag``.
  Keyword retrieval over ``backend/ai/rag/corpus``, with section-level citations. Always works.
* ``procedure_vector_search`` — n8n's Simple Vector Store. Faster and semantic, but the node
  itself warns it is "for experimental use only: data is stored in memory and will be lost if
  n8n restarts, data may also be cleared if available memory gets low". Populated by
  ``rag_ingestion.json``.

Everything downstream of the recommendation is identical to v1, and the agent's error output
falls back to the same deterministic template v1 uses, so a missing or broken LLM credential
degrades to v1 behaviour instead of breaking the demo.

Node types and version numbers were read out of the installed
``@n8n/n8n-nodes-langchain`` package rather than guessed.

Run:  python n8n/workflows/_generate_v2.py
"""

import json
import pathlib
import uuid

HERE = pathlib.Path(__file__).parent
OUT_V2 = HERE / "incident_response_v2.json"
OUT_INGEST = HERE / "rag_ingestion.json"

#: Shared between the ingestion workflow and the retriever tool, so both address the same store.
MEMORY_KEY = "copilot_procedures"

# Corrected on 2026-09-27 from what actually works with Firas's key (his UI fixes, then
# exported back into the repo — the export is authoritative, this generator only bootstraps).
# gemini-2.5-flash returned 404 "no longer available to new users"; Google named
# gemini-3.8-flash as the replacement.
GEMINI_CHAT_MODEL = "models/gemini-3.8-flash"
# The embeddings node's own default is already models/gemini-embedding-001, and n8n omits
# parameters equal to their default when exporting. Leaving modelName unset keeps the generated
# file byte-identical to the export instead of churning the diff on every round trip.
# models/text-embedding-004 was NOT available for this key.


def nid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"copilot/v2/{name}"))


# --------------------------------------------------------------------------- v2 node names
WEBHOOK = "Incident webhook"
PREPARE = "Build agent input"
AGENT = "Recommendation AI Agent"
MODEL = "Google Gemini Chat Model"
PARSER = "Structured Output Parser"
TOOL_HTTP = "Procedure search (backend RAG)"
TOOL_VECTOR = "Procedure search (vector store)"
VECTOR_RETRIEVER = "Simple Vector Store (retrieve)"
TOOL_VECTOR_MODEL = "Google Gemini Chat Model1"   # the tool's own required model
EMBEDDINGS_RETRIEVE = "Embeddings Gemini (retrieve)"
FALLBACK = "Template recommendation (LLM unavailable)"
VALIDATE = "Validate against allowed_actions"
ENRICH = "POST enrichment"
WAIT_DECISION = "Wait for owner decision (10 min)"
APPROVED = "Approved?"
WAIT_SETTLE = "Wait 15s for the plant to settle"
VERIFY = "GET verify"
VERIFIED = "Verified?"
STATUS_RESOLVING = "POST status RESOLVING"
STATUS_ESCALATED = "POST status ESCALATED"
OUTCOME = "Outcome without approval"
STATUS_OUTCOME = "POST status (cancel or timeout)"

SRC = f"$('{WEBHOOK}').first().json.body"

# The schema the agent must fill. Deliberately small: ids only for actions, never free text.
OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["what", "why", "impact", "prediction", "recommended_action_ids", "sources"],
    "properties": {
        "what": {"type": "string", "description": "One sentence naming the hazard, the asset and the zone."},
        "why": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Each corroborating reading, quoting the actual value and its threshold.",
        },
        "impact": {"type": "string", "description": "Who and what is at risk, with the worker count."},
        "prediction": {
            "type": "string",
            "description": "What happens without intervention. Phrase as a risk, never as a certainty.",
        },
        "recommended_action_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ids copied EXACTLY from allowed_actions. Never invent an id.",
        },
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "document": {"type": "string"},
                    "section": {"type": "string"},
                },
            },
            "description": "Procedure sections actually retrieved, e.g. SOP-M04 §4.2.",
        },
    },
}

SYSTEM_MESSAGE = """You are the recommendation agent of an industrial safety copilot. A deterministic detection layer has already decided that an incident exists and how confident it is. Your job is only to explain it and to choose the response from a fixed catalogue.

Hard rules:
1. Choose actions ONLY by copying ids from the allowed_actions list in the user message. Never invent an id, never invent an action, never describe an action that is not in that list. Ids you make up are rejected by the backend and wasted.
2. You do NOT set risk levels, you do NOT decide what needs human approval, and you do NOT set the confidence figure. Those come from the catalogue and from sensor fusion.
3. Cite the procedure sections you actually retrieved, using the citation string the tool returns (for example "SOP-M04 §4.2"). If you retrieved nothing, return an empty sources array. Never cite a section you did not retrieve.
4. Quote the real readings from the evidence. Never introduce numbers that are not in the input.
5. Never claim certainty. Write "risk of", "expected to", "consistent with". A prediction is a risk assessment, not a fact.
6. Always search the procedures before recommending. Use procedure_search; you may also use procedure_vector_search. Prefer the order of actions the procedure specifies.

Use the tools, then answer with the structured object only.

Example of a good answer for a machine overheating incident:
{"what":"Hydraulic overpressure and over-temperature developing on M-04 in ZONE_B","why":["M-04 pressure 8.32 bar, over its 8.0 bar operating limit","M-04 body temperature 82.9 °C, at or over its 80 °C limit","Ambient TEMP-B-01 at 47.9 °C against a 50 °C critical threshold"],"impact":"3 people exposed in ZONE_B (W23, W41, W52) and unplanned loss of M-04","prediction":"Risk of hydraulic line rupture and spindle seizure if the trend continues","recommended_action_ids":["stop_machine","evacuate_zone","activate_cooling"],"sources":[{"document":"SOP-M04","section":"§4.2"},{"document":"EVAC-PROC","section":"§2"}]}"""

PREPARE_CODE = """
// Flatten the incident into one compact prompt, and keep the fields the rest of the workflow
// needs. Everything the agent is allowed to choose from is listed explicitly.
const input = $input.first().json;
const payload = input.body || input;
const incident = payload.incident || {};
const allowed = payload.allowed_actions || [];
const evidence = payload.evidence || [];
const workers = payload.workers || [];

const allowedLines = allowed.map(a =>
  `- id: ${a.id} | ${a.label} | target ${a.target} | risk ${a.risk}` +
  `${a.requires_confirmation ? ' | needs owner approval' : ' | automatic'}`).join('\\n');

const prompt = [
  `INCIDENT ${payload.incident_id}`,
  `type: ${incident.type}`,
  `zone: ${incident.zone}`,
  `severity at detection: ${incident.severity}`,
  `fused confidence: ${Math.round((incident.confidence || 0) * 100)}% (set by sensor fusion, not by you)`,
  `affected assets: ${(incident.affected_assets || []).join(', ') || 'none recorded'}`,
  `people in the zone: ${workers.length ? workers.map(w => `${w.id} (${w.role})`).join(', ') : 'none detected'}`,
  '',
  'EVIDENCE (the only readings you may quote):',
  ...evidence.map(e => `- ${e.source}: ${e.detail}`),
  '',
  'allowed_actions (choose ids from this list only):',
  allowedLines || '- (none)',
].join('\\n');

return [{
  json: {
    incident_id: payload.incident_id,
    backend_base_url: payload.backend_base_url,
    allowed_action_ids: allowed.map(a => a.id),
    incident_type: incident.type,
    prompt,
  },
}];
""".strip()

FALLBACK_CODE = """
// The AI Agent's error output lands here: no credential, quota exhausted, malformed structured
// output, or the model simply unavailable. Produce exactly the same shape deterministically so
// the rest of the workflow cannot tell the difference. This is v1's behaviour.
const src = $('""" + WEBHOOK + """').first().json.body;
const incident = src.incident || {};
const allowed = src.allowed_actions || [];
const evidence = src.evidence || [];
const workers = src.workers || [];

const allowedIds = allowed.map(a => a.id);
const byHazard = {
  MACHINE_OVERHEATING: ['stop_machine', 'evacuate_zone', 'activate_cooling'],
  INDUSTRIAL_FIRE: ['trigger_alarm', 'evacuate_zone', 'close_door', 'activate_suppression'],
  CYBER_INTRUSION: ['vlan_quarantine', 'isolate_device'],
};
const chosen = (byHazard[incident.type] || allowedIds).filter(id => allowedIds.includes(id));
const hazard = String(incident.type || 'hazard').replace(/_/g, ' ').toLowerCase();
const assets = (incident.affected_assets || []).join(', ') || 'the affected zone';

return [{
  json: {
    incident_id: src.incident_id,
    backend_base_url: src.backend_base_url,
    allowed_action_ids: allowedIds,
    what: `${hazard} affecting ${assets} in ${incident.zone}`,
    why: evidence.map(e => `${e.source}: ${e.detail}`),
    impact: workers.length
      ? `${workers.length} person(s) exposed in ${incident.zone}. Unplanned loss of ${assets}.`
      : `No personnel currently detected in ${incident.zone}. Unplanned loss of ${assets}.`,
    prediction: `Risk of the condition on ${assets} continuing to worsen without intervention.`,
    recommended_action_ids: chosen,
    sources: [],
    produced_by: 'n8n template fallback (language model unavailable)',
    fallback: true,
  },
}];
""".strip()

VALIDATE_CODE = """
// One entry point for both paths: the agent's structured output, or the template fallback.
// Reads the original payload off the trigger node, because item pairing is not reliable after
// an agent call. Belt and braces on the ids: the backend validates them against the catalogue
// too, but an id that never leaves n8n is one fewer rejection to explain.
const src = $('""" + WEBHOOK + """').first().json.body;
const item = $input.first().json;
const fromAgent = item.output && typeof item.output === 'object' ? item.output : null;
const body = fromAgent || item;

const allowed = new Set((src.allowed_actions || []).map(a => a.id));
const proposed = Array.isArray(body.recommended_action_ids) ? body.recommended_action_ids : [];
const validated = [...new Set(proposed.map(id => String(id).trim().toLowerCase()))]
  .filter(id => allowed.has(id));
const rejected = [...new Set(proposed)].filter(id => !allowed.has(String(id).trim().toLowerCase()));

return [{
  json: {
    incident_id: src.incident_id,
    backend_base_url: src.backend_base_url,
    what: body.what || '',
    why: Array.isArray(body.why) ? body.why : [],
    impact: body.impact || '',
    prediction: body.prediction || '',
    sources: Array.isArray(body.sources) ? body.sources : [],
    recommended_action_ids: validated,
    rejected_action_ids: rejected,
    produced_by: body.produced_by || ('""" + GEMINI_CHAT_MODEL + """' + ' via n8n AI Agent'),
    fallback: body.fallback === true,
  },
}];
""".strip()

OUTCOME_CODE = """
// The Wait node resumes either because the owner decided, or because its 10 minute limit expired.
const decision = ($json.body && $json.body.decision) || $json.decision || 'timeout';
const cancelled = decision === 'cancel';
return [{
  json: {
    decision,
    status: cancelled ? 'DISMISSED' : 'ESCALATED',
    note: cancelled
      ? 'Owner cancelled the recommended action in the dashboard; incident dismissed by human decision.'
      : 'No owner decision in 10 min -> escalated. Nobody acted on the recommendation inside the '
        + 'approval window, so this incident needs a human now.',
  },
}];
""".strip()


def code_node(name, code, position):
    return {"parameters": {"jsCode": code}, "id": nid(name), "name": name,
            "type": "n8n-nodes-base.code", "typeVersion": 2, "position": position}


def http_node(name, method, url, position, json_body=None, on_error=None):
    parameters = {"method": method, "url": url, "options": {}}
    if json_body is not None:
        parameters.update({"sendBody": True, "specifyBody": "json", "jsonBody": json_body})
    node = {"parameters": parameters, "id": nid(name), "name": name,
            "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": position}
    if on_error:
        node["onError"] = on_error
    return node


def if_string_equals(name, left, expected, position):
    return {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose",
                            "version": 2},
                "conditions": [{"id": nid(name + ":cond"), "leftValue": left,
                                "rightValue": expected,
                                "operator": {"type": "string", "operation": "equals"}}],
                "combinator": "and",
            },
            "looseTypeValidation": True,
            "options": {},
        },
        "id": nid(name), "name": name, "type": "n8n-nodes-base.if",
        "typeVersion": 2.2, "position": position,
    }


def main_link(target, index=0):
    return [{"node": target, "type": "main", "index": index}]


def ai_link(target, connection_type):
    return [{"node": target, "type": connection_type, "index": 0}]


# =========================================================== incident_response_v2

def build_v2():
    nodes = [
        {
            "parameters": {"httpMethod": "POST", "path": "incident",
                           "responseMode": "onReceived", "options": {}},
            "id": nid(WEBHOOK), "name": WEBHOOK, "type": "n8n-nodes-base.webhook",
            "typeVersion": 2, "position": [-460, 300], "webhookId": nid(WEBHOOK + ":hook"),
        },
        code_node(PREPARE, PREPARE_CODE, [-240, 300]),
        {
            "parameters": {
                "promptType": "define",
                "text": "={{ $json.prompt }}",
                "hasOutputParser": True,
                "options": {"systemMessage": SYSTEM_MESSAGE, "maxIterations": 3},
            },
            "id": nid(AGENT), "name": AGENT,
            "type": "@n8n/n8n-nodes-langchain.agent", "typeVersion": 2.2,
            "position": [-20, 300],
            # A missing credential, an exhausted quota or malformed output must not break the
            # demo: send it down the error branch to the deterministic template instead.
            "onError": "continueErrorOutput",
        },
        {
            "parameters": {"modelName": GEMINI_CHAT_MODEL,
                           "options": {"temperature": 0.2}},
            "id": nid(MODEL), "name": MODEL,
            "type": "@n8n/n8n-nodes-langchain.lmChatGoogleGemini", "typeVersion": 1.1,
            "position": [-120, 540],
        },
        {
            "parameters": {"jsonSchema": json.dumps(OUTPUT_SCHEMA, indent=2)},
            "id": nid(PARSER), "name": PARSER,
            "type": "@n8n/n8n-nodes-langchain.outputParserStructured", "typeVersion": 1.1,
            "position": [140, 540],
        },
        {
            "parameters": {
                "toolDescription": "Search the plant's written procedures (SOP-M04, "
                                   "FIRE-EP-03, EVAC-PROC, OT-CYBER-PB, MAINT-PLAN) and return "
                                   "the matching sections with their citation strings. Always "
                                   "use this before recommending actions. Input: a short query "
                                   "describing the hazard.",
                "url": f"={{{{ $('{PREPARE}').first().json.backend_base_url }}}}/api/ai/n8n/rag",
                "sendQuery": True,
                "specifyQuery": "keypair",
                "parametersQuery": {
                    "values": [
                        {"name": "q", "valueProvider": "modelRequired"},
                        {"name": "hazard",
                         "valueProvider": "fieldValue",
                         "value": f"={{{{ $('{PREPARE}').first().json.incident_type }}}}"},
                        {"name": "limit", "valueProvider": "fieldValue", "value": "4"},
                    ]
                },
                "options": {},
            },
            "id": nid(TOOL_HTTP), "name": TOOL_HTTP,
            "type": "@n8n/n8n-nodes-langchain.toolHttpRequest", "typeVersion": 1.1,
            "position": [340, 540],
        },
        {
            "parameters": {
                "name": "procedure_vector_search",
                "description": "Semantic search over the same procedure corpus, using the "
                               "in-memory vector store. May be empty if n8n restarted; if it "
                               "returns nothing useful, use procedure_search instead.",
                "topK": 4,
            },
            "id": nid(TOOL_VECTOR), "name": TOOL_VECTOR,
            "type": "@n8n/n8n-nodes-langchain.toolVectorStore", "typeVersion": 1.1,
            "position": [560, 540],
        },
        {
            "parameters": {
                "mode": "retrieve",
                "memoryKey": {"__rl": True, "mode": "id", "value": MEMORY_KEY},
            },
            "id": nid(VECTOR_RETRIEVER), "name": VECTOR_RETRIEVER,
            "type": "@n8n/n8n-nodes-langchain.vectorStoreInMemory", "typeVersion": 1.2,
            "position": [560, 760],
        },
        {
            "parameters": {},   # modelName defaults to models/gemini-embedding-001
            "id": nid(EMBEDDINGS_RETRIEVE), "name": EMBEDDINGS_RETRIEVE,
            "type": "@n8n/n8n-nodes-langchain.embeddingsGoogleGemini", "typeVersion": 1,
            "position": [560, 960],
        },
        {
            # The vector-store TOOL requires its own language model to summarise retrieved
            # chunks — n8n flags it red without one. Same credential and model as the agent.
            "parameters": {"modelName": GEMINI_CHAT_MODEL, "options": {}},
            "id": nid(TOOL_VECTOR_MODEL), "name": TOOL_VECTOR_MODEL,
            "type": "@n8n/n8n-nodes-langchain.lmChatGoogleGemini", "typeVersion": 1.1,
            "position": [780, 760],
        },
        code_node(FALLBACK, FALLBACK_CODE, [200, 120]),
        code_node(VALIDATE, VALIDATE_CODE, [420, 300]),
        http_node(
            ENRICH, "POST",
            "={{ $json.backend_base_url }}/api/ai/n8n/enrichment/{{ $json.incident_id }}",
            [640, 300],
            json_body=("={{ JSON.stringify({ what: $json.what, why: $json.why, "
                       "impact: $json.impact, prediction: $json.prediction, "
                       "recommended_action_ids: $json.recommended_action_ids, "
                       "sources: $json.sources, produced_by: $json.produced_by, "
                       "fallback: $json.fallback, resume_url: $execution.resumeUrl }) }}"),
        ),
        {
            "parameters": {"resume": "webhook", "httpMethod": "POST",
                           "responseMode": "onReceived", "limitWaitTime": True,
                           "resumeAmount": 10, "resumeUnit": "minutes", "options": {}},
            "id": nid(WAIT_DECISION), "name": WAIT_DECISION,
            "type": "n8n-nodes-base.wait", "typeVersion": 1.1, "position": [860, 300],
            "webhookId": nid(WAIT_DECISION + ":hook"),
        },
        if_string_equals(APPROVED,
                         "={{ ($json.body && $json.body.decision) || $json.decision || 'timeout' }}",
                         "approve", [1080, 300]),
        {
            "parameters": {"resume": "timeInterval", "amount": 15, "unit": "seconds"},
            "id": nid(WAIT_SETTLE), "name": WAIT_SETTLE, "type": "n8n-nodes-base.wait",
            "typeVersion": 1.1, "position": [1300, 180],
            "webhookId": nid(WAIT_SETTLE + ":hook"),
        },
        http_node(VERIFY, "GET",
                  f"={{{{ {SRC}.backend_base_url }}}}/api/ai/n8n/verify/{{{{ {SRC}.incident_id }}}}",
                  [1520, 180], on_error="continueRegularOutput"),
        if_string_equals(VERIFIED, "={{ $json.verified ? 'yes' : 'no' }}", "yes", [1740, 180]),
        http_node(STATUS_RESOLVING, "POST",
                  f"={{{{ {SRC}.backend_base_url }}}}/api/ai/n8n/status/{{{{ {SRC}.incident_id }}}}",
                  [1960, 80],
                  json_body=("={{ JSON.stringify({ status: 'RESOLVING', note: "
                             "'Owner authorised the action and verification passed: ' + "
                             "($json.details || []).filter(d => d.passed).map(d => d.check).join('; '), "
                             "produced_by: 'n8n incident_response_v2' }) }}"),
                  on_error="continueRegularOutput"),
        http_node(STATUS_ESCALATED, "POST",
                  f"={{{{ {SRC}.backend_base_url }}}}/api/ai/n8n/status/{{{{ {SRC}.incident_id }}}}",
                  [1960, 300],
                  json_body=("={{ JSON.stringify({ status: 'ESCALATED', note: "
                             "'Action was authorised but verification did not confirm the plant "
                             "changed: ' + ($json.details || []).filter(d => !d.passed)"
                             ".map(d => d.check).join('; '), "
                             "produced_by: 'n8n incident_response_v2' }) }}"),
                  on_error="continueRegularOutput"),
        code_node(OUTCOME, OUTCOME_CODE, [1300, 460]),
        http_node(STATUS_OUTCOME, "POST",
                  f"={{{{ {SRC}.backend_base_url }}}}/api/ai/n8n/status/{{{{ {SRC}.incident_id }}}}",
                  [1520, 460],
                  json_body=("={{ JSON.stringify({ status: $json.status, note: $json.note, "
                             "produced_by: 'n8n incident_response_v2' }) }}"),
                  on_error="continueRegularOutput"),
    ]

    connections = {
        WEBHOOK: {"main": [main_link(PREPARE)]},
        PREPARE: {"main": [main_link(AGENT)]},
        # Output 0 = the agent answered; output 1 = the error branch -> deterministic template.
        AGENT: {"main": [main_link(VALIDATE), main_link(FALLBACK)]},
        FALLBACK: {"main": [main_link(VALIDATE)]},
        VALIDATE: {"main": [main_link(ENRICH)]},
        ENRICH: {"main": [main_link(WAIT_DECISION)]},
        WAIT_DECISION: {"main": [main_link(APPROVED)]},
        APPROVED: {"main": [main_link(WAIT_SETTLE), main_link(OUTCOME)]},
        WAIT_SETTLE: {"main": [main_link(VERIFY)]},
        VERIFY: {"main": [main_link(VERIFIED)]},
        VERIFIED: {"main": [main_link(STATUS_RESOLVING), main_link(STATUS_ESCALATED)]},
        OUTCOME: {"main": [main_link(STATUS_OUTCOME)]},
        # Sub-nodes attach upwards into the node that uses them.
        MODEL: {"ai_languageModel": [ai_link(AGENT, "ai_languageModel")]},
        PARSER: {"ai_outputParser": [ai_link(AGENT, "ai_outputParser")]},
        TOOL_HTTP: {"ai_tool": [ai_link(AGENT, "ai_tool")]},
        TOOL_VECTOR: {"ai_tool": [ai_link(AGENT, "ai_tool")]},
        VECTOR_RETRIEVER: {"ai_vectorStore": [ai_link(TOOL_VECTOR, "ai_vectorStore")]},
        TOOL_VECTOR_MODEL: {"ai_languageModel": [ai_link(TOOL_VECTOR, "ai_languageModel")]},
        EMBEDDINGS_RETRIEVE: {"ai_embedding": [ai_link(VECTOR_RETRIEVER, "ai_embedding")]},
    }

    return {
        "name": "Incident Response v2 (Gemini + RAG)",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
        "pinData": {},
    }


# =========================================================== rag_ingestion

INGEST_TRIGGER = "When clicking Execute"
INGEST_FETCH = "GET corpus from backend"
INGEST_SPLIT = "One item per section"
INGEST_STORE = "Simple Vector Store (insert)"
INGEST_EMBED = "Embeddings Gemini (insert)"
INGEST_LOADER = "Default Data Loader"
INGEST_SPLITTER = "Recursive Character Text Splitter"

INGEST_SPLIT_CODE = """
// One n8n item per procedure section, so each becomes its own retrievable chunk with its own
// citation metadata.
const sections = $input.first().json.sections || [];
return sections.map(s => ({
  json: {
    text: `${s.citation} — ${s.section}\\n\\n${s.text}`,
    doc_id: s.doc_id,
    citation: s.citation,
    section: s.section,
    hazard: s.hazard || 'ANY',
    category: s.category || '',
  },
}));
""".strip()


def build_ingestion(backend_base="http://127.0.0.1:8000"):
    nodes = [
        {
            "parameters": {},
            "id": nid(INGEST_TRIGGER), "name": INGEST_TRIGGER,
            "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [-320, 300],
        },
        http_node(INGEST_FETCH, "GET", f"{backend_base}/api/ai/n8n/corpus", [-100, 300]),
        code_node(INGEST_SPLIT, INGEST_SPLIT_CODE, [120, 300]),
        {
            "parameters": {
                "mode": "insert",
                "memoryKey": {"__rl": True, "mode": "id", "value": MEMORY_KEY},
                # Wipe before loading so re-running does not duplicate every chunk.
                "clearStore": True,
            },
            "id": nid(INGEST_STORE), "name": INGEST_STORE,
            "type": "@n8n/n8n-nodes-langchain.vectorStoreInMemory", "typeVersion": 1.2,
            "position": [340, 300],
        },
        {
            "parameters": {},   # modelName defaults to models/gemini-embedding-001
            "id": nid(INGEST_EMBED), "name": INGEST_EMBED,
            "type": "@n8n/n8n-nodes-langchain.embeddingsGoogleGemini", "typeVersion": 1,
            "position": [240, 520],
        },
        {
            "parameters": {
                "dataType": "json",
                "jsonMode": "expressionData",
                "jsonData": "={{ $json.text }}",
                "textSplittingMode": "custom",
                "options": {
                    "metadata": {
                        "metadataValues": [
                            {"name": "doc_id", "value": "={{ $json.doc_id }}"},
                            {"name": "citation", "value": "={{ $json.citation }}"},
                            {"name": "section", "value": "={{ $json.section }}"},
                            {"name": "hazard", "value": "={{ $json.hazard }}"},
                        ]
                    }
                },
            },
            "id": nid(INGEST_LOADER), "name": INGEST_LOADER,
            "type": "@n8n/n8n-nodes-langchain.documentDefaultDataLoader", "typeVersion": 1.1,
            "position": [460, 520],
        },
        {
            "parameters": {"chunkSize": 400, "chunkOverlap": 50, "options": {}},
            "id": nid(INGEST_SPLITTER), "name": INGEST_SPLITTER,
            "type": "@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter",
            "typeVersion": 1, "position": [620, 720],
        },
    ]

    connections = {
        INGEST_TRIGGER: {"main": [main_link(INGEST_FETCH)]},
        INGEST_FETCH: {"main": [main_link(INGEST_SPLIT)]},
        INGEST_SPLIT: {"main": [main_link(INGEST_STORE)]},
        INGEST_EMBED: {"ai_embedding": [ai_link(INGEST_STORE, "ai_embedding")]},
        INGEST_LOADER: {"ai_document": [ai_link(INGEST_STORE, "ai_document")]},
        INGEST_SPLITTER: {"ai_textSplitter": [ai_link(INGEST_LOADER, "ai_textSplitter")]},
    }

    return {
        "name": "RAG ingestion (procedures -> Simple Vector Store)",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
        "pinData": {},
    }


if __name__ == "__main__":
    v2 = build_v2()
    OUT_V2.write_text(json.dumps(v2, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_V2.name} ({len(v2['nodes'])} nodes)")

    ingest = build_ingestion()
    OUT_INGEST.write_text(json.dumps(ingest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_INGEST.name} ({len(ingest['nodes'])} nodes)")
