"""In-stadium wayfinding.

Each venue is a small weighted graph (gates, concourses, sections,
facilities). Routes are computed with Dijkstra's algorithm; when a fan
requests a step-free route, nodes flagged ``step_free: false`` are
excluded so wheelchair users are never sent through stairs-only areas.
"""

import heapq
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "stadiums.json"


@lru_cache(maxsize=1)
def load_venues() -> dict[str, dict]:
    """Load and index venue data once per process."""
    with DATA_PATH.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    return {v["id"]: v for v in raw["venues"]}


def get_venue(venue_id: str) -> Optional[dict]:
    return load_venues().get(venue_id)


def _adjacency(venue: dict, step_free_only: bool) -> dict[str, list[tuple[str, int]]]:
    nodes = venue["nodes"]
    adj: dict[str, list[tuple[str, int]]] = {n: [] for n in nodes}
    for a, b, w in venue["edges"]:
        if step_free_only and (not nodes[a]["step_free"] or not nodes[b]["step_free"]):
            continue
        adj[a].append((b, w))
        adj[b].append((a, w))
    return adj


def find_route(
    venue_id: str, start: str, destination: str, step_free_only: bool = False
) -> Optional[dict]:
    """Return the shortest route between two points in a venue.

    Returns ``None`` when the venue or either endpoint is unknown, and a
    ``found: False`` payload when no path satisfies the constraints.
    """
    venue = get_venue(venue_id)
    if venue is None:
        return None
    nodes = venue["nodes"]
    if start not in nodes or destination not in nodes:
        return None

    adj = _adjacency(venue, step_free_only)
    dist: dict[str, int] = {start: 0}
    prev: dict[str, str] = {}
    heap: list[tuple[int, str]] = [(0, start)]
    visited: set[str] = set()

    while heap:
        d, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        if node == destination:
            break
        for nxt, w in adj[node]:
            nd = d + w
            if nd < dist.get(nxt, float("inf")):
                dist[nxt] = nd
                prev[nxt] = node
                heapq.heappush(heap, (nd, nxt))

    if destination not in visited:
        return {"found": False, "step_free": step_free_only, "estimated_minutes": 0, "steps": []}

    path = [destination]
    while path[-1] != start:
        path.append(prev[path[-1]])
    path.reverse()

    steps = [
        {"node_id": n, "label": nodes[n]["label"], "type": nodes[n]["type"]}
        for n in path
    ]
    route_step_free = all(nodes[n]["step_free"] for n in path)
    return {
        "found": True,
        "step_free": route_step_free,
        "estimated_minutes": dist[destination],
        "steps": steps,
    }


def describe_route(route: dict) -> str:
    """Human-readable one-line summary of a computed route."""
    if not route or not route.get("found"):
        return "No route found for those constraints."
    labels = " → ".join(s["label"] for s in route["steps"])
    suffix = " (step-free)" if route["step_free"] else ""
    return f"{labels} — about {route['estimated_minutes']} min{suffix}."
