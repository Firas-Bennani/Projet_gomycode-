"""Generate n8n/workflows/incident_response_v1.json.

Kept in the repo so the workflow can be regenerated instead of hand-edited as JSON.
After importing into n8n, the authoritative copy is the export from the n8n UI
(Workflows -> ... -> Download), which overwrites this file's output.

Run:  python n8n/workflows/_generate_v1.py
"""

import json
import pathlib
import uuid

OUT = pathlib.Path(__file__).with_name("incident_response_v1.json")

# Deterministic ids so regenerating does not churn the diff.
def nid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"copilot/v1/{name}"))


WEBHOOK = "Incident webhook"
TEMPLATE = "Template recommendation"
VALIDATE = "Validate against allowed_actions"
ENRICH = "POST enrichment"
WAIT_DECISION = "Wait for owner decision"
APPROVED = "Approved?"
WAIT_SETTLE = "Wait 15s for the plant to settle"
VERIFY = "GET verify"
VERIFIED = "Verified?"
STATUS_RESOLVING = "POST status RESOLVING"
STATUS_ESCALATED = "POST status ESCALATED"
OUTCOME = "Outcome without approval"
STATUS_OUTCOME = "POST status (cancel or timeout)"

# The webhook node wraps the POSTed JSON in `body`; everything after the Wait node reads the
# original payload back off the trigger node, because item pairing is not reliable across a wait.
SRC = f"$('{WEBHOOK}').first().json.body"

TEMPLATE_CODE = """
// Deterministic recommendation. No LLM: this is the fallback path that must always work,
// and in v1 it is the only path. It chooses ONLY from allowed_actions, which the backend
// built from ai/actions_catalog.py.
const input = $input.first().json;
const payload = input.body || input;
const incident = payload.incident || {};
const allowed = payload.allowed_actions || [];
const evidence = payload.evidence || [];
const workers = payload.workers || [];

const allowedIds = allowed.map(a => a.id);
const byHazard = {
  MACHINE_OVERHEATING: ['stop_machine', 'evacuate_zone', 'activate_cooling'],
  INDUSTRIAL_FIRE: ['trigger_alarm', 'evacuate_zone', 'close_door', 'activate_suppression'],
  CYBER_INTRUSION: ['vlan_quarantine', 'isolate_device'],
};
const chosen = (byHazard[incident.type] || allowedIds).filter(id => allowedIds.includes(id));

const hazard = String(incident.type || 'hazard').replace(/_/g, ' ').toLowerCase();
const assets = (incident.affected_assets || []).join(', ') || 'the affected zone';
const names = workers.map(w => `${w.id} (${w.role})`).join(', ');

return [{
  json: {
    incident_id: payload.incident_id,
    backend_base_url: payload.backend_base_url,
    allowed_action_ids: allowedIds,
    what: `${hazard} affecting ${assets} in ${incident.zone}`,
    why: evidence.map(e => `${e.source}: ${e.detail}`),
    impact: workers.length
      ? `${workers.length} person(s) exposed in ${incident.zone}: ${names}. Unplanned loss of ${assets}.`
      : `No personnel currently detected in ${incident.zone}. Unplanned loss of ${assets}.`,
    prediction: `Without intervention the condition on ${assets} is expected to continue worsening; `
      + `severity at detection was ${incident.severity} with ${Math.round((incident.confidence || 0) * 100)}% fused confidence.`,
    recommended_action_ids: chosen,
    sources: [],
    produced_by: 'n8n template (deterministic, no LLM)',
    fallback: true,
  },
}];
""".strip()

VALIDATE_CODE = """
// Belt and braces: the backend validates ids against the catalogue as well, but an id that
// never leaves n8n is one fewer rejection to explain. Also de-duplicates.
const item = $input.first().json;
const allowed = new Set(item.allowed_action_ids || []);
const proposed = item.recommended_action_ids || [];
const validated = [...new Set(proposed)].filter(id => allowed.has(id));
const rejected = [...new Set(proposed)].filter(id => !allowed.has(id));
return [{ json: { ...item, recommended_action_ids: validated, rejected_action_ids: rejected } }];
""".strip()

OUTCOME_CODE = """
// The Wait node resumes either because the owner decided, or because its 180 s limit expired.
// Distinguish the two: a cancel is a human decision, a timeout is an unattended incident.
const decision = ($json.body && $json.body.decision) || $json.decision || 'timeout';
const cancelled = decision === 'cancel';
return [{
  json: {
    decision,
    status: cancelled ? 'DISMISSED' : 'ESCALATED',
    note: cancelled
      ? 'Owner cancelled the recommended action in the dashboard; incident dismissed by human decision.'
      : 'No owner decision within the 180 s approval window; escalated for human handling.',
  },
}];
""".strip()


def code_node(name, code, position):
    return {
        "parameters": {"jsCode": code},
        "id": nid(name),
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
    }


def http_node(name, method, url, position, json_body=None, on_error=None):
    parameters = {"method": method, "url": url, "options": {}}
    if json_body is not None:
        parameters.update({"sendBody": True, "specifyBody": "json", "jsonBody": json_body})
    node = {
        "parameters": parameters,
        "id": nid(name),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": position,
    }
    if on_error:
        node["onError"] = on_error
    return node


def if_string_equals(name, left_expression, expected, position):
    """String comparison only — avoids depending on the boolean operator's JSON shape."""
    return {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{
                    "id": nid(name + ":cond"),
                    "leftValue": left_expression,
                    "rightValue": expected,
                    "operator": {"type": "string", "operation": "equals"},
                }],
                "combinator": "and",
            },
            "looseTypeValidation": True,
            "options": {},
        },
        "id": nid(name),
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": position,
    }


