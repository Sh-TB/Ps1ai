"""Issue #9 §8/§9-E/F: armor_hold behaviour tests (clamp-death fix).

Discriminator background (CLAMP-ROOT, live evidence this session):
holding px 950-998 = 0 deaths in 5400 frames; pressing to the pin zone
died 4/4 to the one-shot -291 truck ram. The policy must NEVER walk
toward an armored foe (hp >= 200): it stops, faces, and fires, escalating
to grenades when hp is unchanged."""
from ps1play.agent.combat import CombatPolicy, ARMOR_GRENADE_X


def _truck(px, dx, hp=300, hp_a4=300):
    """Corrected-semantics fixture: `hp` = the +0x8E SCREEN-X (legacy
    key, kept for compat), `hp_a4` = the REAL HP u16@+0xA4 (the field
    the armored class must key since the 73c172d correction)."""
    return {"slot": 14, "x_px": px + dx, "dx_px": dx, "hp": hp,
            "hp_a4": hp_a4, "h": 64, "kind": "enemy"}


def test_armored_foe_triggers_stop_not_walk():
    pol = CombatPolicy()
    pol.observe(950.0, 0.0, False)
    segs = pol.decide(60, 950.0, [_truck(950.0, 180.0)], grenades=2, hp=200)
    assert pol.mode == "armor_hold"
    assert pol.stats["armor_hold"] == 1
    joined = set()
    for s in segs:
        joined |= s["btns"]
    assert "Y" in joined
    # at most the 2-frame face-assert taps RIGHT; after that, standing
    # fire only — no sustained walking into the truck
    right_frames = sum(s["frames"] for s in segs if "RIGHT" in s["btns"])
    assert right_frames <= 2


def test_rear_armored_keeps_rear_check_not_armor_hold():
    """Corrected semantics (regression-taught): a REAR armored pursuer
    stays on the verified rear_check/grenade campaign; armor_hold is
    ahead-only so it can never hijack the mid-run rear defence."""
    pol = CombatPolicy()
    pol.observe(950.0, 0.0, False)
    pol.decide(60, 950.0, [_truck(950.0, -100.0)], grenades=2, hp=200)
    assert pol.mode != "armor_hold"          # never hijacks the rear path
    assert pol.stats["armor_hold"] == 0
    # persisting pursuer (REAR_CHECK_PERSIST chunks, NO clamp) ->
    # rear_check fires (clamp_clear only owns the clamped state)
    modes = []
    for _ in range(6):
        pol.observe(950.0, 0.0, False)
        segs = pol.decide(60, 950.0, [_truck(950.0, -100.0)],
                          grenades=2, hp=200)
        modes.append(pol.mode)
    assert "rear_check" in modes
    assert pol.rear_checks >= 1
    assert "armor_hold" not in modes


def test_armor_hold_escalates_to_grenade_on_no_progress():
    pol = CombatPolicy()
    px = 950.0
    # 3+ checks with unchanged hp at grenade range -> grenade cadence;
    # GRENADE_PERIOD windows land every 150f, so run 8 chunks (480f)
    grenade_chunks = []
    for i in range(8):
        pol.observe(px, 0.0, False)
        segs = pol.decide(60, px, [_truck(px, 80.0, hp=254)],
                          grenades=3, hp=200)
        if any("A" in s["btns"] for s in segs):
            grenade_chunks.append(i)
    assert pol.armor_no_progress is True
    assert pol.armor_checks >= 4
    assert pol.stats.get("armor_grenade", 0) >= 1
    assert grenade_chunks


def test_armor_release_when_softened():
    pol = CombatPolicy()
    px = 950.0
    pol.observe(px, 0.0, False)
    pol.decide(60, px, [_truck(px, 100.0, hp_a4=210)], grenades=0,
               hp=200)
    assert pol.mode == "armor_hold"
    # truck softened below ARMOR_HP_MIN on the REAL HP field -> normal
    # selection resumes
    pol.observe(px, 0.0, False)
    pol.decide(60, px, [_truck(px, 100.0, hp_a4=180)], grenades=0,
               hp=200)
    assert pol.mode != "armor_hold"


def test_screenx_soldier_no_longer_mislocks_as_armor():
    """Regression (this session's reach2 live probe): the +0x8E field
    is the SCREEN-X — a right-side soldier at screen-x 250 with NO
    real HP (hp_a4 == 0) must NOT trigger armor_hold (the historical
    mislock stalled the run 58 chunks at ~900 until the faller bombs
    killed the agent)."""
    pol = CombatPolicy()
    px = 900.0
    pol.observe(px, 0.0, False)
    pol.decide(60, px, [_truck(px, 150.0, hp=250, hp_a4=0)],
               grenades=0, hp=200)
    assert pol.mode != "armor_hold"
    assert pol.stats["armor_hold"] == 0


def test_airborne_chopper_never_gets_armor_hold():
    """Regression (this session's chopper campaign): the chopper
    (hp_a4 300, h 206-228) is AIRBORNE — bullets cannot reach it, so
    the stand-and-fire armor_hold treatment would just hold the agent
    in the bomb rain. Only GROUND contact (h == 64) classifies."""
    pol = CombatPolicy()
    px = 950.0
    pol.observe(px, 0.0, False)
    chop = {"slot": 19, "x_px": px + 120.0, "dx_px": 120.0,
            "hp": 150, "hp_a4": 300, "h": 212,
            "kind": "projectile_air"}
    pol.decide(60, px, [chop], grenades=2, hp=200)
    assert pol.mode != "armor_hold"
    assert pol.stats["armor_hold"] == 0


def test_route_damaged_truck_still_classifies():
    """The truck's route-state HP is 230 (live, reach5 anchor) — above
    ARMOR_HP_MIN on the REAL field even after route attrition."""
    pol = CombatPolicy()
    px = 950.0
    pol.observe(px, 0.0, False)
    pol.decide(60, px, [_truck(px, 150.0, hp=90, hp_a4=230)],
               grenades=2, hp=200)
    assert pol.mode == "armor_hold"


def test_armored_threat_outranks_closer_soft_foe():
    pol = CombatPolicy()
    px = 950.0
    pol.observe(px, 0.0, False)
    segs = pol.decide(60, px, [_truck(px, 200.0, hp=254),
                               {"slot": 5, "x_px": px + 60, "dx_px": 60.0,
                                "hp": 30, "h": 64, "kind": "enemy"}],
                      grenades=0, hp=200)
    assert pol.mode == "armor_hold"


def test_clamped_rear_keeps_precedence_over_armor_hold():
    """At the end-clamp, the defensive clamp_clear must still own the
    state — armor_hold never overrides the clamped branch."""
    pol = CombatPolicy()
    px = 950.0
    for _ in range(4):
        pol.observe(px, 0.0, True)      # no progress while advancing
        pol.decide(60, px, [], grenades=2, hp=200)
    assert pol.clamp_streak >= 2
    pol.observe(px, 0.0, True)
    pol.decide(60, px, [_truck(px, -150.0)], grenades=2, hp=200)
    assert pol.mode == "clamp_clear"


def test_stale_reset_clears_armor_campaign():
    pol = CombatPolicy()
    px = 950.0
    pol.observe(px, 0.0, False)
    pol.decide(60, px, [_truck(px, 150.0)], grenades=2, hp=200)
    assert pol.armor_slot == 14
    pol._invalidate_stale()
    assert pol.armor_slot is None
    assert pol.armor_checks == 0
