"""Navigation service tests: shortest paths, step-free constraints, edge cases."""

from app.services import navigation


def test_route_found_between_gate_and_section():
    route = navigation.find_route("metlife", "gate_a", "sec_115")
    assert route["found"] is True
    assert route["steps"][0]["node_id"] == "gate_a"
    assert route["steps"][-1]["node_id"] == "sec_115"
    assert route["estimated_minutes"] > 0


def test_route_is_shortest():
    # gate_a -> concourse_n (2) -> sec_101 (1) = 3 minutes
    route = navigation.find_route("metlife", "gate_a", "sec_101")
    assert route["estimated_minutes"] == 3
    assert [s["node_id"] for s in route["steps"]] == ["gate_a", "concourse_n", "sec_101"]


def test_step_free_route_avoids_stairs_only_nodes():
    # sec_130 is not step-free, so a step-free route to it must not exist.
    route = navigation.find_route("metlife", "gate_a", "sec_130", step_free_only=True)
    assert route["found"] is False

    # Without the constraint the route exists but is flagged not step-free.
    route = navigation.find_route("metlife", "gate_a", "sec_130", step_free_only=False)
    assert route["found"] is True
    assert route["step_free"] is False


def test_step_free_route_flagged_when_all_nodes_accessible():
    route = navigation.find_route("metlife", "gate_a", "wc_e", step_free_only=True)
    assert route["found"] is True
    assert route["step_free"] is True


def test_unknown_venue_or_node_returns_none():
    assert navigation.find_route("nowhere", "a", "b") is None
    assert navigation.find_route("metlife", "gate_a", "does_not_exist") is None


def test_describe_route_summary():
    route = navigation.find_route("metlife", "gate_a", "sec_101")
    text = navigation.describe_route(route)
    assert "Gate A" in text and "Section 101" in text and "min" in text
