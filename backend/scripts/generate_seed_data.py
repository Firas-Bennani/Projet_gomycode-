"""Generate deterministic seed data for Industrial_Copilot (workers + inventory).

Deterministic: a fixed `random.seed`, so the same file is produced every run and the repo does not
churn. Regenerate with:  python backend/scripts/generate_seed_data.py

**The five workers the demo scenarios depend on (W23, W41, W52 in ZONE_B, W12, W09) are NOT
generated here.** They stay hardcoded in `state_store.py` exactly as they were, and this data is
*appended* to them. Same for machines. That is deliberate: the simulator, the agents and the
scenario tests all reference those ids, and a seed file must not be able to move them.
"""

import json
import pathlib
import random
from datetime import datetime, timedelta

SEED = 20260927
OUT = pathlib.Path(__file__).resolve().parents[1] / "app" / "data" / "seed"

FIRST_NAMES = [
    "Ahmed", "Mohamed", "Youssef", "Karim", "Slim", "Bilel", "Hatem", "Nizar", "Walid", "Tarek",
    "Sami", "Anis", "Riadh", "Mehdi", "Aymen", "Sofiene", "Wassim", "Hamza", "Khalil", "Zied",
    "Sarah", "Amira", "Ines", "Rim", "Nour", "Salma", "Yosra", "Mariem", "Dorra", "Hiba",
    "Olfa", "Sonia", "Leila", "Nadia", "Asma", "Fatma", "Mouna", "Hela", "Imen", "Rania",
]
LAST_NAMES = [
    "Ben Ali", "Trabelsi", "Bouazizi", "Mansouri", "Gharbi", "Chaabane", "Jebali", "Haddad",
    "Khelifi", "Sassi", "Ayari", "Bouzid", "Nasri", "Hamdi", "Zouari", "Karoui", "Mejri",
    "Ferchichi", "Amri", "Belhadj", "Tounsi", "Ouali", "Rekik", "Dridi", "Slimani", "Aloui",
]
ROLES = [
    ("CNC Technician", "Machining"), ("Maintenance Specialist", "Maintenance"),
    ("Safety Inspector", "HSE"), ("Quality Controller", "Quality"),
    ("Furnace Operator", "Heat Treatment"), ("Robotics Technician", "Assembly"),
    ("Logistics Handler", "Logistics"), ("Electrical Technician", "Maintenance"),
    ("Press Operator", "Machining"), ("Shift Supervisor", "Operations"),
]
# ZONE_B is deliberately excluded. The worker agent still reports the three ZONE_B workers it
# knows (W23/W41/W52) on an incident, so adding more staff there would make the Workers page say
# eight while the incident card says three. Until the worker agent reads the state store (Step 9,
# cut for time) the honest option is to keep ZONE_B staffed by exactly those three.
ZONES = ["ZONE_A", "ZONE_C", "ZONE_D"]
SHIFTS = [("Morning", "06:00", "14:00"), ("Afternoon", "14:00", "22:00"), ("Night", "22:00", "06:00")]
CERTS = ["ISO 45001 Awareness", "Forklift Licence", "LOTO Authorised", "Confined Space",
         "First Aid", "Hot Work Permit", "Electrical LV", "Crane Signalling"]

CATEGORIES = {
    "Raw Material": [("Steel billet S235", "kg"), ("Aluminium sheet 3mm", "kg"),
                     ("Cast iron block", "kg"), ("Copper wire 2.5mm", "m"),
                     ("Brass rod 20mm", "kg"), ("Stainless coil 304", "kg")],
    "Consumable": [("Cutting fluid emulsion", "L"), ("Hydraulic oil ISO 46", "L"),
                   ("Welding wire ER70S", "kg"), ("Abrasive disc 230mm", "pcs"),
                   ("Nitrile gloves", "pairs"), ("Coolant filter cartridge", "pcs"),
                   ("Degreaser concentrate", "L"), ("Argon shielding gas", "m3")],
    "Spare Part": [("Spindle bearing SKF 6206", "pcs"), ("Hydraulic seal kit M-04", "kit"),
                   ("Contactor 24V DC", "pcs"), ("Proximity sensor M12", "pcs"),
                   ("Drive belt A-1250", "pcs"), ("Thermocouple type K", "pcs"),
                   ("Safety relay PNOZ", "pcs"), ("Air dryer element", "pcs")],
    "Finished Good": [("Machined flange DN80", "pcs"), ("Gearbox housing", "pcs"),
                      ("Valve body 2in", "pcs"), ("Bracket assembly", "pcs"),
                      ("Shaft 40x300", "pcs"), ("Pump casing", "pcs"),
                      ("Coupling half", "pcs"), ("Cover plate", "pcs")],
}
SUPPLIERS = ["Sidérurgie Tunisie SA", "MetalPro Sfax", "Techni-Fluides SARL", "Industrial Bearings Co",
             "Gaz Industriels Tunisie", "ElectroParts Sousse", "Nord Abrasifs", "Hydro-Tech Tunis"]


