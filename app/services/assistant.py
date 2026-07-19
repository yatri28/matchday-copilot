"""Matchday assistant orchestration.

Two-tier design:

1. **GenAI tier** — when ``ANTHROPIC_API_KEY`` is set, the fan's question
   is answered by Claude, *grounded* in a context pack built from live
   service data (crowd snapshot, venue map, fixtures). The model is told
   to answer only from that context, in the fan's language.
2. **Offline tier** — with no key configured, a transparent rule-based
   intent router answers from the same services, so the app is fully
   demoable and testable anywhere. The response's ``source`` field always
   discloses which tier produced the answer.
"""

import json
import re
from pathlib import Path
from typing import Optional

import httpx

from ..config import Settings
from . import crowd, i18n, navigation

MATCHES_PATH = Path(__file__).resolve().parent.parent / "data" / "matches.json"

SYSTEM_PROMPT = (
    "You are MatchDay Copilot, a stadium assistant for fans at the FIFA "
    "World Cup 2026. Answer ONLY from the provided venue context. Be "
    "concise (under 120 words), warm, and practical. Reply in the "
    "language with ISO code '{lang}'. If the fan indicated accessibility "
    "needs, prioritise step-free routes and accessible facilities. If the "
    "context cannot answer the question, say so and point the fan to a "
    "steward or the information desk — never invent gate numbers, times "
    "or facilities."
)


def load_matches() -> list[dict]:
    with MATCHES_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)["matches"]


def build_context(venue_id: str) -> tuple[str, list[str]]:
    """Assemble the grounding context pack for the LLM."""
    used: list[str] = []
    parts: list[str] = []

    venue = navigation.get_venue(venue_id)
    if venue:
        used.append("venue_map")
        facilities = "; ".join(
            f"{n['label']} [{n['type']}{', step-free' if n['step_free'] else ''}]"
            for n in venue["nodes"].values()
        )
        parts.append(f"VENUE: {venue['name']}, {venue['city']}. FACILITIES: {facilities}")

    snap = crowd.snapshot(venue_id)
    if snap:
        used.append("live_crowd")
        zones = "; ".join(f"{z['label']}: {z['level']} ({z['density_pct']}%)" for z in snap["zones"])
        parts.append(f"LIVE CROWD: {zones}. ADVISORY: {snap['advisory']}")

    todays = [m for m in load_matches() if m["venue_id"] == venue_id]
    if todays:
        used.append("fixtures")
        fx = "; ".join(f"{m['home']} vs {m['away']} ({m['stage']}) kickoff {m['kickoff_utc']}" for m in todays)
        parts.append(f"FIXTURES: {fx}")

    return "\n".join(parts), used


async def ask_genai(question: str, venue_id: str, language: str,
                    accessibility: bool, settings: Settings) -> Optional[dict]:
    """Query the Anthropic API. Returns None on any failure so the caller
    can fall back to the offline tier instead of erroring out."""
    context, used = build_context(venue_id)
    needs = "The fan HAS accessibility needs." if accessibility else ""
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.anthropic_model,
                    "max_tokens": 400,
                    "system": SYSTEM_PROMPT.format(lang=language),
                    "messages": [{
                        "role": "user",
                        "content": f"CONTEXT:\n{context}\n\n{needs}\n\nFAN QUESTION: {question}",
                    }],
                },
            )
        resp.raise_for_status()
        blocks = resp.json().get("content", [])
        text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
        if not text:
            return None
        return {"answer": text, "source": "genai", "context_used": used}
    except (httpx.HTTPError, ValueError, KeyError):
        return None


# --- Offline tier ---------------------------------------------------------

_ROUTE_RE = re.compile(r"\bfrom\b(.+?)\bto\b(.+)", re.IGNORECASE)


def _find_mentioned_nodes(venue: dict, question: str) -> list[str]:
    """Find venue locations mentioned anywhere in free text, in order of
    appearance. Handles casual phrasings like 'gate A to section 115 kese
    jaye?' where no 'from' keyword is present. Longer matches win, so
    'planta baja 8' resolves to Planta Baja 8, not Planta Baja 1."""
    text = " " + re.sub(r"[^\w\s]", " ", question).lower() + " "
    hits: list[tuple[int, int, str]] = []  # (pos, match_len, node_id)
    for node_id, node in venue["nodes"].items():
        label = re.sub(r"[^\w\s]", " ", node["label"]).lower().strip()
        label = re.sub(r"\s+", " ", label)
        words = label.split()
        candidates = [label]
        alias = node_id.replace("_", " ")
        if alias != label:
            candidates.append(alias)
        if len(words) >= 2:
            candidates.append(" ".join(words[:2]))
        candidates.sort(key=len, reverse=True)
        for cand in candidates:  # longest first
            pos = text.find(" " + cand + " ")
            if pos != -1:
                hits.append((pos, len(cand), node_id))
                break
    # Longest match at each position wins; drop matches nested inside another.
    hits.sort(key=lambda h: (h[0], -h[1]))
    ordered: list[str] = []
    covered_until = -1
    for pos, length, nid in hits:
        if pos < covered_until:
            continue
        if nid not in ordered:
            ordered.append(nid)
        covered_until = pos + length
    return ordered

