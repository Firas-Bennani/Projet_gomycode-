"""Cybersecurity agent for the OT network.

Before Step 8 this agent flagged **every** ``CYBER_EVENT`` as HIGH with no rules and hardcoded
defaults (`attempts=47`). It now classifies the event against named rules, attributes each one to
a MITRE ATT&CK for ICS technique **looked up in the published STIX bundle** (never from memory),
and — the part that matters most — when it concludes a sensor is lying it tells the risk engine to
**distrust** that sensor rather than ignore it.

That last behaviour is the one place where one agent changes how another reasons:
``OT-CYBER-PB §4`` requires that a spoofed reading be down-weighted, not discarded, so a machine
overheating is still detected when its own ambient sensor has been pinned low by an attacker. The
decision is written into ``state.agent_logs`` as "Distrust <sensor_id>" so it is visible on the
multi-agent page.
"""

from typing import Any, Dict, List, Optional

from ai import clock, mitre_ics, risk_engine
from ai.agents.base_agent import BaseAgent

#: Failed authentications from one source inside the window that constitute a brute-force
#: attempt. From OT-CYBER-PB §2.2.
BRUTE_FORCE_ATTEMPTS = 20
BRUTE_FORCE_WINDOW_S = 60.0

#: Traffic z-score beyond which volume counts as anomalous. OT-CYBER-PB §2.4.
TRAFFIC_Z_THRESHOLD = 3.0

#: Sources allowed to issue control commands to a controller.
COMMAND_WHITELIST = {"ENG-WS-01", "SCADA-PRIMARY", "HMI-B-01"}

#: Trust applied to a sensor judged to be spoofed. OT-CYBER-PB §4.2.
SPOOFED_SENSOR_TRUST = 0.2

RULE_SEVERITY = {
    "UNAUTHORIZED_COMMAND": "CRITICAL",
    "SPOOFED_SENSOR": "CRITICAL",
    "BRUTE_FORCE": "HIGH",
    "UNKNOWN_DEVICE": "HIGH",
    "CREDENTIAL_ABUSE": "HIGH",
    "TRAFFIC_ANOMALY": "WARNING",
}
SEVERITY_ORDER = {"WARNING": 1, "HIGH": 2, "CRITICAL": 3}


class CybersecurityAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="cyber_agent",
            name="Cybersecurity Industrial Defense Agent"
        )
        self.simulated_devices = set()
        #: source -> [(timestamp, failed_auth_count)] for the brute-force window.
        self.auth_failures: Dict[str, List[Any]] = {}
        #: Sensors this agent has already distrusted, so it does not repeat itself every tick.
        self.distrusted_sensors: set = set()

    # ------------------------------------------------------------------ inventory

    @staticmethod
    def _known_devices() -> set:
        """Everything legitimately on the OT segment, from the state store plus fixed infra."""
        known = {"SWITCH-CORE-01", "PLC-B-01", "GATEWAY-MODBUS-01"} | COMMAND_WHITELIST
        try:
            from app.services.state_store import state
            known |= set(state.machines.keys())
            known |= set(state.sensors.keys())
        except Exception:
            pass
        return known

    # ------------------------------------------------------------------ rules

    def _brute_force(self, source: str, failures: int) -> bool:
        """Failed authentications from one source inside a rolling 60 s window."""
        if not source or failures <= 0:
            return False
        now = clock.now()
        history = self.auth_failures.setdefault(source, [])
        history.append((now, failures))
        cutoff = now.timestamp() - BRUTE_FORCE_WINDOW_S
        while history and history[0][0].timestamp() < cutoff:
            history.pop(0)
        return sum(count for _, count in history) >= BRUTE_FORCE_ATTEMPTS

    def _spoofed_sensor(self, data: Dict[str, Any]) -> Optional[str]:
        """Which sensor, if any, is reporting something physically inconsistent.

        Either the event says so outright, or we cross-check the named sensor against the machine
        it shares a zone with: an ambient sensor sitting at baseline while the machine beside it is
        past its own temperature limit is not measuring the same room.
        """
        sensor_id = data.get("sensor_id") or data.get("spoofed_sensor")
        if not sensor_id:
            return None
        if str(data.get("cyber_type", "")).upper() == "SPOOFED_SENSOR":
            return sensor_id
        try:
            from app.services.state_store import state
            sensor = state.sensors.get(sensor_id)
            if sensor is None or sensor.type != "temperature":
                return None
            for machine in state.machines.values():
                if machine.zone != sensor.zone:
                    continue
                body = machine.parameters.get("temperature")
                if body is None or not body.threshold:
                    continue
                if body.value >= body.threshold and sensor.current_value <= (sensor.threshold_warning or 35.0):
                    return sensor_id
        except Exception:
            return None
        return None

    def _classify(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Every rule this event trips, each with its evidence and ATT&CK attribution."""
        device = data.get("device") or "UNKNOWN-DEVICE"
        source = data.get("source") or data.get("source_ip") or device
        target = data.get("target") or "Industrial Modbus Gateway"
        attempts = int(data.get("attempts") or data.get("failed_auths") or 0)
        declared = str(data.get("cyber_type", "")).upper()

        findings: List[Dict[str, Any]] = []

        def add(rule: str, detail: str) -> None:
            findings.append({
                "rule": rule,
                "severity": RULE_SEVERITY.get(rule, "WARNING"),
                "detail": detail,
                "mitre": mitre_ics.for_rule(rule),
            })

        if self._brute_force(source, attempts):
            add("BRUTE_FORCE",
                f"{attempts} failed authentication attempts from {source} against {target} "
                f"within {BRUTE_FORCE_WINDOW_S:.0f}s (threshold {BRUTE_FORCE_ATTEMPTS})")

        if device not in self._known_devices():
            add("UNKNOWN_DEVICE",
                f"{device} is not in the OT asset inventory but is transacting with {target}")

        if declared == "UNAUTHORIZED_COMMAND" or (data.get("command") and source not in COMMAND_WHITELIST):
            add("UNAUTHORIZED_COMMAND",
                f"control command {data.get('command', 'write')!r} reached {target} from {source}, "
                f"which is not on the engineering whitelist")

        traffic_z = data.get("traffic_z")
        if traffic_z is not None and abs(float(traffic_z)) >= TRAFFIC_Z_THRESHOLD:
            add("TRAFFIC_ANOMALY",
                f"segment traffic volume at {float(traffic_z):+.1f} sigma from its baseline")

        if declared == "VALID_ACCOUNTS" or data.get("valid_account_misuse"):
            add("CREDENTIAL_ABUSE",
                f"a valid engineering account was used from {source}, outside its normal pattern")

        spoofed = self._spoofed_sensor(data)
        if spoofed:
            add("SPOOFED_SENSOR",
                f"{spoofed} is reporting a value inconsistent with the machine in its zone")
            findings[-1]["sensor_id"] = spoofed

        if not findings:
            # Something reached us but matched no rule. Say that, rather than inventing a verdict.
            add("TRAFFIC_ANOMALY",
                f"unclassified OT event from {source} towards {target}; no rule matched")
            findings[-1]["severity"] = "WARNING"
            findings[-1]["unclassified"] = True

        return findings

    # ------------------------------------------------------------------ main entry

    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_type = event.get("event_type", "")
        if event_type not in ["CYBER_EVENT"]:
            return None

        data = event.get("data", {})
        sub_type = data.get("cyber_type", "UNAUTHORIZED_DEVICE")
        device = data.get("device", "UNKNOWN-DEVICE-07")
        attempts = int(data.get("attempts", 0) or 0)
        target = data.get("target", "Industrial Modbus Gateway (192.168.10.45)")

        findings = self._classify(data)
        severity = max((f["severity"] for f in findings),
                       key=lambda s: SEVERITY_ORDER.get(s, 0))

        # ---- the flagship: a spoofed sensor is distrusted, not ignored --------------------
        spoof = next((f for f in findings if f["rule"] == "SPOOFED_SENSOR"), None)
        distrust_note = ""
        if spoof and spoof.get("sensor_id"):
            sensor_id = spoof["sensor_id"]
            reason = (f"spoofed: {spoof['detail']}"
                      + (f" [{mitre_ics.describe(spoof['mitre'])}]" if spoof.get("mitre") else ""))
            risk_engine.set_trust(sensor_id, SPOOFED_SENSOR_TRUST, reason)
            self.distrusted_sensors.add(sensor_id)
            distrust_note = (
                f" Distrust {sensor_id}: its trust weight is now {SPOOFED_SENSOR_TRUST:.1f}, so the "
                f"risk engine keeps using it but no longer lets it mask a hazard on its own "
                f"(OT-CYBER-PB 4.2)."
            )
        # ----------------------------------------------------------------------------------

        rule_text = "; ".join(
            f"{f['rule']} ({f['detail']}"
            + (f"; {mitre_ics.describe(f['mitre'])}" if f.get("mitre") else "")
            + ")"
            for f in findings
        )
        observation = f"OT network findings on {device}: {rule_text}.{distrust_note}"

        primary = max(findings, key=lambda f: SEVERITY_ORDER.get(f["severity"], 0))
        if primary["rule"] == "SPOOFED_SENSOR":
            decision = f"DISTRUST {spoof['sensor_id']} and investigate the source of the spoofed data"
        elif primary["rule"] == "UNAUTHORIZED_COMMAND":
            decision = f"BLOCK the command path and isolate {device} immediately"
        else:
            decision = f"RECOMMEND ISOLATION: sever MAC/VLAN connectivity for {device}"

        self.update_status(
            task="OT Network Intrusion Defense & Anomaly Quarantine",
            observation=observation,
            decision=decision,
            status="WARNING"
        )

        return {
            "agent_id": self.agent_id,
            "anomaly": True,
            "severity": severity,
            "cyber_type": sub_type,
            "device": device,
            "attempts": attempts,
            "target": target,
            # --- added keys (never remove/rename the ones above) ---
            "rules": [f["rule"] for f in findings],
            "findings": findings,
            "mitre_techniques": [
                {"rule": f["rule"], **f["mitre"]} for f in findings if f.get("mitre")
            ],
            "spoofed_sensor": spoof.get("sensor_id") if spoof else None,
            "distrusted_sensors": sorted(self.distrusted_sensors),
            "observation": observation,
            "decision": decision,
        }