def main() -> None:
    random.seed(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime(2026, 9, 27, 8, 0, 0)

    # ---- workers: 35 extra, ids from W100 so they can never clash with W09..W52 ----
    workers = []
    used = set()
    for index in range(35):
        while True:
            name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            if name not in used:
                used.add(name)
                break
        role, team = random.choice(ROLES)
        shift, shift_start, shift_end = random.choice(SHIFTS)
        zone = random.choice(ZONES)
        hours = round(random.uniform(28, 46), 1)
        workers.append({
            "id": f"W{100 + index}",
            "badge": f"BDG-{4200 + index}",
            "name": name,
            "role": role,
            "team": team,
            "zone": zone,
            "shift": shift,
            "shift_start": shift_start,
            "shift_end": shift_end,
            "status": random.choice(["ON_SITE", "ON_SITE", "ON_SITE", "OFF_SITE", "ON_BREAK"]),
            "entry_time": shift_start,
            "working_hours_today": round(random.uniform(1.5, 8.0), 1),
            "hours_this_week": hours,
            "overtime_hours": round(max(0.0, hours - 40), 1),
            "productivity_pct": round(random.uniform(78, 99), 1),
            "ppe": {
                "helmet": random.random() > 0.05,
                "vest": random.random() > 0.04,
                "gloves": random.random() > 0.12,
                "safety_shoes": random.random() > 0.03,
            },
            "certifications": sorted(random.sample(CERTS, random.randint(1, 4))),
            "last_entry": (now - timedelta(hours=random.uniform(0.5, 9))).isoformat(timespec="minutes"),
            "last_exit": (now - timedelta(hours=random.uniform(10, 20))).isoformat(timespec="minutes"),
        })

    # ---- inventory: 30 items with 30 days of movements ----
    inventory = []
    counter = 0
    for category, items in CATEGORIES.items():
        for label, unit in items:
            counter += 1
            daily = round(random.uniform(2, 60), 1)
            minimum = round(daily * random.uniform(3, 6), 1)
            reorder = round(minimum * random.uniform(1.3, 1.9), 1)
            # A few items are deliberately below their threshold so the low-stock alerts have
            # something real to show.
            stock = round(minimum * random.uniform(0.4, 0.95), 1) if counter % 7 == 0 \
                else round(reorder * random.uniform(1.1, 3.0), 1)
            movements = []
            for day in range(30, 0, -1):
                date = (now - timedelta(days=day)).date().isoformat()
                out = round(daily * random.uniform(0.5, 1.5), 1)
                movements.append({"date": date, "issued": out,
                                  "received": round(reorder * 2, 1) if day % 11 == 0 else 0.0})
            inventory.append({
                "id": f"INV-{counter:03d}",
                "sku": f"{category[:2].upper()}-{1000 + counter}",
                "name": label,
                "category": category,
                "unit": unit,
                "stock": stock,
                "min_threshold": minimum,
                "reorder_point": reorder,
                "supplier": random.choice(SUPPLIERS),
                "lead_time_days": random.randint(2, 21),
                "daily_consumption": daily,
                "days_of_cover": round(stock / daily, 1) if daily else None,
                "status": "CRITICAL" if stock < minimum else ("LOW" if stock < reorder else "NORMAL"),
                "unit_cost_tnd": round(random.uniform(3, 480), 2),
                "movements_30d": movements,
            })

    for filename, payload, note in (
        ("workers.json", workers,
         "35 additional workers, ids from W100. The demo workers W09/W12/W23/W41/W52 stay in "
         "state_store.py and are NOT listed here, because the simulator and the scenario tests "
         "reference them by id."),
        ("inventory.json", inventory,
         "30 stock items across raw material, consumables, spare parts and finished goods, each "
         "with 30 days of movements. Roughly one in seven is deliberately below its threshold so "
         "the low-stock alerts have real data."),
    ):
        path = OUT / filename
        path.write_text(json.dumps(
            {"_comment": note, "_generated_by": "backend/scripts/generate_seed_data.py",
             "_seed": SEED, "items": payload}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        print(f"  {path.name}: {len(payload)} records")

    low = [i for i in inventory if i["status"] != "NORMAL"]
    print(f"  ({len(low)} inventory items are LOW or CRITICAL, so the alerts are not empty)")


if __name__ == "__main__":
    main()
