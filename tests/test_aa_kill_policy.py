"""tests/test_aa_kill_policy.py — R38 Task 6 + R39 Task 7: the
anti-air (chopper) kill rule.

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
  - R39 Boot-1 (scratch/r39/r39_boot1_report.json): BASE reproduced
    R38 exactly (1/10 connects); a matched anchor A/B showed the
    15f-chunked in-policy delivery at 0/8 vs the ATOMIC Session-3
    delivery at 2/12; throws at cycle-start |dx| > 30 NEVER
    connected (0/5+ across arms); the frame capture showed the
    grenade releasing on the FIRST UP+A frame and the blind fc%90
    rain-hop leaving the player airborne at cycle start.

The R39 rule: in the pin context (clamp/section_pinned/d7_zone), a
live chopper with NO soldier-family present engages mode aa_kill with
the J1 pattern delivered ATOMICALLY (plan + aim locked at cycle
start), only inside the verified connect band (|dx| <= AA_THROW_DX),
with a bounded positioning walk beyond AA_WAIT_DX, a grounded-start
guard (B-free window + the rain-hop phase-locked inside the cooldown),
and the committed release window finished atomically once the grenade
is out. Fallers/corpses never trigger it; AA_MAX_MISS no-progress
thrown cycles bail to clamp_clear for AA_BAIL_COOLDOWN frames; a
hp_a4 drop counts as a connect and resets the miss streak; a vanished
chopper resolves quietly (no fire during the possible queue release)
and counts the kill-connect when the last observed hp_a4 was <= 100.
"""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from ps1play.agent.combat import (  # noqa: E402
    CombatPolicy, find_chopper, AA_CYCLE, AA_MAX_MISS, AA_BAIL_COOLDOWN,
    AA_THROW_DX, AA_ANCHOR_PX, AA_WALK_FRAMES, AA_COMMIT_T,
    AA_RELEASE_T, CHOPPER_ST,
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


def test_band_gate_and_anchor_positioning():
    """R39 v2.2: throws fire inside the verified connect band
    (|dx| <= AA_THROW_DX; boot-1: connects at 13.7-29, 0/5+ beyond
    30); outside the band the policy HOLDS AT THE ANCHOR (px >=
    AA_ANCHOR_PX - the chopper hovers at 1132-1155 near the clamp)
    or walks back to the anchor from below it. Boot-3's
    walk-toward-the-chopper dragged the player into the wave zone and
    was reverted; the boot-3 hard-gate-on-a-starved-grid variant
    fired 0 throws and was replaced by the S3 cadence."""
    pol = pinned_policy()
    pol.decide(15, 1164.0, [chopper_entry(dx=-80.0)], grenades=10,
               hp=100)
    assert pol.mode == "aa_kill"
    assert pol.aa_plan == "hold"          # anchored, out of band
    pol2 = pinned_policy()
    segs2 = pol2.decide(15, 1100.0, [chopper_entry(dx=-80.0)],
                        grenades=10, hp=100)
    assert pol2.aa_plan == "walk_r"       # walk back to the anchor
    fr2 = frames_of(segs2)
    assert any("RIGHT" in b for b in fr2[:AA_WALK_FRAMES])
    assert not any("A" in b for b in fr2)  # no grenade off-band
    pol3 = pinned_policy()
    pol3.decide(15, 1164.0, [chopper_entry(dx=-28.0)], grenades=10,
                hp=100)
    assert pol3.aa_plan == "throw"        # in-band: the S3 recipe
    # band floor: EVERY verified connect sat at |dx| >= 13.7 while the
    # close hovers at |dx| 3-8.6 missed 4/4 (the UP-lob arcs over a
    # too-close target)
    pol4 = pinned_policy()
    pol4.decide(15, 1164.0, [chopper_entry(dx=-5.0)], grenades=10,
                hp=100)
    assert pol4.aa_plan == "hold"         # too close: wait the patrol out


def test_throw_cycles_repeat_on_the_s3_cadence():
    """The boot-3 grounded-start guard is REMOVED (its interaction
    with the hold plan's own rain-hop self-blocked every re-lock: 12
    chunks of perfect dx -8.7..-27 geometry, zero throws). The S3
    recipe throws on its proven cadence with no guard - occasional
    airborne cycle starts are the accepted cost."""
    pol = pinned_policy()
    plans = []
    for _ in range(6):
        pol.decide(15, 1164.0, [chopper_entry(dx=-28.0)], grenades=10,
                   hp=100)
        plans.append(pol.aa_plan)
    assert plans[0] == "throw"
    assert plans.count("throw") >= 4      # ~76f cadence over 90f
    fr = frames_of(pol.decide(15, 1164.0, [chopper_entry(dx=-28.0)],
                              grenades=10, hp=100))
    # the drifted phase still emits lob frames every cycle
    assert any({"UP", "A"} <= b for b in fr)


def test_cooldown_rain_hop_survives():
    """The R38-proven cooldown rain-hop (fc%90 < JUMP_HOLD for
    t >= 19) stays active through the throw cycle - the R38 gated
    run died php 291->0 waiting a cycle without it."""
    pol = pinned_policy()
    pol.fc = 80                           # fc 99..103 during t 19..23
    segs = pol.decide(AA_CYCLE, 1164.0, [chopper_entry(dx=-28.0)],
                      grenades=10, hp=100)
    fr = frames_of(segs)
    assert len(fr) >= AA_CYCLE
    assert any("B" in fr[t] for t in range(19, AA_CYCLE))
    # the throw window itself stays hop-free after the J1 hop
    assert not any("B" in fr[t] for t in range(3, 19))


def test_locked_aim_survives_sign_flip_mid_cycle():
    """R39 atomic delivery: the lob aim is LOCKED at cycle start; a
    chopper crossing overhead between chunks must not flip the aim
    mid-lob (the chunked-delivery failure mode: per-chunk aim
    recompute split the proven recipe)."""
    pol = pinned_policy()
    pol.decide(15, 1164.0, [chopper_entry(dx=-20.0)], grenades=10,
               hp=100)
    assert pol.aa_aim == "LEFT"
    segs2 = pol.decide(15, 1164.0, [chopper_entry(dx=+20.0)],
                       grenades=10, hp=100)
    fr2 = frames_of(segs2)
    lob2 = [b for b in fr2 if {"UP", "A"} <= b]
    assert lob2 and all("LEFT" in b for b in lob2)


def test_committed_release_window_survives_a_soldier():
    """Once the grenade is out (t < AA_COMMIT_T of a locked throw)
    the J1 window finishes atomically even if a soldier appears;
    the queue discipline applies again at the next cycle start."""
    pol = pinned_policy()
    pol.decide(15, 1164.0, [chopper_entry(dx=-28.0)], grenades=10,
               hp=100)
    assert pol._aa_threw
    segs = pol.decide(15, 1164.0, [chopper_entry(dx=-28.0),
                                   soldier_entry()], grenades=10,
                      hp=100)
    fr = frames_of(segs)
    assert any({"UP", "A"} <= b for b in fr[:4])   # lob tail continued
    pol.decide(15, 1164.0, [chopper_entry(dx=-28.0), soldier_entry()],
               grenades=10, hp=100)
    assert pol.mode != "aa_kill"          # soldier outranks again


def test_dodge_suppressed_only_before_release():
    """A verified falling shell must not interrupt the pre-release
    hop+press frames (t <= AA_RELEASE_T of a locked throw); dodges
    resume once the grenade is out."""
    pol = pinned_policy()
    faller = faller_entry(dx=-10.0)
    pol.prev_h = {11: faller["h"] + 20}   # prime: verified falling
    segs = pol.decide(15, 1164.0, [chopper_entry(dx=-28.0), faller],
                      grenades=10, hp=100)
    assert pol.mode == "aa_kill"
    fr = frames_of(segs)
    pre = fr[:AA_RELEASE_T + 1]
    assert all("RIGHT" not in b for b in pre)      # no dodge frames
    # post-release the dodge may fire (the grenade is out)
    assert len(fr) == 15


def test_chopper_gone_after_throw_counts_kill_connect():
    """A thrown grenade's -100 step completing the kill (last
    observed hp_a4 <= 100, then the chopper is gone) counts as a
    verified connect, not a silent resolution."""
    pol = pinned_policy()
    for _ in range(2):
        pol.decide(15, 1164.0, [chopper_entry(a4=100, dx=-28.0)],
                   grenades=10, hp=100)
    assert pol._aa_threw                  # the grenade is out
    pol.decide(15, 1164.0, [], grenades=10, hp=100)
    assert pol.stats.get("aa_connect", 0) >= 1
    assert pol.stats.get("aa_kill_connect", 0) >= 1
    assert pol.stats.get("aa_resolved", 0) >= 1
    assert pol.aa_slot is None


def test_bail_after_sustained_miss_is_bounded():
    pol = pinned_policy()
    # drive AA_MAX_MISS full cycles with a frozen hp_a4; a 96f cycle
    # needs ceil(AA_CYCLE/15) chunks per cycle
    for _ in range(AA_MAX_MISS * (AA_CYCLE // 15 + 1) + 2):
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
