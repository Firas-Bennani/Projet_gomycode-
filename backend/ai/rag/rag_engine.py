"""Keyword retrieval over the procedure corpus in ``backend/ai/rag/corpus/``.

Two consumers:

* the agents, which call :meth:`RAGEngine.query` while synthesising an incident;
* the n8n AI Agent (Step 5), which reaches the same retrieval through
  ``POST /api/ai/rag/query`` as a tool. That matters because n8n's Simple Vector Store is
  in-memory and declares itself experimental — "data is lost if n8n restarts, and may be
  cleared if available memory gets low". So the vector store is the fast path and this is the
  path that always works.

Retrieval is per **section**, not per document, so a citation can be specific: the incident
explanation says `SOP-M04 §4.2` rather than naming a whole procedure. Sections come from the
``## N.N Title`` headings in the Markdown.

If the corpus directory is missing, the engine falls back to the original hardcoded documents so
nothing breaks.
"""

import logging
import pathlib
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("rag_engine")

CORPUS_DIR = pathlib.Path(__file__).resolve().parent / "corpus"

# Words too common in this domain to discriminate between procedures.
STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "must", "not", "any", "all",
    "when", "then", "than", "been", "have", "has", "was", "were", "are", "its", "it's", "a", "an",
    "of", "to", "in", "on", "at", "by", "is", "be", "or", "if", "as", "up", "out", "no",
}

# Kept as a last-resort fallback if the corpus files are unavailable.
KNOWLEDGE_DOCUMENTS = [
    {
        "id": "EP-07",
        "title": "Emergency Protocol EP-07: Heavy Machine Overheating & Pressure Spikes",
        "category": "Emergency Procedures",
        "content": (
            "1. When core temperature exceeds 50°C and hydraulic pressure exceeds 8.0 bar, "
            "initiate immediate controlled shutdown.\n"
            "2. Evacuate all non-essential personnel within a 15-meter perimeter (Zone B).\n"
            "3. Engage auxiliary coolant circulation bypass to prevent spindle seizure."
        ),
        "keywords": ["overheating", "temperature", "pressure", "m-04", "shutdown", "cooling"],
    },
    {
        "id": "EP-03",
        "title": "Emergency Protocol EP-03: Combustion Aerosol & Fire Suppression Protocol",
        "category": "Safety Protocols",
        "content": (
            "1. Upon dual confirmation from optical smoke sensors and thermal sensors, declare a "
            "Tier-1 Fire Emergency.\n2. Sound plant-wide evacuation alarms.\n"
            "3. Close fire containment doors, then discharge clean-agent suppression."
        ),
        "keywords": ["fire", "smoke", "suppression", "alarm", "evacuate", "combustion"],
    },
    {
        "id": "EP-12",
        "title": "Emergency Protocol EP-12: OT Industrial Cyber Threat Containment",
        "category": "Cybersecurity",
        "content": (
            "1. Classify repeated handshakes from an unregistered MAC as a rogue device "
            "intrusion.\n2. Isolate the switch port.\n"
            "3. Do NOT power cycle controllers — volatile memory holds the evidence."
        ),
        "keywords": ["cyber", "unauthorized", "device", "isolation", "network", "intrusion"],
    },
]


def _tokenise(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9\-\.]+", text.lower()) if w not in STOPWORDS and len(w) > 1}


def _parse_front_matter(raw: str) -> tuple:
    """Return (metadata, body). Tiny parser — no YAML dependency in requirements."""
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end == -1:
        return {}, raw
    block, body = raw[3:end], raw[end + 4:]
    meta: Dict[str, Any] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key] = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key] = value.strip('"').strip("'")
    return meta, body


class Section:
    __slots__ = ("doc_id", "doc_title", "category", "hazard", "number", "heading", "text",
                 "keywords", "tokens")

    def __init__(self, doc_id, doc_title, category, hazard, number, heading, text, keywords):
        self.doc_id = doc_id
        self.doc_title = doc_title
        self.category = category
        self.hazard = hazard
        self.number = number
        self.heading = heading
        self.text = text
        self.keywords = keywords
        self.tokens = _tokenise(f"{heading} {text}")

    @property
    def citation(self) -> str:
        return f"{self.doc_id} §{self.number}" if self.number else self.doc_id

    @property
    def label(self) -> str:
        return f"§{self.number} {self.heading}".strip() if self.number else self.heading


