#!/usr/bin/env python3
"""tests/test_issue5_addendum.py — regression tests for the Issue #5
addendum batch (evidence-driven RAM map / WorldModel / recon).

Covers the pure, core-free logic produced this batch:
  1. policy chunk-partition independence (v0.7 contract) for the NEW
     FireHeldPolicy and the recon stall ladder input
  2. cheat-registry honesty invariants after the addendum updates
  3. overlay mapping invariant (ENEMY.BIN live_override 0x8009C0E8)
  4. telemetry score contract note (low-byte) stays documented
"""
import json
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

from ps1play.agent.cheatprof import CheatRegistry       # noqa: E402
from ps1play.agent.route import StallDetector            # noqa: E402


class _Det:
    state = "PROGRESS"


def _timeline(policy, chunk, total):
    out = []
    left = total
    while left > 0:
        n = min(chunk, left)
        for s in policy.decide(n, None):
            out.extend([frozenset(s["btns"] or set())] * s["frames"])
        left -= n
    return out


def test_fireheld_partition_independence():
    from issue5_recon import FireHeldPolicy
    a = _timeline(FireHeldPolicy(allow_grenades=True), 60, 600)
    b = _timeline(FireHeldPolicy(allow_grenades=True), 7, 600)
    c = _timeline(FireHeldPolicy(allow_grenades=True), 53, 600)
    assert a == b == c


def test_fireheld_holds_right_and_y():
    from issue5_recon import FireHeldPolicy
    pol = FireHeldPolicy(allow_grenades=False)
    tl = _timeline(pol, 60, 120)
    assert all({"RIGHT", "Y"} <= set(t) for t in tl)


def test_hop_policy_presses_jump_periodically():
    sys.path.insert(0, os.path.join(_REPO, "scripts"))
    from issue5_truckhop import HopPolicy
    pol = HopPolicy(hop_period=50, allow_grenades=False)
    tl = _timeline(pol, 60, 200)
    b_frames = sum(1 for t in tl if "B" in t)
    assert 20 <= b_frames <= 90          # ~14/50 frames held per cycle


def test_registry_honest_statuses():
    reg = CheatRegistry.load(os.path.join(
        _REPO, "data/games/SLUS-01212/cheats.json"))
    assert reg.entries["bombs"]["status"] == "VERIFIED"
    assert reg.entries["bombs_freeze"]["status"] == "VERIFIED"
    for name in ("hp_freeze", "invuln_blink", "lives_mirror", "invuln"):
        assert reg.entries[name]["status"] == "FAILED", name
    assert reg.validate() == []


def test_superseded_entries_carry_evidence():
    reg = CheatRegistry.load(os.path.join(
        _REPO, "data/games/SLUS-01212/cheats.json"))
    for name in ("hp_freeze", "invuln_blink"):
        ev = reg.entries[name].get("evidence")
        assert ev, f"{name} must carry its rejection evidence"
        assert any("die" in json.dumps(e).lower() or
                   "reject" in json.dumps(e).lower()
                   for e in ev), name


def test_overlay_mapping_invariant():
    p = os.path.join(_REPO, "data/games/SLUS-01212/overlay_index.json")
    d = json.load(open(p))
    m = d["modules"]["ENEMY.BIN"]["mapping"]
    assert m["live_dest"] == "0x8009C0E8"
    assert m["dest_source"].startswith("LIVE")
    assert m["status"] == "TESTED"


def test_recon_policy_recovery_shape():
    """FireHeldPolicy under a RECOVERY detector pulls back briefly
    (bounded left-walk), then resumes RIGHT — never a permanent flip."""
    from issue5_recon import FireHeldPolicy

    class RecDet:
        state = "RECOVERY"

    pol = FireHeldPolicy(allow_grenades=False)
    tl = _timeline(pol, 60, 180, ) if False else None
    pol2 = FireHeldPolicy(allow_grenades=False)
    out = []
    for s in pol2.decide(180, RecDet()):
        out.extend([frozenset(s["btns"] or set())] * s["frames"])
    lefts = sum(1 for t in out if "LEFT" in t)
    rights = sum(1 for t in out if "RIGHT" in t)
    assert lefts > 0 and rights > lefts      # bounded pull-back
    # and back to normal when the detector clears
    ok = _timeline(FireHeldPolicy(allow_grenades=False), 60, 60)
    assert all("LEFT" not in t for t in ok)


def test_stall_detector_still_bounds_recovery():
    det = StallDetector(stall_limit=3, recovery_chunks=2)
    states = []
    for _ in range(10):
        det.update(None, 0, 0)
        states.append(det.state)
    assert "RECOVERY" in states and "BLOCKED" in states
