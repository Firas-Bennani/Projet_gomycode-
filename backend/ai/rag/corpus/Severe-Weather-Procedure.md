---
doc_id: WX-SP-07
title: WX-SP-07 — Severe weather and thunderstorm preparation
category: Safety Protocols
hazard: SEVERE_WEATHER_RISK
zone: SITE
keywords: [storm, thunderstorm, lightning, weather, forecast, gust, wind, cape, surge, load shedding, shed, derate, setpoint, pressure, ups, generator, outage, switchyard, electrical room, crew, 30-30 rule, predictive]
---

## 1 Scope

Applies to the whole site whenever a thunderstorm, a squall line or damaging gusts are forecast
over the plant. Unlike every other procedure in this corpus, this one is **acted on before the
event**: its value is entirely in the lead time. Once the front is overhead only §7 (lightning
safety) still applies.

Assets exposed to a storm at this site: the outdoor switchyard, electrical room B, and the
compressor house that contains M-04. Outdoor and semi-outdoor work areas are ZONE_B and ZONE_D.

## 2 Forecast thresholds

2.1 Raise a severe weather risk when the hourly forecast for the site shows **either**:

- a thunderstorm WMO weather code (95 thunderstorm, 96 thunderstorm with slight hail,
  99 thunderstorm with heavy hail) with a precipitation probability of 50 % or more; **or**
- wind gusts of 60 km/h or more.

2.2 Escalate to a critical preparation when any of:

- precipitation probability 70 % or more together with a thunderstorm code;
- CAPE (convective available potential energy) of 2000 J/kg or more, which indicates strong
  instability and therefore a real chance of a severe cell rather than passing rain;
- gusts of 90 km/h or more.

2.3 CAPE bands used here: below 1000 J/kg weak instability, 1000–2000 J/kg moderate,
above 2000 J/kg strong. CAPE alone is not a forecast — it is treated as a confidence
modifier on top of the precipitation probability, never as the probability itself.

2.4 A forecast is a probability, not a measurement. Confidence in a weather risk is therefore
capped below 0.97 no matter how strong the indicators are, and the incident text must state the
remaining lead time so the operator can judge for themselves.

## 3 Load shedding

3.1 At 60 minutes of lead time or less, shed non-critical electrical load and derate running
machines to about 60 % of nominal. Two reasons: less load is exposed to a surge or a sag, and a
derated machine stores less energy, so a sudden trip is a smaller transient.

3.2 Do not shed load feeding safety systems: fire detection and suppression, emergency lighting,
evacuation signage, gas detection, or the control network itself (see §5).

## 4 Pressure setpoints

4.1 Lower the compressor pressure setpoint on M-04 from 8.0 bar to **6.5 bar**. The 8.0 bar
figure is the alarm limit from SOP-M04 §3.1, not a target; running at 6.5 bar widens the margin
to 1.5 bar so a surge-driven excursion during the storm cannot reach the limit.

4.2 Restore the normal setpoint only after the front has cleared the site and the electrical
supply has been stable for 15 minutes.

## 5 Control power and UPS

5.1 Transfer PLCs, the Modbus gateway and the historian to UPS-MAIN-01 before the front arrives.
A control layer that dies mid-storm turns a weather event into a blind plant.

5.2 Verify backup generator readiness at the same time: fuel level, auto-start armed, transfer
switch in AUTO. Verify, do not test-start, once gusts have begun.

## 6 Crew

6.1 Call the on-call electrical crew to the exposed zone so a fault during the storm is handled
in minutes rather than after a call-out. Minimum two qualified technicians.

6.2 Move planned outdoor and roof work to after the event. No work at height, on the switchyard,
or with a crane once §2.1 is met.

## 7 Lightning safety

7.1 Suspend outdoor work and clear open areas when thunder is heard or lightning is detected
within 15 km.

7.2 Apply the 30/30 rule: seek shelter when the interval between the flash and the thunder is
30 seconds or less, and stay sheltered until 30 minutes after the last thunder. Restarting
outdoor work between cells is the most common way people are struck.

## 8 Stand-down and recovery

8.1 Stand down when the forecast probability falls below 50 % and gusts are below 60 km/h.

8.2 Before restoring load: walk the switchyard and electrical room B, check for tripped
protection, water ingress and displaced covers, then restore load in steps, not all at once.

8.3 Record the forecast that triggered the preparation, what was authorised, and what the peak
measured pressure and gust were. A prepared storm that causes nothing still has to be evidenced;
that record is what justifies the next preparation.
