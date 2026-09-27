from typing import List, Dict, Any, Optional
import re

KNOWLEDGE_DOCUMENTS = [
    {
        "id": "EP-07",
        "title": "Emergency Protocol EP-07: Heavy Machine Overheating & Pressure Spikes",
        "category": "Emergency Procedures",
        "content": """Standard Operating Procedure for CNC/Milling Thermal Spikes:
1. When core temperature exceeds 50°C and hydraulic pressure exceeds 8.0 bar, initiate immediate controlled shutdown.
2. Evacuate all non-essential personnel within a 15-meter perimeter (Zone B).
3. Engage auxiliary coolant circulation bypass to prevent spindle seizure.
4. Verify complete mechanical standstill before opening access doors.
5. Notify Shift Supervisor and log incident in Plant CMMS.""",
        "keywords": ["overheating", "temperature", "pressure", "m-04", "shutdown", "cooling", "spindle", "hydraulic", "zone b"]
    },
    {
        "id": "EP-03",
        "title": "Emergency Protocol EP-03: Combustion Aerosol & Fire Suppression Protocol",
        "category": "Safety Protocols",
        "content": """Industrial Fire Suppression Protocol:
1. Upon dual confirmation from optical smoke sensors (>25 ppm) and thermal sensors (>45°C), declare Tier-1 Fire Emergency.
2. Sound acoustic and optical plant-wide evacuation alarms.
3. Automatically close fire containment doors (D-01 to D-04) to seal ventilation dampers.
4. Trigger clean-agent / high-pressure water mist suppression system after 30-second delay for personnel evacuation.
5. De-energize high-voltage 400V machine supply lines in affected sector.""",
        "keywords": ["fire", "smoke", "suppression", "water", "alarm", "evacuate", "flame", "combustion"]
    },
    {
        "id": "EP-12",
        "title": "Emergency Protocol EP-12: OT Industrial Cyber Threat Containment",
        "category": "Cybersecurity",
        "content": """OT Network Defense Protocol:
1. If an unauthorized MAC or IP address attempts repeated handshakes to PLC or Edge Gateways, classify as Rogue Device Intrusion.
2. Immediately trigger network port isolation on the managed Hirschmann OT switch.
3. Switch critical machine controllers to isolated local run mode.
4. Capture packet capture (PCAP) forensic buffer for audit.
5. Do NOT power cycle controllers to preserve volatile memory logs.""",
        "keywords": ["cyber", "unauthorized", "device", "isolation", "network", "modbus", "traffic", "intrusion"]
    },
    {
        "id": "MAN-M04",
        "title": "Technical Operating Manual: CNC Lathe / Heavy Milling Unit M-04",
        "category": "Equipment Manuals",
        "content": """Operational Specifications for Machine M-04:
- Maximum Continuous Operating Temperature: 75.0°C (Critical Limit: 80.0°C)
- Maximum Safe Hydraulic Line Pressure: 7.5 bar (Safety Valve Tripping Point: 8.0 bar)
- Optimal Spindle Velocity: 1200 - 1500 RPM (Overspeed trip: 1800 RPM)
- Vibration Tolerance: < 4.5 mm/s RMS (Bearing failure threshold: 6.0 mm/s)
- Automatic emergency shutdown trigger: Pressure sustained above 8.2 bar for > 15 seconds.""",
        "keywords": ["m-04", "milling", "lathe", "specifications", "limits", "tolerance", "bearing", "rpm"]
    },
    {
        "id": "REG-ISO45001",
        "title": "ISO 45001 & OSHA 1910 Industrial Worker Safety Standards",
        "category": "Regulations",
        "content": """Worker Safety Compliance Standards:
- Mandatory PPE in designated Sector B & C zones: ANSI-certified hard hat, high-visibility vest, cut-resistant gloves, steel-toed boots.
- Maximum continuous shift in high-decibel areas (>85 dBA): 4 consecutive hours without rotation.
- In event of any Tier-1 or Tier-2 hazard alarm, all workers must evacuate to Muster Point Alpha via designated escape corridors.""",
        "keywords": ["ppe", "worker", "safety", "helmet", "vest", "evacuation", "osha", "compliance", "muster"]
    }
]

class RAGEngine:
    def __init__(self):
        self.documents = KNOWLEDGE_DOCUMENTS

    def query(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        query_words = set(re.findall(r'\w+', user_query.lower()))
        if context:
            for k, v in context.items():
                if isinstance(v, str):
                    query_words.update(re.findall(r'\w+', v.lower()))

        scored_docs = []
        for doc in self.documents:
            score = 0
            for kw in doc["keywords"]:
                if kw in query_words or any(kw in word for word in query_words):
                    score += 2
            for word in query_words:
                if len(word) > 3 and word in doc["content"].lower():
                    score += 1
            if score > 0:
                relevance = min(0.98, 0.65 + (score * 0.05))
                scored_docs.append((relevance, doc))

        scored_docs.sort(key=lambda x: x[0], reverse=True)

        if not scored_docs:
            top_doc = self.documents[0]
            scored_docs = [(0.75, top_doc)]

        best_score, best_doc = scored_docs[0]
        answer = f"According to {best_doc['title']}:\n{best_doc['content']}"

        sources = [
            {
                "document": doc["title"],
                "section": doc["category"],
                "relevance": round(score, 2)
            }
            for score, doc in scored_docs[:3]
        ]

        return {
            "answer": answer,
            "sources": sources
        }

rag_engine = RAGEngine()
