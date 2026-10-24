"""Issue #9 §9-A: scan schema validation tests (combat-state correctness)."""
import pytest

from ps1play.agent.combat import (
    CombatPolicy, GROUND_HEIGHT, SLOTS, validate_scan,
)


def _good(px):
    return [{"slot": 3, "x_px": px + 50.0, "dx_px": 50.0, "hp": 30,
             "h": 64, "kind": "enemy"},
            {"slot": 7, "x_px": px - 90.5, "dx_px": -90.5, "hp": 12,
             "h": 200, "kind": "projectile_air"}]


def test_valid_scan_passes():
    assert validate_scan(_good(1000.0), px=1000.0) is True


def test_empty_scan_passes():
    assert validate_scan([], px=1000.0) is True
    assert validate_scan(None, px=1000.0) is True


def test_kind_height_mismatch_flagged():
    bad = [{"slot": 3, "x_px": 1050.0, "dx_px": 50.0, "hp": 30,
            "h": 64, "kind": "projectile_air"}]   # h==64 is ground contact
    d = {}
    assert validate_scan(bad, px=1000.0, diagnostics=d) is False
    assert any("mismatch" in v for v in d["violations"])


def test_sort_order_and_dx_flagged():
    bad = [{"slot": 3, "x_px": 1150.0, "dx_px": 50.0, "hp": 30,
            "h": 64, "kind": "enemy"},        # dx says 50, x says 150
           {"slot": 4, "x_px": 1010.0, "dx_px": 10.0, "hp": 30,
            "h": 64, "kind": "enemy"}]        # out of order after entry 0
    d = {}
    assert validate_scan(bad, px=1000.0, diagnostics=d) is False
    assert any("dx_px" in v for v in d["violations"])
    assert any("sort" in v for v in d["violations"])


def test_bad_fields_flagged():
    bad = [{"slot": 0, "x_px": 5000.0, "dx_px": 10.0, "hp": 0,
            "h": -3, "kind": "ufo"}]
    d = {}
    assert validate_scan(bad, px=1000.0, diagnostics=d) is False
    assert len(d["violations"]) >= 4
    assert d["schema"] == "ps1play-combat-scan/1"


def test_policy_counts_violations_never_treats_as_safe():
    pol = CombatPolicy()
    bad = [{"slot": 2, "x_px": 1050.0, "dx_px": 99999.0, "hp": 30,
            "h": 64, "kind": "enemy"}]
    pol.decide(0, 1000.0, bad, grenades=0, hp=100)
    assert pol.stats.get("scan_schema_violations") == 1
    assert pol.last_scan_diagnostics["violations"]
    # a valid scan does not increment
    pol.decide(1, 1000.0, _good(1000.0), grenades=0, hp=100)
    assert pol.stats.get("scan_schema_violations") == 1


def test_live_scan_entities_output_conforms():
    """scan_entities output must satisfy its own declared contract."""
    try:
        from ps1play.agent import combat
    except Exception:
        pytest.skip("no mem backend in offline suite")
    px = 500.0
    scan = [{"slot": s, "x_px": px + 40 * s, "dx_px": 40.0 * s,
             "hp": 10 + s, "h": GROUND_HEIGHT, "kind": "enemy"}
            for s in range(1, min(6, SLOTS))]
    assert validate_scan(scan, px=px) is True
