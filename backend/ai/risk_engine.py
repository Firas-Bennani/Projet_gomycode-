"""Risk engine: how confident are we, how bad is it, and what should be dealt with first.

Replaces the provisional fusion that lived in ``recommendation_agent`` (and, before Step 1, the
hardcoded 0.94 / 0.95 / 0.96 literals). Three jobs:

**1. Confidence — noisy-OR over independent sources, weighted by trust.**

``confidence = 1 - Π(1 - cᵢ · trustᵢ)``

Two weak but independent sensors agreeing is stronger evidence than either alone, and no finite
amount of evidence reaches certainty. ``trustᵢ`` defaults to 1.0 and is lowered for a sensor the
cyber agent judges to be spoofed (Step 8), which is what lets an overheating stay detected even
when its own temperature sensor is lying.

**2. Severity — impact × likelihood, capped by what the sensors actually justify.**

Impact comes from the asset's criticality, +1 if people are exposed, +1 for a hazard class that
hurts people directly (fire, overpressure). Likelihood is a band of the fused confidence. The
product picks a severity — but it is then **capped one band above the strongest single source**,
so the system cannot announce CRITICAL while every sensor is merely at a warning level. That cap
is what produces the honest WARNING → CRITICAL progression as a fault develops.

**3. Priority — what a human should look at first:** severity, then people exposed, then how
little time is left (ETA to a limit).

Everything returned carries its own arithmetic so the incident text can show the numbers rather
than assert them.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("risk_engine")

SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "HIGH": 2, "CRITICAL": 3}
RANK_TO_SEVERITY = {rank: name for name, rank in SEVERITY_RANK.items()}

#: Likelihood that the hazard is real given a single source at this severity, alone.
SOURCE_CONFIDENCE = {"WARNING": 0.60, "HIGH": 0.80, "CRITICAL": 0.85}

MAX_CONFIDENCE = 0.99

#: Asset criticality, 1 (minor) to 3 (a loss that stops the plant or endangers people).
ASSET_CRITICALITY: Dict[str, int] = {
    "M-04": 3,   # heavy milling unit, hydraulic circuit
    "M-05": 3,   # induction furnace
    "M-01": 2,
    "M-02": 2,
    "M-06": 2,
}
DEFAULT_ASSET_CRITICALITY = 2

#: Hazards that injure people directly rather than only destroying equipment.
DIRECT_HARM_TYPES = ("INDUSTRIAL_FIRE", "MACHINE_OVERHEATING")

#: Base impact per hazard type, before the +1 modifiers.
HAZARD_IMPACT_BASE = {
    "INDUSTRIAL_FIRE": 3,      # life safety, spreads
    "CYBER_INTRUSION": 3,      # controller manipulation, spoofed readings
    "MACHINE_OVERHEATING": None,  # taken from the asset's own criticality
}

MAX_IMPACT = 4
MAX_LIKELIHOOD = 4


# --------------------------------------------------------------------- sensor trust

#: sensor_id / asset_id -> trust in [0, 1]. Mutated by the cyber agent when it decides a source
#: is lying; read here when fusing. Deliberately module state, not in schemas.py.
TRUST: Dict[str, float] = {}
TRUST_REASONS: Dict[str, str] = {}


def set_trust(source_id: str, trust: float, reason: str = "") -> None:
    trust = max(0.0, min(1.0, float(trust)))
    TRUST[source_id] = trust
    if reason:
        TRUST_REASONS[source_id] = reason
    logger.info("Trust for %s set to %.2f (%s)", source_id, trust, reason or "no reason given")


def get_trust(source_id: Optional[str]) -> float:
    if not source_id:
        return 1.0
    return TRUST.get(source_id, 1.0)


def trust_reason(source_id: Optional[str]) -> str:
    return TRUST_REASONS.get(source_id or "", "")


def reset_trust() -> None:
    TRUST.clear()
    TRUST_REASONS.clear()


# --------------------------------------------------------------------- results

@dataclass
class Contribution:
    source_id: str
    agent_id: str
    severity: str
    base_confidence: float
    trust: float
    #: ``base_confidence * trust`` — what this source actually contributes to the fusion.
    effective: float
    #: Fused confidence after including this source, so the build-up is visible.
    running_total: float

    @property
    def text(self) -> str:
        trust_note = "" if self.trust >= 0.999 else f", trust {self.trust:.2f}"
        return (f"{self.source_id} ({self.severity}, {self.base_confidence:.2f}{trust_note}"
                f" -> {self.effective:.2f}; running {self.running_total:.2f})")


@dataclass
class RiskResult:
    confidence: float
    severity: str
    contributions: List[Contribution] = field(default_factory=list)
    impact: int = 1
    likelihood: int = 1
    matrix_severity: str = "INFO"
    severity_cap: str = "CRITICAL"
    strongest_source_severity: str = "INFO"
    priority: int = 0
    workers_exposed: int = 0
    eta_seconds: Optional[float] = None
    distrusted: List[str] = field(default_factory=list)

    @property
    def contribution_text(self) -> str:
        return ", ".join(c.text for c in self.contributions) or "no scored source"

    @property
    def severity_explanation(self) -> str:
        capped = SEVERITY_RANK[self.matrix_severity] > SEVERITY_RANK[self.severity]
        base = (f"impact {self.impact}/4 x likelihood {self.likelihood}/4 "
                f"= {self.impact * self.likelihood}/16 -> {self.matrix_severity}")
        if capped:
            return (f"{base}, capped to {self.severity} because the strongest single source is "
                    f"only {self.strongest_source_severity}")
        return f"{base}"


# --------------------------------------------------------------------- fusion

def source_id_of(observation: Dict[str, Any]) -> str:
    for field_name in ("sensor_id", "machine_id", "device", "worker_id"):
        value = observation.get(field_name)
        if value:
            return str(value)
    return str(observation.get("agent_id", "unknown"))


def fuse(observations: List[Dict[str, Any]]) -> Tuple[float, List[Contribution], List[str]]:
    """Noisy-OR fusion. Returns (confidence, contributions, distrusted source ids).

    One contribution per source: the observation window already keeps a single observation per
    ``(agent, asset)``, so the same sensor cannot be counted twice.
    """
    product = 1.0
    contributions: List[Contribution] = []
    distrusted: List[str] = []
    seen = set()

    for observation in observations:
        severity = str(observation.get("severity", "INFO")).upper()
        base = SOURCE_CONFIDENCE.get(severity)
        if base is None:
            continue
        source_id = source_id_of(observation)
        if source_id in seen:
            continue
        seen.add(source_id)

        trust = get_trust(source_id)
        effective = base * trust
        if trust < 0.999:
            distrusted.append(source_id)
        if effective <= 0.0:
            continue
        product *= (1.0 - effective)
        contributions.append(Contribution(
            source_id=source_id,
            agent_id=str(observation.get("agent_id", "unknown")),
            severity=severity,
            base_confidence=base,
            trust=trust,
            effective=round(effective, 3),
            running_total=round(min(1.0 - product, MAX_CONFIDENCE), 3),
        ))

    if not contributions:
        return 0.0, [], distrusted
    return round(min(1.0 - product, MAX_CONFIDENCE), 3), contributions, distrusted


# --------------------------------------------------------------------- severity

def likelihood_band(confidence: float) -> int:
    if confidence >= 0.90:
        return 4
    if confidence >= 0.75:
        return 3
    if confidence >= 0.50:
        return 2
    return 1


def impact_score(incident_type: str, assets: List[str], workers_exposed: int) -> int:
    base = HAZARD_IMPACT_BASE.get(incident_type)
    if base is None:
        base = max(
            (ASSET_CRITICALITY.get(str(a), DEFAULT_ASSET_CRITICALITY) for a in assets or []),
            default=DEFAULT_ASSET_CRITICALITY,
        )
    score = base
    if workers_exposed > 0:
        score += 1
    if incident_type in DIRECT_HARM_TYPES:
        score += 1
    return max(1, min(MAX_IMPACT, score))


def matrix_severity(impact: int, likelihood: int) -> str:
    score = impact * likelihood
    if score >= 12:
        return "CRITICAL"
    if score >= 8:
        return "HIGH"
    if score >= 4:
        return "WARNING"
    return "INFO"


def severity_cap(strongest_source_severity: str) -> str:
    """At most one band above the strongest single source.

    Without this the matrix would announce CRITICAL from two warning-level readings, which is
    how you train an operator to ignore the system.
    """
    rank = SEVERITY_RANK.get(strongest_source_severity.upper(), 0)
    return RANK_TO_SEVERITY[min(3, rank + 1)]


# --------------------------------------------------------------------- priority

def priority_score(severity: str, workers_exposed: int, eta_seconds: Optional[float]) -> int:
    """Higher is more urgent. Severity dominates, then people, then time remaining."""
    score = SEVERITY_RANK.get(severity, 0) * 1000
    score += min(workers_exposed, 9) * 50
    if eta_seconds is not None:
        # 0 s left -> +100, 600 s or more left -> +0.
        score += int(max(0.0, 100.0 - (eta_seconds / 6.0)))
    return score


# --------------------------------------------------------------------- entry point

def assess(
    observations: List[Dict[str, Any]],
    incident_type: str,
    assets: Optional[List[str]] = None,
    workers_exposed: int = 0,
    eta_seconds: Optional[float] = None,
    severity_floor: str = "WARNING",
) -> RiskResult:
    """Fuse the evidence and grade the hazard."""
    confidence, contributions, distrusted = fuse(observations)

    strongest = "INFO"
    for observation in observations:
        severity = str(observation.get("severity", "INFO")).upper()
        if SEVERITY_RANK.get(severity, 0) > SEVERITY_RANK.get(strongest, 0):
            strongest = severity

    impact = impact_score(incident_type, assets or [], workers_exposed)
    likelihood = likelihood_band(confidence)
    from_matrix = matrix_severity(impact, likelihood)
    cap = severity_cap(strongest)

    rank = min(SEVERITY_RANK[from_matrix], SEVERITY_RANK[cap])
    rank = max(rank, SEVERITY_RANK.get(severity_floor.upper(), 1))
    severity = RANK_TO_SEVERITY[rank]

    return RiskResult(
        confidence=confidence,
        severity=severity,
        contributions=contributions,
        impact=impact,
        likelihood=likelihood,
        matrix_severity=from_matrix,
        severity_cap=cap,
        strongest_source_severity=strongest,
        priority=priority_score(severity, workers_exposed, eta_seconds),
        workers_exposed=workers_exposed,
        eta_seconds=eta_seconds,
        distrusted=distrusted,
    )
