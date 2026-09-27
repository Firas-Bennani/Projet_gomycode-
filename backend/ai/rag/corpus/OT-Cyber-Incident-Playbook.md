---
doc_id: OT-CYBER-PB
title: OT-CYBER-PB — Industrial control network incident playbook
category: Cybersecurity
hazard: CYBER_INTRUSION
keywords: [cyber, ot, network, intrusion, unauthorized, rogue, device, mac, modbus, plc, gateway, isolation, quarantine, vlan, brute force, spoofed, sensor, traffic, forensics]
---

## 1 Scope

Covers the operational technology network: PLCs, the Modbus gateway, the managed OT switch and
every field device on the industrial segment. It does not cover the office IT network.

## 2 Classifying an event

2.1 **UNKNOWN_DEVICE** — a device whose MAC or IP is absent from the asset inventory appears on
the OT segment.

2.2 **BRUTE_FORCE** — repeated failed authentication attempts from one source against a
controller. Threshold: more than 20 failures from the same source within 60 seconds.

2.3 **UNAUTHORIZED_COMMAND** — a write or control command reaching a controller from a source
that is not on the engineering whitelist.

2.4 **TRAFFIC_ANOMALY** — segment traffic volume departing from its established baseline by more
than three standard deviations.

2.5 **SPOOFED_SENSOR** — a sensor reading that is physically inconsistent with correlated
sensors: a temperature that does not move while the machine it sits on heats, or a reading that
changes faster than the physical process allows.

## 3 Containment

### 3.1 Automatic, no authorisation required

3.1.1 Engage OT VLAN quarantine on the core switch. This limits the blast radius without cutting
any control path and is therefore low risk.

### 3.2 On the owner's authorisation

3.2.1 **Isolate the offending device** — block its MAC and disable its switch port. This is the
action that removes the hazard.
3.2.2 Switch critical controllers to isolated local run mode so production survives the
isolation.

### 3.3 Prohibited

3.3.1 **Do not power-cycle controllers.** Volatile memory holds the forensic evidence.
3.3.2 Do not re-admit an isolated device before the forensic capture is complete.

## 4 A spoofed sensor changes how other agents must reason

4.1 When a sensor is judged to be spoofed, its readings must be **distrusted, not ignored.**
Ignoring them hides a real physical hazard; trusting them lets an attacker mask one.

4.2 The correct response is to reduce that sensor's weight in any risk assessment (a trust factor
of roughly 0.2) and to rely on physically independent sensors for the same hazard.

4.3 A machine overheating must still be detected even when its own temperature sensor has been
spoofed — that is precisely the attack this clause exists to defeat. Corroborate with pressure,
vibration and the machine's own body temperature.

4.4 Record the distrust decision explicitly in the incident evidence so a reviewer can see which
readings were down-weighted and why.

## 5 Forensics and reporting

5.1 Capture the PCAP buffer for the affected segment before any containment action.
5.2 Record the device identifier, the target controller and the attempt count in the incident.
5.3 Map the observed behaviour to a MITRE ATT&CK for ICS technique, by looking the technique up
in the published ATT&CK data — never from memory.
5.4 The plant security officer, not the production owner, approves re-admission of a device.
