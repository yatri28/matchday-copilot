"""Crowd service tests: bounds, determinism, and advisory logic."""

from datetime import datetime, timezone

from app.services import crowd

FIXED_NOW = datetime(2026, 7, 19, 18, 0, tzinfo=timezone.utc)


def test_snapshot_zone_bounds_and_levels():
    snap = crowd.snapshot("metlife", now=FIXED_NOW)
    assert snap is not None
    assert snap["zones"], "expected at least one monitored zone"
    for zone in snap["zones"]:
        assert 0 <= zone["density_pct"] <= 100
        assert zone["level"] in {"low", "moderate", "high"}


def test_snapshot_is_deterministic_for_fixed_time():
    a = crowd.snapshot("metlife", now=FIXED_NOW)
    b = crowd.snapshot("metlife", now=FIXED_NOW)
    assert a["zones"] == b["zones"]
    assert a["least_crowded_gate"] == b["least_crowded_gate"]


def test_least_crowded_gate_is_actually_least_crowded():
    snap = crowd.snapshot("metlife", now=FIXED_NOW)
    gates = [z for z in snap["zones"] if z["zone_id"].startswith("gate_")]
    best = min(gates, key=lambda z: z["density_pct"])
    assert snap["least_crowded_gate"] == best["label"]


def test_unknown_venue_returns_none():
    assert crowd.snapshot("nowhere") is None