nodes = [
    {
        "parameters": {
            "httpMethod": "POST",
            "path": "incident",
            # Answer the backend immediately: the orchestrator must never wait on n8n.
            "responseMode": "onReceived",
            "options": {},
        },
        "id": nid(WEBHOOK),
        "name": WEBHOOK,
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [-320, 300],
        "webhookId": nid(WEBHOOK + ":hook"),
    },
    code_node(TEMPLATE, TEMPLATE_CODE, [-100, 300]),
    code_node(VALIDATE, VALIDATE_CODE, [120, 300]),
    http_node(
        ENRICH, "POST",
        "={{ $json.backend_base_url }}/api/ai/n8n/enrichment/{{ $json.incident_id }}",
        [340, 300],
        json_body=(
            "={{ JSON.stringify({ what: $json.what, why: $json.why, impact: $json.impact, "
            "prediction: $json.prediction, recommended_action_ids: $json.recommended_action_ids, "
            "sources: $json.sources, produced_by: $json.produced_by, fallback: $json.fallback, "
            "resume_url: $execution.resumeUrl }) }}"
        ),
    ),
    {
        "parameters": {
            "resume": "webhook",
            "httpMethod": "POST",
            "responseMode": "onReceived",
            "limitWaitTime": True,
            "resumeAmount": 180,
            "resumeUnit": "seconds",
            "options": {},
        },
        "id": nid(WAIT_DECISION),
        "name": WAIT_DECISION,
        "type": "n8n-nodes-base.wait",
        "typeVersion": 1.1,
        "position": [560, 300],
        "webhookId": nid(WAIT_DECISION + ":hook"),
    },
    if_string_equals(
        APPROVED,
        "={{ ($json.body && $json.body.decision) || $json.decision || 'timeout' }}",
        "approve",
        [780, 300],
    ),
    {
        "parameters": {"resume": "timeInterval", "amount": 15, "unit": "seconds"},
        "id": nid(WAIT_SETTLE),
        "name": WAIT_SETTLE,
        "type": "n8n-nodes-base.wait",
        "typeVersion": 1.1,
        "position": [1000, 180],
        "webhookId": nid(WAIT_SETTLE + ":hook"),
    },
    http_node(
        VERIFY, "GET",
        f"={{{{ {SRC}.backend_base_url }}}}/api/ai/n8n/verify/{{{{ {SRC}.incident_id }}}}",
        [1220, 180],
        on_error="continueRegularOutput",
    ),
    if_string_equals(VERIFIED, "={{ $json.verified ? 'yes' : 'no' }}", "yes", [1440, 180]),
    http_node(
        STATUS_RESOLVING, "POST",
        f"={{{{ {SRC}.backend_base_url }}}}/api/ai/n8n/status/{{{{ {SRC}.incident_id }}}}",
        [1660, 80],
        json_body=(
            "={{ JSON.stringify({ status: 'RESOLVING', "
            "note: 'Owner authorised the action and verification passed: ' + "
            "($json.details || []).filter(d => d.passed).map(d => d.check).join('; '), "
            "produced_by: 'n8n incident_response_v1' }) }}"
        ),
        on_error="continueRegularOutput",
    ),
    http_node(
        STATUS_ESCALATED, "POST",
        f"={{{{ {SRC}.backend_base_url }}}}/api/ai/n8n/status/{{{{ {SRC}.incident_id }}}}",
        [1660, 300],
        json_body=(
            "={{ JSON.stringify({ status: 'ESCALATED', "
            "note: 'Action was authorised but verification did not confirm the plant changed: ' + "
            "($json.details || []).filter(d => !d.passed).map(d => d.check).join('; '), "
            "produced_by: 'n8n incident_response_v1' }) }}"
        ),
        on_error="continueRegularOutput",
    ),
    code_node(OUTCOME, OUTCOME_CODE, [1000, 460]),
    http_node(
        STATUS_OUTCOME, "POST",
        f"={{{{ {SRC}.backend_base_url }}}}/api/ai/n8n/status/{{{{ {SRC}.incident_id }}}}",
        [1220, 460],
        json_body=(
            "={{ JSON.stringify({ status: $json.status, note: $json.note, "
            "produced_by: 'n8n incident_response_v1' }) }}"
        ),
        on_error="continueRegularOutput",
    ),
]


def main(target, index=0):
    return [{"node": target, "type": "main", "index": index}]


connections = {
    WEBHOOK: {"main": [main(TEMPLATE)]},
    TEMPLATE: {"main": [main(VALIDATE)]},
    VALIDATE: {"main": [main(ENRICH)]},
    ENRICH: {"main": [main(WAIT_DECISION)]},
    WAIT_DECISION: {"main": [main(APPROVED)]},
    # IF: first list is the true branch, second is the false branch.
    APPROVED: {"main": [main(WAIT_SETTLE), main(OUTCOME)]},
    WAIT_SETTLE: {"main": [main(VERIFY)]},
    VERIFY: {"main": [main(VERIFIED)]},
    VERIFIED: {"main": [main(STATUS_RESOLVING), main(STATUS_ESCALATED)]},
    OUTCOME: {"main": [main(STATUS_OUTCOME)]},
}

workflow = {
    "name": "Incident Response v1 (deterministic, no LLM)",
    "nodes": nodes,
    "connections": connections,
    "settings": {"executionOrder": "v1"},
    "pinData": {},
    "meta": {"instanceId": "ai-industrial-copilot"},
}

if __name__ == "__main__":
    OUT.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(nodes)} nodes)")