class RAGEngine:
    def __init__(self, corpus_dir: pathlib.Path = CORPUS_DIR):
        self.corpus_dir = corpus_dir
        self.sections: List[Section] = []
        self.documents: List[Dict[str, Any]] = []
        self.load()

    # ------------------------------------------------------------------ loading

    def load(self) -> int:
        self.sections = []
        self.documents = []
        files = sorted(self.corpus_dir.glob("*.md")) if self.corpus_dir.is_dir() else []

        for path in files:
            try:
                meta, body = _parse_front_matter(path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not read %s: %s", path.name, exc)
                continue

            doc_id = meta.get("doc_id") or path.stem
            doc_title = meta.get("title") or path.stem
            category = meta.get("category", "Procedure")
            hazard = meta.get("hazard", "ANY")
            keywords = [k.lower() for k in (meta.get("keywords") or [])]

            self.documents.append({
                "id": doc_id, "title": doc_title, "category": category,
                "hazard": hazard, "keywords": keywords, "content": body.strip(),
                "file": path.name,
            })

            for number, heading, text in self._split_sections(body):
                self.sections.append(Section(doc_id, doc_title, category, hazard,
                                             number, heading, text, keywords))

        if not self.sections:
            logger.warning("No corpus found in %s — using the built-in fallback documents.",
                           self.corpus_dir)
            for doc in KNOWLEDGE_DOCUMENTS:
                self.documents.append(doc)
                self.sections.append(Section(doc["id"], doc["title"], doc["category"], "ANY",
                                            "", doc["title"], doc["content"], doc["keywords"]))
        else:
            logger.info("Loaded %d sections from %d procedure documents.",
                        len(self.sections), len(self.documents))
        return len(self.sections)

    @staticmethod
    def _split_sections(body: str) -> List[tuple]:
        """Split on `## ` headings, keeping the leading number as the section id."""
        sections: List[tuple] = []
        current = None
        buffer: List[str] = []
        for line in body.splitlines():
            if line.startswith("## ") or line.startswith("### "):
                if current is not None:
                    sections.append((current[0], current[1], "\n".join(buffer).strip()))
                heading = line.lstrip("#").strip()
                match = re.match(r"^([0-9]+(?:\.[0-9]+)*)\s+(.*)$", heading)
                current = (match.group(1), match.group(2)) if match else ("", heading)
                buffer = []
            else:
                buffer.append(line)
        if current is not None:
            sections.append((current[0], current[1], "\n".join(buffer).strip()))
        return [s for s in sections if s[2]]

    # ------------------------------------------------------------------ retrieval

    def search(self, user_query: str, context: Optional[Dict[str, Any]] = None,
               limit: int = 4, hazard: Optional[str] = None) -> List[Dict[str, Any]]:
        """Top matching sections, each with a citable reference."""
        query_tokens = _tokenise(user_query)
        if context:
            for value in context.values():
                if isinstance(value, str):
                    query_tokens |= _tokenise(value)

        scored = []
        for section in self.sections:
            score = 0.0
            overlap = query_tokens & section.tokens
            score += len(overlap)
            score += 2.0 * len(query_tokens & set(section.keywords))
            if hazard and section.hazard in (hazard, "ANY"):
                score += 3.0
            if score <= 0:
                continue
            scored.append((score, section))

        scored.sort(key=lambda pair: (-pair[0], pair[1].doc_id, pair[1].number))
        if not scored:
            return []

        best = scored[0][0]
        results = []
        for score, section in scored[:limit]:
            results.append({
                "document": section.doc_id,
                "document_title": section.doc_title,
                "section": section.label,
                "citation": section.citation,
                "category": section.category,
                "hazard": section.hazard,
                # Normalised against the best hit, so it reads as a relative ranking rather
                # than a probability we cannot justify.
                "relevance": round(min(0.99, 0.55 + 0.44 * (score / best)), 2),
                "text": section.text,
            })
        return results

    def query(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Backwards-compatible entry point used by the agents and ``POST /api/ai/rag/query``.

        Returns the shape ``RAGQueryResponse`` expects: ``{answer, sources}``.
        """
        hazard = None
        if context:
            hazard = context.get("hazard") or context.get("incident_type")
        hits = self.search(user_query, context=context, hazard=hazard)

        if not hits:
            return {
                "answer": "No procedure section matches this query.",
                "sources": [],
            }

        answer_parts = [f"{hit['document']} {hit['section']}:\n{hit['text']}" for hit in hits[:2]]
        return {
            "answer": "\n\n".join(answer_parts),
            "sources": [
                {"document": hit["document_title"], "section": hit["section"],
                 "relevance": hit["relevance"]}
                for hit in hits
            ],
        }


rag_engine = RAGEngine()
