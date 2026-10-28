"""tests/test_aa_kill_policy.py — R38 Task 6: the anti-air (chopper)
kill rule.

Evidence base:
  - R38 trial (scripts/r38t2_trials.py, trialA1/A2 deterministic from
    the rebuilt r38_ckpt): the SHIPPED policy killed the armored truck
    (hp_a4 240 -> 150 fire chips, grenade -100 -> 50, wreck 0xA44C;
    the pure-RIGHT control held a4=300 frozen) yet the D7 pin never
    released - the pending-entity queue kept slot 4 = the CHOPPER
    (st 0xAA94/0xABDC, hp_a4 300, h 207-210) alive at every pin
    observation.
  - Session-3 chopper_kill.py arm J1 (GAMEPLAY_VERIFIED 3/3): hop
    (B x3) -> neutral x8 -> UP+A lob AT APEX x8, connect band |dx|
    7-29, 3 connects = dead, +1100 score.
  - clamp_clear's UP-bullet alternation cannot connect at h~210
    (session-2 negative); armor_hold correctly refuses airborne rows.

The rule: in the pin context (clamp/section_pinned/d7_zone), a live
chopper with NO soldier-family present engages mode aa_kill with the
J1 pattern; fallers/corpses never trigger it; AA_MAX_MISS no-progress
cycles bail to clamp_clear for AA_BAIL_COOLDOWN frames; a hp_a4 drop
counts as a connect and resets the miss streak; a vanished chopper
resolves quietly (no fire during the possible queue release).
"""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from ps1play.agent.combat import (  # noqa: E402
    CombatPolicy, find_chopper, AA_CYCLE, AA_MAX_MISS, AA_BAIL_COOLDOWN,
    CHOPPER_ST,
)


def chopper_entry(slot=4, dx=-28.0, a4=300, h=210, st=0xAA94):
    px = 1164.0
    return {"slot": slot, "x_px": round(px + dx, 1), "dx_px": dx,
            "hp": 96, "sx": 96, "h": h, "st": st, "hp_a4": a4,
            "kind": "projectile_air" if h > 64 else "enemy"}


def soldier_entry(slot=12, dx=-90.0):
    px = 1164.0
    return {"slot": slot, "x_px": round(px + dx, 1), "dx_px": dx,
            "hp": 190, "sx": 190, "h": 64, "st": 0x4054, "hp_a4": 0,
            "kind": "enemy"}


def faller_entry(slot=11, dx=-15.0):
    px = 1164.0
    return {"slot": slot, "x_px": round(px + dx, 1), "dx_px": dx,
            "hp": 88, "sx": 88, "h": 164, "st": 0xB4E4, "hp_a4": 30,
            "kind": "projectile_air"}


def pinned_policy(px=1164.0):
    pol = CombatPolicy()
    pol.observe(px, 0.0, False)          # latches the D7 zone (px>=1150)
    pol.observe_section({"state": 10, "flags": 67}, px_now=px)
    pol.observe_section({"state": 10, "flags": 67}, px_now=px)
    assert pol.section_pinned or pol.d7_zone
    return pol


def frames_of(segs):
    """Expand segments into a per-frame btns list."""
    out = []
    for s in segs:
        out.extend([frozenset(s["btns"] or set())] * s["frames"])
    return out


def test_find_chopper_identity():
    live = find_chopper([chopper_entry()])
    assert live is not None and live["st"] in CHOPPER_ST
    assert find_chopper([faller_entry()]) is None          # bomb
    assert find_chopper([chopper_entry(a4=0)]) is None     # wreck
    assert find_chopper([chopper_entry(h=64)]) is None     # grounded row
    assert find_chopper([]) is None


