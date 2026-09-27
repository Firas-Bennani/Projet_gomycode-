# Industrial_Copilot — rename, authentication, richer seed data, Events and Clients pages

Final pass before submission, branch `final-touches` off `upstream/main`. Items were done in a
fixed order with a commit after each, and the three demo scenarios were kept working throughout.

## 1. Rename to `Industrial_Copilot`

The product name is exactly **`Industrial_Copilot`**. Updated everywhere it is user-visible —
browser tab title, dashboard header, backend `PROJECT_NAME` and startup logs, README title and
prose, and our own docs. **No code identifiers or file names were renamed**, so nothing imports
differently and no teammate's import breaks.

The separate `standalone-3d-ai-copilot/` app was left alone: it is a teammate's parallel build with
its own branding, and renaming inside it was not asked for.

## 3. Richer seed data — PARTIAL (shipped the safe core, ran out of clock)

`backend/scripts/generate_seed_data.py`, deterministic (`seed=20260927`), writing
`backend/app/data/seed/`:

- **`workers.json` — 35 additional workers** with Tunisian names, role, team, shift and window,
  zone, badge, PPE status, hours this week, overtime, productivity %, certifications, last
  entry/exit. Loaded on top of the existing five, giving **40 workers**.
- **`inventory.json` — 30 items** across raw material, consumables, spare parts and finished goods,
  each with SKU, unit, stock, min threshold, reorder point, supplier, lead time, daily consumption,
  days of cover, unit cost in TND and **30 days of movements**. Five items sit below threshold so
  the low-stock alerts have real data. Total **34 inventory items**.

**The loader is deliberately additive and guarded.** The simulator, the agents and the scenario
tests reference `W23/W41/W52`, `M-01..M-06` and the ZONE_B sensors *by id*, so those stay defined in
`state_store.py` and are never overwritten; a `try/except` means a missing or malformed seed file
leaves the platform running exactly as before.

**One consistency trap avoided:** the extra workers are placed in ZONE_A/C/D only. Putting any in
ZONE_B would have made the Workers page say eight people while the incident card said three,
because the worker agent still reports its own three (reading it from the state store was Step 9,
which was cut). Rather than create a visible contradiction on stage, ZONE_B stays staffed by
exactly those three, with the reason written next to the constant.

**Not done in item 3:** machine 24 h history for charts, OEE and energy series, and wiring the
richer fields (certifications, movements, days of cover) into the page components — the existing
pages read the original schema and already show the new rows, so no page is empty, but they do not
yet show the new columns.

## 4. Events page — NOT STARTED
## 5. Clients page — NOT STARTED

Ran out of the 15:45 coding deadline. Items 1–3 are complete-and-tested / safe-partial as above.
