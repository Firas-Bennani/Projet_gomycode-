---
doc_id: MAINT-PLAN
title: MAINT-PLAN — Preventive maintenance and post-incident release
category: Maintenance
hazard: MACHINE_OVERHEATING
keywords: [maintenance, preventive, service, interval, coolant, filter, seal, bearing, inspection, cmms, release, restart, sign-off, spare]
---

## 1 Scope

Preventive maintenance intervals for ZONE_B assets and the sign-off required before a machine
returns to production after an automatic or commanded shutdown.

## 2 Intervals for M-04

| Task | Interval | Notes |
|---|---|---|
| Coolant loop filter | 250 operating hours | Restriction here is the most common cause of a thermal excursion |
| Hydraulic seal inspection | 500 h | Replace on any weep, not only on leak |
| Spindle bearing vibration survey | 1000 h | Trend the RMS value; act on the trend, not one reading |
| Heat exchanger descale | 2000 h | Pump PUMP-COOL-02 included |
| Safety valve calibration | 12 months | Certified test at 8.2 bar |

## 3 Post-incident release to production

3.1 A machine that shut down on a thermal or hydraulic trip is **out of service** until released,
regardless of what the live readings now say. A falling temperature is not a repair.

3.2 Release requires, in order:

3.2.1 coolant loop flow verified at or above 45 L/min at the heat exchanger;
3.2.2 hydraulic circuit held at working pressure for 10 minutes with no decay;
3.2.3 no vibration alarm through a full test cycle;
3.2.4 maintenance sign-off recorded in the CMMS against the incident id.

3.3 The incident record and the CMMS work order must reference each other. An incident closed
without a work order is an audit finding.

## 4 Root causes seen on this asset

4.1 Coolant filter restriction — presents as body temperature rising while ambient is normal.
4.2 Failing hydraulic accumulator — presents as pressure rising faster than 0.3 bar/min under
constant load.
4.3 Bearing wear — presents as vibration above 5.0 mm/s with only a mild temperature rise.
4.4 Blocked heat exchanger — presents as both temperature and pressure climbing together, which
is the signature the copilot treats as a critical mechanical fault.

## 5 Spares held on site

5.1 Coolant filter cartridges — 4 in stock, reorder at 2.
5.2 Hydraulic seal kit for M-04 — 1 in stock, single point of failure, reorder immediately on use.
5.3 Spindle bearing set — not stocked, 5-day lead time. Plan shutdowns around this.
