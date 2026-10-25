"""D7 instrument-pin policy wiring tests (Issue #9, sectioncorr1 follow-up).

The section-walker pin signature (state 0xA, live-correlated in
sectioncorr1: 8/8 pin chunks px 1159.8..1164.0, never mid-section) is
wired into CombatPolicy as an INSTRUMENT-based clamp trigger. These
tests pin the contract:

  - 2 consecutive state-0xA readings engage the defensive clamp_clear
    mode WITHOUT the derived px-stagnation streak (the instrument
    reacts while clamp_streak is still 1).
  - single readings and 1-frame transients never fire the trigger.
  - (0xB, 0x43) SINGLE/transient readings are NOT a pin (the
    sectioncorr1 c12/c30 mid-section transients).
  - Session-3 CONTRACT UPDATE (Issue #5 D7 release campaign): a
    second live boot pins SUSTAINED at (0xB, 0x43) — px frozen 1164.0,
    3/3 identical releases once the section's pending entities are
    cleared (release_test.py rel1-3 + the MISSION 1 screen PNG).
    2+ consecutive (0xB, flags&0x40) readings now latch the pin.
  - (0xA, 0x1) / (0xA, 0x0) ARE pins (flags are corroboration only).
  - release needs 2 consecutive non-signature readings.
  - stale invalidation (px jump) keeps the pin but resets streaks.
  - knockback px wobble cannot defeat the instrument trigger (the
    derived streak kept resetting in sectioncorr1 c11-c20).
"""
import pytest

from ps1play.agent.combat import (
    SECTION_PIN_CONFIRM,
    SECTION_PIN_STATE,
    CombatPolicy,
)


def _sec(state, flags=0x43, progress=0xFFFF):
    return {"state": state, "flags": flags, "progress": progress,
            "schema": "ps1play-section-scan/1", "complete": False}


PIN = {"state": SECTION_PIN_STATE, "flags": 0x43}
FREE = {"state": 0xB, "flags": 0x1}


def test_two_pin_readings_engage_defensive_mode_before_derived_streak():
    pol = CombatPolicy()
    pol.observe_section(PIN)
    assert pol.section_pinned is False        # 1 reading: not yet
    pol.observe_section(PIN)
    assert pol.section_pinned is True
    # derived streak is only 1 (one stalled observe) — the instrument
    # alone must drive the defensive mode
    pol.observe(px=1164.0, advanced=0.0, intent_right=True)
    pol.decide(60, 1164.0, [], grenades=0, hp=291)
    assert pol.mode == "clamp_clear"
    assert pol.clamp_streak < 2
    assert pol.stats["section_pin"] == 1


def test_single_reading_and_transient_never_fire():
    pol = CombatPolicy()
    pol.observe_section(PIN)
    pol.observe_section({"state": 0x5, "flags": 0x1})   # walker-reset transient
    assert pol.section_pinned is False
    pol.observe(px=1100.0, advanced=30.0, intent_right=True)
    pol.decide(60, 1100.0, [], grenades=0, hp=291)
    assert pol.mode == "advance"


def test_state_0b_flags_43_transient_is_not_the_pin():
    # sectioncorr1 c12/c30: (0xB, 0x43) SINGLE mid-section transients
    # — one reading (or a non-sustained run) must never trigger.
    # Session-3: SUSTAINED (0xB,0x43) IS the boot-2 pin (see the
    # sustained test below); the confirm streak keeps transients out.
    pol = CombatPolicy()
    pol.observe_section({"state": 0xB, "flags": 0x43})
    pol.observe_section({"state": 0xB, "flags": 0x1})   # transient broken
    pol.observe_section({"state": 0xB, "flags": 0x43})
    pol.observe_section({"state": 0xB, "flags": 0x1})   # never 2 consecutive
    assert pol.section_pinned is False
    pol.observe(px=1052.0, advanced=0.0, intent_right=True)
    pol.decide(60, 1052.0, [], grenades=0, hp=179)
    assert pol.mode != "clamp_clear" or pol.clamp_streak >= 2


def test_state_0b_flags_43_sustained_is_the_boot2_pin():
    # Session-3 (Issue #5): boot 2 pins SUSTAINED at (0xB, 0x43) with
    # px frozen 1164.0; clearing the section entities released it 3/3
    # (release_test.py rel1/2/3) and reached the MISSION 1 screen.
    pol = CombatPolicy()
    for _ in range(2):
        pol.observe_section({"state": 0xB, "flags": 0x43})
    assert pol.section_pinned is True
    pol.observe(px=1164.0, advanced=0.0, intent_right=True)
    pol.decide(60, 1164.0, [], grenades=0, hp=291)
    assert pol.mode == "clamp_clear"
    assert pol.stats["section_pin"] == 1


def test_clamp_clear_aims_at_the_nearest_ground_foe_side():
    # Session-3 aiming fix: the hard-coded LEFT fired AWAY from the
    # respawn-side soldiers (px 992 respawn, foes 1064-1103 RIGHT).
    # The foe sits beyond ENGAGE_SHORT (200) but inside the scan
    # window — near is None, so the pinned clear itself must aim.
    pol = CombatPolicy()
    for _ in range(2):
        pol.observe_section({"state": 0xB, "flags": 0x43})
    pol.observe(px=992.0, advanced=0.0, intent_right=True)
    foes = [{"slot": 12, "st": 0x4054, "x_px": 1222.0,
             "dx_px": 230.0, "hp": 100, "sx": 100, "h": 64,
             "hp_a4": 0, "kind": "enemy"}]
    segs = pol.decide(60, 992.0, foes, grenades=0, hp=291)
    assert pol.mode == "clamp_clear"
    fired_right = any("RIGHT" in (s.get("btns") or set()) and
                      "Y" in (s.get("btns") or set())
                      for s in segs)
    assert fired_right
    walked_left = any("LEFT" in (s.get("btns") or set())
                      for s in segs)
    assert not walked_left          # hold the line, fire RIGHT


