"""API tests via FastAPI TestClient.

These run entirely offline: no ANTHROPIC_API_KEY is set in the test
environment, so /api/ask exercises the rule-based tier — which is also
proof the app degrades gracefully without GenAI connectivity.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import _request_log, app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _request_log.clear()
    with TestClient(app) as c:
        yield c


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["genai_enabled"] is False


def test_index_serves_ui_with_security_headers(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "MatchDay Copilot" in res.text
    assert res.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in res.headers


def test_venues_and_matches(client):
    venues = client.get("/api/venues").json()["venues"]
    assert {v["id"] for v in venues} >= {"metlife", "azteca"}
    matches = client.get("/api/matches").json()["matches"]
    assert any(m["venue_id"] == "metlife" for m in matches)


def test_crowd_endpoint(client):
    res = client.get("/api/crowd/metlife")
    assert res.status_code == 200
    assert res.json()["zones"]
    assert client.get("/api/crowd/nowhere").status_code == 404


def test_navigate_endpoint_and_validation(client):
    ok = client.post("/api/navigate", json={
        "venue_id": "metlife", "start": "gate_a", "destination": "sec_115",
    })
    assert ok.status_code == 200
    assert ok.json()["found"] is True

    # Unknown fields rejected (extra=forbid)
    bad = client.post("/api/navigate", json={
        "venue_id": "metlife", "start": "gate_a", "destination": "sec_115",
        "evil": "payload",
    })
    assert bad.status_code == 422

    # Malicious/invalid IDs rejected by pattern validation
    inj = client.post("/api/navigate", json={
        "venue_id": "metlife", "start": "gate_a", "destination": "../etc/passwd",
    })
    assert inj.status_code == 422


def test_ask_routes_a_to_b(client):
    res = client.post("/api/ask", json={
        "question": "How do I get from Gate A to Section 115?",
        "venue_id": "metlife",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "offline_assistant"
    # Must be an actual computed route (arrow-joined path + ETA), not the fallback help text.
    assert "→" in body["answer"] and "min" in body["answer"]
    assert "Gate A" in body["answer"] and "Section 115" in body["answer"]


def test_ask_routes_casual_phrasing_without_from_keyword(client):
    # Real fan phrasing (Hinglish): no "from", trailing words after destination.
    res = client.post("/api/ask", json={
        "question": "gate A to section 115 kese jaye?",
        "venue_id": "metlife",
        "language": "hi",
    })
    assert res.status_code == 200
    body = res.json()
    assert "→" in body["answer"] and "Gate A" in body["answer"] and "Section 115" in body["answer"]


def test_ask_crowd_intent(client):
    res = client.post("/api/ask", json={
        "question": "Which gate is least busy right now?",
        "venue_id": "metlife",
    })
    assert res.status_code == 200
    assert "live_crowd" in res.json()["context_used"]


def test_ask_multilingual_spanish(client):
    res = client.post("/api/ask", json={
        "question": "donde esta la comida",
        "venue_id": "metlife",
        "language": "es",
    })
    assert res.status_code == 200
    assert "ruta" in res.json()["answer"].lower()


def test_ask_accessibility_gets_step_free_route(client):
    res = client.post("/api/ask", json={
        "question": "How do I get from Gate A to East Restrooms?",
        "venue_id": "metlife",
        "accessibility_needs": True,
    })
    assert res.status_code == 200
    assert "step-free" in res.json()["answer"]


def test_ask_question_length_capped(client):
    res = client.post("/api/ask", json={"question": "x" * 501, "venue_id": "metlife"})
    assert res.status_code == 422


def test_rate_limit(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    payload = {"question": "hello", "venue_id": "metlife"}
    codes = [client.post("/api/ask", json=payload).status_code for _ in range(5)]
    assert 429 in codes