def test_aa_mode_engages_in_pin_context():
    pol = pinned_policy()
    segs = pol.decide(45, 1164.0, [chopper_entry()], grenades=10,
                      hp=100)
    assert pol.mode == "aa_kill"
    fr = frames_of(segs)
    # J1 verbatim: B within the first 3 frames, UP+A around apex (f11+)
    assert any("B" in b for b in fr[:4])
    assert any({"UP", "A"} <= b for b in fr[8:20])
    assert all("Y" not in b for b in fr)   # bullets are not the recipe


def test_aa_never_fires_outside_the_pin_context():
    pol = CombatPolicy()
    segs = pol.decide(45, 900.0, [chopper_entry(dx=-20.0)], grenades=10,
                      hp=100)
    assert pol.mode != "aa_kill"
    assert "aa_connect" not in pol.stats


def test_soldiers_outrank_the_chopper():
    pol = pinned_policy()
    pol.decide(45, 1164.0, [chopper_entry(), soldier_entry()],
               grenades=10, hp=100)
    assert pol.mode != "aa_kill"          # queue discipline preserved


def test_faller_alone_never_triggers_aa():
    pol = pinned_policy()
    pol.decide(45, 1164.0, [faller_entry()], grenades=10, hp=100)
    assert pol.mode != "aa_kill"


def test_connect_counts_and_resets_miss_streak():
    pol = pinned_policy()
    a4 = [300, 300, 200, 200, 100, 100]
    k = 0
    # 5 cycles: two connects (a4 drops), interleaved
    for _ in range(5 * AA_CYCLE // 15 + 4):
        e = chopper_entry(a4=a4[min(k // (AA_CYCLE // 15), len(a4) - 1)])
        pol.decide(15, 1164.0, [e], grenades=10, hp=100)
        k += 1
    assert pol.stats.get("aa_connect", 0) >= 1
    assert pol.aa_miss < AA_MAX_MISS
    assert pol.stats.get("aa_bail", 0) == 0


def test_throw_is_ungated_and_cooldown_hops():
    """The J1 pattern throws whenever grenades remain (the |dx|<=40
    gate was tried and falsified live - see the constant-block note);
    and the cooldown phase KEEPS THE RAIN HOP (the pin window's faller
    bombs are a one-shot death through full HP - the first aa build
    dropped clamp_clear's hop protection and died php 291->0)."""
    pol = pinned_policy()
    pol.fc = 160
    segs = pol.decide(45, 1164.0, [chopper_entry(dx=-80.0)],
                      grenades=10, hp=100)
    assert pol.mode == "aa_kill"
    fr = frames_of(segs)
    assert any("A" in b for b in fr[8:20])       # throw not gated
    # cooldown frames (t>=19 within the 45f chunk): hop cadence present
    cooldown = fr[19:45]
    assert any("B" in b for b in cooldown)


def test_bail_after_sustained_miss_is_bounded():
    pol = pinned_policy()
    # drive AA_MAX_MISS full cycles with a frozen hp_a4
    for _ in range(AA_MAX_MISS * (AA_CYCLE // 15) + 2):
        pol.decide(15, 1164.0, [chopper_entry()], grenades=10, hp=100)
    assert pol.stats.get("aa_bail", 0) >= 1
    assert pol.mode != "aa_kill"          # clamped back to clamp_clear
    assert pol.aa_bail_until > 0
    # after the cooldown the campaign may re-engage (bounded, not dead)
    pol.fc += AA_BAIL_COOLDOWN + 1
    pol.decide(15, 1164.0, [chopper_entry()], grenades=10, hp=100)
    assert pol.mode == "aa_kill"


def test_chopper_gone_resolves_without_firing():
    pol = pinned_policy()
    segs = pol.decide(15, 1164.0, [chopper_entry()], grenades=10,
                      hp=100)
    assert pol.mode == "aa_kill"
    # next chunk: the chopper is dead/absent -> quiet, resolved
    segs = pol.decide(15, 1164.0, [], grenades=10, hp=100)
    assert pol.stats.get("aa_resolved", 0) >= 1
    assert all(not (b & {"Y", "A"}) for b in
               frames_of(segs))           # no fire into the release
