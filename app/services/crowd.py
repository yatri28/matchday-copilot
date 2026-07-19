"""Crowd intelligence.

In production this module would subscribe to turnstile counts, CCTV
analytics or Wi-Fi telemetry. For the challenge it produces a
*deterministic simulation*: density per zone is derived from a hash of
(venue, zone, current 5-minute window), so values look live, change over
time, and are fully reproducible in tests by passing a fixed ``now``.
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional

from .navigation import get_venue

LEVELS = [(45, "low"), (75, "moderate"), (101, "high")]


def _density(venue_id: str, zone_id: str, window: int) -> int:
    seed = f"{venue_id}:{zone_id}:{window}".encode()
    digest = hashlib.sha256(seed).digest()
    return digest[0] * 100 // 255  # 0..100


def _level(pct: int) -> str:
    for ceiling, name in LEVELS:
        if pct < ceiling:
            return name
    return "high"


def snapshot(venue_id: str, now: Optional[datetime] = None) -> Optional[dict]:
    """Current crowd densities for every gate/concourse/food zone."""
    venue = get_venue(venue_id)
    if venue is None:
        return None
    now = now or datetime.now(timezone.utc)
    window = int(now.timestamp() // 300)  # rotates every 5 minutes

    zones = []
    gates = []
    for node_id, node in venue["nodes"].items():
        if node["type"] not in {"gate", "concourse", "food", "transport"}:
            continue
        pct = _density(venue_id, node_id, window)
        zones.append(
            {
                "zone_id": node_id,
                "label": node["label"],
                "density_pct": pct,
                "level": _level(pct),
            }
        )
        if node["type"] == "gate":
            gates.append((pct, node_id, node["label"]))

    least_gate = min(gates)[2] if gates else None
    high_zones = [z["label"] for z in zones if z["level"] == "high"]
    if high_zones:
        advisory = (
            "Heavy congestion at: " + ", ".join(high_zones) + ". "
            f"Fastest entry right now: {least_gate}." if least_gate else ""
        )
    else:
        advisory = "Crowd levels are comfortable across the venue."

    return {
        "venue_id": venue_id,
        "generated_at_utc": now.isoformat(),
        "zones": zones,
        "least_crowded_gate": least_gate,
        "advisory": advisory,
    }
