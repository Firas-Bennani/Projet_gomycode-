---
doc_id: SOP-M04
title: SOP-M04 — Heavy Milling Unit M-04, thermal and hydraulic excursions
category: Emergency Procedures
hazard: MACHINE_OVERHEATING
asset: M-04
zone: ZONE_B
keywords: [overheating, overtemperature, overpressure, temperature, pressure, m-04, milling, compressor, shutdown, cooling, spindle, hydraulic, bearing, vibration, zone b]
---

## 1 Scope

This procedure covers the Heavy Industrial Milling Unit **M-04** in **ZONE_B**, including its
hydraulic circuit and the auxiliary cooling loop served by pump **PUMP-COOL-02**. It applies to
any thermal or hydraulic excursion, whether detected by the operator or raised automatically by
the plant copilot.

## 2 Operating envelope

| Parameter | Normal | Warning | Limit / trip |
|---|---|---|---|
| Hydraulic line pressure | 4.5 – 6.5 bar | 7.2 bar | **8.0 bar** (safety valve 8.2 bar) |
| Machine body temperature | 40 – 65 °C | 72 °C (90 % of limit) | **80 °C** |
| Ambient temperature, ZONE_B | 22 – 28 °C | 35 °C | **50 °C** |
| Spindle speed | 1200 – 1500 RPM | — | 1800 RPM overspeed trip |
| Vibration (RMS) | < 4.5 mm/s | 5.0 mm/s | 6.0 mm/s bearing failure |

## 3 Interpreting a rising trend

3.1 A pressure rise faster than **0.3 bar per minute** sustained for more than one minute
indicates a restriction downstream of the pump, not a load change. Treat it as a fault.

3.2 A body temperature within 10 % of its 80 °C limit is a warning even when pressure is
nominal: the two failure modes share a root cause in the cooling loop.

3.3 Do not act on a single sample. Corroborate with a second parameter or a second reading
before declaring an incident. A trend requires at least 10 seconds of history to be meaningful.

## 4 Response

### 4.1 Warning level — pressure ≥ 7.2 bar or body temperature ≥ 72 °C

4.1.1 Reduce feed rate and confirm the coolant return line is not restricted.
4.1.2 Engage auxiliary cooling via **PUMP-COOL-02** and verify a flow rate of at least
45 L/min at the heat exchanger.
4.1.3 Keep personnel outside the 5-metre working envelope while the machine is under load.

### 4.2 Critical level — pressure ≥ 8.0 bar or body temperature ≥ 80 °C

4.2.1 **Initiate a controlled emergency shutdown of M-04.** This is the action that removes the
hazard; cooling and evacuation support it but do not resolve it.
4.2.2 Confirm spindle RPM reads zero and the hydraulic main valve is depressed before treating
the machine as safe.
4.2.3 Evacuate all non-essential personnel from the 15-metre perimeter in ZONE_B.
4.2.4 Leave auxiliary cooling running until the body temperature is below 60 °C.
4.2.5 The shutdown stops production, so it requires the system owner's explicit authorisation.
Do not automate it.

### 4.3 Verification before closing the incident

4.3.1 Spindle at zero RPM, hydraulic pressure below 7.0 bar and falling.
4.3.2 Body temperature below its 80 °C limit and falling.
4.3.3 Zero personnel detected inside the perimeter.
4.3.4 An incident may only be closed when the readings are **receding**, not merely when the
commanded actions report success.

## 5 Prohibited actions

5.1 Never discharge fire suppression on a hot machine that shows no combustion signature. Water
or clean agent on a hydraulic overpressure fault adds a thermal shock risk and destroys
evidence. Suppression requires smoke or flame confirmation — see FIRE-EP-03 §2.

5.2 Never restart M-04 after a thermal trip until maintenance has signed off the cooling loop
(see MAINT-PLAN §3.2).