_INTENTS = {
    "crowd": ("crowd", "busy", "queue", "line", "congest", "wait", "multitud", "fila"),
    "food": ("food", "eat", "drink", "hungry", "comida", "snack"),
    "restroom": ("restroom", "toilet", "bathroom", "wc", "baño", "sanitario"),
    "first_aid": ("first aid", "medic", "hurt", "injur", "doctor", "auxilio"),
    "transport": ("train", "bus", "shuttle", "transit", "metro", "transport", "leave", "exit"),
    "accessibility": ("wheelchair", "accessib", "step-free", "sensory", "disab", "silla"),
    "match": ("kickoff", "match", "game", "start", "fixture", "partido"),
}


def _match_node(venue: dict, text: str) -> Optional[str]:
    """Fuzzy-match free text like 'gate a' or 'section 115' to a node id."""
    text = re.sub(r"[^\w\s]", "", text).strip().lower()
    for node_id, node in venue["nodes"].items():
        label = node["label"].lower()
        if text in label or label in text or text.replace(" ", "_") == node_id:
            return node_id
    # loose token match, e.g. "gate a" vs "Gate A (North)"
    tokens = set(text.split())
    for node_id, node in venue["nodes"].items():
        if tokens and tokens.issubset(set(node["label"].lower().replace("(", "").replace(")", "").split())):
            return node_id
    return None


def _nearest_of_type(venue_id: str, start: str, node_type: str, step_free: bool) -> Optional[dict]:
    venue = navigation.get_venue(venue_id)
    best = None
    for node_id, node in venue["nodes"].items():
        if node["type"] != node_type:
            continue
        route = navigation.find_route(venue_id, start, node_id, step_free)
        if route and route["found"] and (best is None or route["estimated_minutes"] < best["estimated_minutes"]):
            best = route
    return best


def ask_offline(question: str, venue_id: str, language: str, accessibility: bool) -> dict:
    """Deterministic intent-routed answer built from the same services."""
    venue = navigation.get_venue(venue_id)
    q = question.lower()
    used: list[str] = ["venue_map"]

    if venue:
        # Routing intent: prefer explicit "from X to Y", otherwise any two
        # known locations mentioned in order ("gate A to section 115 kese jaye?").
        start = dest = None
        m = _ROUTE_RE.search(question)
        if m:
            start = _match_node(venue, m.group(1))
            dest = _match_node(venue, m.group(2))
        if not (start and dest):
            mentioned = _find_mentioned_nodes(venue, question)
            if len(mentioned) >= 2:
                start, dest = mentioned[0], mentioned[1]
        if start and dest:
            route = navigation.find_route(venue_id, start, dest, accessibility)
            answer = i18n.phrase("route_intro", language, navigation.describe_route(route))
            if accessibility and route and route.get("step_free"):
                answer += " " + i18n.phrase("accessibility_note", language)
            return {"answer": answer, "source": "offline_assistant", "context_used": used}

        default_start = next(
            (nid for nid, n in venue["nodes"].items() if n["type"] == "gate" and n["step_free"]),
            next(iter(venue["nodes"])),
        )
        for intent, keywords in _INTENTS.items():
            if not any(k in q for k in keywords):
                continue
            if intent == "crowd":
                snap = crowd.snapshot(venue_id)
                used.append("live_crowd")
                return {
                    "answer": i18n.phrase("crowd_intro", language, snap["advisory"]),
                    "source": "offline_assistant",
                    "context_used": used,
                }
            if intent == "match":
                used.append("fixtures")
                todays = [m for m in load_matches() if m["venue_id"] == venue_id]
                fx = "; ".join(f"{m['home']} vs {m['away']} — {m['stage']} — {m['kickoff_utc']} (gates open {m['gates_open_hours_before']}h before)" for m in todays)
                return {"answer": fx or i18n.phrase("fallback", language), "source": "offline_assistant", "context_used": used}
            type_map = {
                "food": "food", "restroom": "restroom", "first_aid": "first_aid",
                "transport": "transport", "accessibility": "accessibility",
            }
            node_type = type_map.get(intent)
            if node_type:
                route = _nearest_of_type(venue_id, default_start, node_type, accessibility)
                if route:
                    answer = i18n.phrase("route_intro", language, navigation.describe_route(route))
                    if accessibility:
                        answer += " " + i18n.phrase("accessibility_note", language)
                    return {"answer": answer, "source": "offline_assistant", "context_used": used}

    return {
        "answer": i18n.phrase("fallback", language),
        "source": "offline_assistant",
        "context_used": used,
    }


async def ask(question: str, venue_id: str, language: str,
              accessibility: bool, settings: Settings) -> dict:
    """Main entry point: GenAI first, offline tier as guaranteed fallback."""
    if settings.llm_enabled:
        result = await ask_genai(question, venue_id, language, accessibility, settings)
        if result:
            return result
    return ask_offline(question, venue_id, language, accessibility)
