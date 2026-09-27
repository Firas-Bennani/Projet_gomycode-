"""Authentication for the messages agents send each other, and the checks around them.

Everything else in this system assumes the agents are honest. They talk over an in-process bus,
and until now any code that could publish an event could put words in another agent's mouth: a
forged "machine_agent says M-04 is fine" would have been fused into the evidence with full trust,
and the recommendation agent would have reasoned over a lie without any way to notice.

Three defences live here, and the cyber agent applies them (``ai/agents/cyber_agent.py``):

1. **Authenticity.** Every inter-agent observation carries an HMAC-SHA256 tag over its own
   content, keyed with a shared secret. An attacker who cannot read the secret cannot produce a
   tag, so an unsigned message, a message with a wrong tag, and a message from an agent id that
   does not exist are all rejectable *before* the content is believed.

2. **Behaviour.** A signature proves who sent a message, not that the sender is behaving. A
   real agent emits a handful of observations per window and a confidence inside [0, 1]; a
   flooding agent or one reporting 4.7 confidence is malfunctioning or captured, whichever it is.

3. **The LLM channel.** The enrichment text that comes back through n8n is untrusted input. It
   is scanned for instruction-injection before being shown, on top of the existing rules that it
   must carry the service secret and that any action it proposes must validate against the
   catalogue (``ai/actions_catalog.py``).

The secret comes from ``AGENT_BUS_SECRET`` in the environment. A development default is used when
it is unset so the demo runs out of the box; that is stated rather than hidden, because a shared
secret compiled into a repository is not a secret.
"""

import hashlib
import hmac
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from ai import clock

logger = logging.getLogger("agent_bus_auth")

#: Development default. Overridden by AGENT_BUS_SECRET in .env for anything real.
DEV_SECRET = "dev-agent-bus-secret-change-me"

#: The only senders that exist. An id outside this set is forged by definition.
KNOWN_AGENTS = {
    "temperature_agent",
    "machine_agent",
    "cyber_agent",
    "weather_agent",
    "worker_agent",
    "recommendation_agent",
}

#: More observations than this from one agent inside the window is not normal operation.
FLOOD_LIMIT = 12
FLOOD_WINDOW_SECONDS = 10.0

#: Trust applied to an agent whose messages or behaviour failed a check. Not zero: its readings
#: still count for something, they just stop being able to carry an incident on their own.
COMPROMISED_TRUST = 0.2

#: Instruction-injection shapes. Deliberately a short list of things that have no business in a
#: safety narrative, rather than a long list of clever phrasings — a scanner that fires on normal
#: procedure text would be turned off within a day.
INJECTION_PATTERNS = [
    (r"ignore\s+(all\s+)?(the\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)",
     "asks the reader to ignore its instructions"),
    (r"disregard\s+(all\s+)?(the\s+)?(previous|prior|above|safety)", "asks the reader to disregard"),
    (r"(reveal|print|repeat|show)\s+(your|the)\s+(system\s+)?(prompt|instructions|secret|key)",
     "asks for the system prompt or a secret"),
    (r"you\s+are\s+now\s+", "tries to reassign the reader's role"),
    (r"(skip|bypass|without)\s+(the\s+)?(owner|human)\s+(approval|authorisation|authorization|confirmation)",
     "tries to remove the human approval step"),
    (r"execute\s+(all|every|any)\s+action", "tries to trigger unrestricted execution"),
    (r"<\s*/?\s*(system|instructions?)\s*>", "contains a fake system tag"),
]


def secret() -> bytes:
    return (os.getenv("AGENT_BUS_SECRET") or DEV_SECRET).encode()


def using_dev_secret() -> bool:
    return not os.getenv("AGENT_BUS_SECRET")


# --------------------------------------------------------------------- signing

#: Fields that make up a message's identity. The signature covers what the message *claims*, so
#: changing any of them invalidates it — an attacker cannot lift a real tag onto a new claim.
SIGNED_FIELDS = ("agent_id", "zone", "severity", "observation", "decision")


def canonical(observation: Dict[str, Any]) -> str:
    return "|".join(f"{name}={observation.get(name, '')}" for name in SIGNED_FIELDS)


def tag_for(observation: Dict[str, Any]) -> str:
    return hmac.new(secret(), canonical(observation).encode(), hashlib.sha256).hexdigest()


def sign(observation: Dict[str, Any]) -> Dict[str, Any]:
    """Attach an authenticity tag. Mutates and returns the same dict, as the callers expect."""
    observation["sig"] = tag_for(observation)
    return observation


def verify(observation: Dict[str, Any]) -> Tuple[bool, str]:
    """Return ``(ok, reason)``. The reason is written for a human reading the agent log."""
    agent_id = str(observation.get("agent_id") or "")
    if agent_id not in KNOWN_AGENTS:
        return False, f"unknown agent_id {agent_id or '(missing)'}"

    provided = observation.get("sig")
    if not provided:
        return False, f"unsigned message claiming to be {agent_id}"

    if not hmac.compare_digest(str(provided), tag_for(observation)):
        return False, f"bad signature on a message claiming to be {agent_id}"

    return True, "signature valid"


# --------------------------------------------------------------------- behaviour

#: agent_id -> timestamps of its recent observations.
_recent: Dict[str, List[Any]] = {}


def reset_behaviour() -> None:
    _recent.clear()


def record(agent_id: str) -> int:
    """Remember that this agent spoke, and return how often it has spoken in the window."""
    now = clock.now()
    times = _recent.setdefault(agent_id, [])
    times.append(now)
    cutoff = now.timestamp() - FLOOD_WINDOW_SECONDS
    times[:] = [t for t in times if t.timestamp() >= cutoff]
    return len(times)


def behaviour_fault(observation: Dict[str, Any]) -> Optional[str]:
    """A signed message can still be wrong in ways a signature cannot catch."""
    agent_id = str(observation.get("agent_id") or "unknown")

    confidence = observation.get("source_confidence", observation.get("confidence"))
    if confidence is not None:
        try:
            value = float(confidence)
        except (TypeError, ValueError):
            return f"{agent_id} reported a non-numeric confidence {confidence!r}"
        if not 0.0 <= value <= 1.0:
            return (f"{agent_id} reported a confidence of {value:g}, which is outside [0, 1] and "
                    f"cannot be a probability")

    rate = record(agent_id)
    if rate > FLOOD_LIMIT:
        return (f"{agent_id} emitted {rate} observations in {FLOOD_WINDOW_SECONDS:.0f} s, far above "
                f"its normal rate of a few per event")

    return None


# --------------------------------------------------------------------- the LLM channel

def scan_for_injection(text: str) -> Optional[str]:
    """Return the reason this text should not be trusted as narrative, or None."""
    if not text:
        return None
    lowered = str(text).lower()
    for pattern, reason in INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            return reason
    return None