def test_clamp_clear_default_left_facing_preserved():
    # no ground foes -> the historical LEFT/UP-LEFT rain behaviour.
    # session-4: px kept below the D7 zone (1150) — at the D7 pin the
    # policy now goes SILENT on an empty scan (d7_quiet_hold, its own
    # test in test_session4_release.py); this test pins the GENERIC
    # section-pin clear behaviour.
    pol = CombatPolicy()
    for _ in range(2):
        pol.observe_section({"state": 0xA, "flags": 0x43})
    pol.observe(px=1000.0, advanced=0.0, intent_right=True)
    segs = pol.decide(60, 1000.0, [], grenades=0, hp=291)
    assert pol.mode == "clamp_clear"
    assert any("LEFT" in (s.get("btns") or set()) for s in segs)
    assert not any("RIGHT" in (s.get("btns") or set())
                   for s in segs)


@pytest.mark.parametrize("flags", [0x43, 0x1, 0x0])
def test_state_0a_is_the_discriminator_regardless_of_flags(flags):
    # pin chunks came with flags 0x43/0x1/0x0 (c25-33); requiring the
    # 0x40 bit would falsely release at (0xA, 0x0) like c33
    pol = CombatPolicy()
    pol.observe_section({"state": 0xA, "flags": flags})
    pol.observe_section({"state": 0xA, "flags": flags})
    assert pol.section_pinned is True


def test_release_after_two_free_readings():
    pol = CombatPolicy()
    pol.observe_section(PIN)
    pol.observe_section(PIN)
    assert pol.section_pinned is True
    pol.observe_section(FREE)
    assert pol.section_pinned is True          # 1 free reading: hold
    pol.observe_section(FREE)
    assert pol.section_pinned is False
    assert pol.stats["section_pin_release"] == 1
    assert pol.stats["section_pin"] == 1


def test_release_counter_reengages():
    pol = CombatPolicy()
    for s in (PIN, PIN, FREE, FREE, PIN, PIN):
        pol.observe_section(s)
    assert pol.stats["section_pin"] == 2
    assert pol.stats["section_pin_release"] == 1
    assert pol.section_pinned is True


def test_stale_invalidation_keeps_pin_resets_streaks():
    pol = CombatPolicy()
    pol.observe_section(PIN)
    pol.observe_section(PIN)
    assert pol.section_pinned is True
    # respawn-grade px jump (RESPAWN_JUMP_PX = 300)
    pol.last_observe_px = 1164.0
    pol.observe(px=800.0, advanced=0.0, intent_right=False)
    assert pol.section_pinned is True          # game-state evidence kept
    assert pol.sec_pin_streak == 0             # streaks must re-confirm
    assert pol.sec_free_streak == 0
    # and the defensive stance is STILL active at the respawn point
    pol.decide(60, 800.0, [], grenades=0, hp=100)
    assert pol.mode == "clamp_clear"


def test_px_wobble_cannot_defeat_the_instrument_trigger():
    # sectioncorr1 c11-c20: knockback wobble (px 1052->962->1057->953)
    # kept resetting the derived streak; the instrument must hold the
    # defensive mode through it
    pol = CombatPolicy()
    pol.observe_section(PIN)
    pol.observe_section(PIN)
    pxs = [1164.0, 1050.0, 1164.0, 962.0, 1057.0, 953.0, 1046.0, 984.0]
    for px in pxs:
        pol.observe(px=px, advanced=0.0, intent_right=True)
        pol.decide(60, px, [], grenades=0, hp=150)
        assert pol.mode == "clamp_clear", f"mode lost at px {px}"


def test_observe_section_none_is_a_noop():
    pol = CombatPolicy()
    pol.observe_section(None)
    pol.observe_section({})
    assert pol.section_pinned is False
    assert pol.stats["section_pin"] == 0


def test_two_consecutive_non_signature_readings_release():
    # any 2 consecutive non-signature readings release the pin (a real
    # free reading + a walker-reset transient are 2 non-signature
    # readings); a false release self-heals: the derived px-stall
    # streak rebuilds within 2 chunks and re-clamps
    pol = CombatPolicy()
    pol.observe_section(PIN)
    pol.observe_section(PIN)
    pol.observe_section(FREE)
    pol.observe_section({"state": 0x5, "flags": 0x1})
    assert pol.section_pinned is False
    assert pol.stats["section_pin_release"] == 1


def test_isolated_transient_inside_the_pin_does_not_release():
    # the LIVE c28 pattern from sectioncorr1: (0xA,0x43) x3, ONE
    # transient chunk (0x5,0x1) with a knockback px jump, then back to
    # (0xA,0x43) — the pin held; a single non-signature reading must
    # not release
    pol = CombatPolicy()
    for s in (PIN, PIN, PIN, {"state": 0x5, "flags": 0x1}, PIN):
        pol.observe_section(s)
    assert pol.section_pinned is True
    assert pol.stats["section_pin_release"] == 0
