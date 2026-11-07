"""tests/test_r66_msx_adapter.py — R66 Metal Slug X adapter + policy
(offline; no emulator, no boot).

Covers:
  * the R66 corridor predicate: the bullet-transparent state NEVER
    blocks a shot and is never targeted; any other mortal DOES block;
  * policy determinism (same observation stream -> byte-identical
    action sequence) and the bounded stall ladder;
  * the fire cooldown and the grenade budget;
  * the adapter's action mapping (legal pad buttons only) and the
    state-code classification;
  * scan_mortals over a mocked entity table (read-only contract);
  * the registry/disc pins for metal_slug_x;
  * package isolation: the MSX package imports no other game's
    modules (the absolute knowledge-isolation law).
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from ps1play.adapters.metal_slug_x.adapter import (  # noqa: E402
    CORPSE_ST, OBS_LEN, ST_AE7C, ST_SOFT, ST_TRANSPARENT, ST_WOUND,
    MetalSlugXAdapter, state_code,
)
from ps1play.adapters.metal_slug_x.policy import (  # noqa: E402
    FIRE_COOLDOWN, Mission1Policy,
)
from ps1play.runtime.errors import AdapterError  # noqa: E402
from ps1play.runtime.interfaces import (  # noqa: E402
    ActionDecision, Frame, GameObservation,
)
from ps1play.runtime.session import (  # noqa: E402
    EXPECTED_ISO_SHA, GAME_DEFAULT_ISO,
)
from ps1play.runtime.registry import (  # noqa: E402
    progress_label_for, registered_games,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mk_frame(seq=1):
    return Frame(seq=seq, emulator_frame_count=seq, rgb=None,
                 timestamp=0.0, stale=False)


def obs_from(px=1000.0, score=0, php=144, gren=10, alive=True,
             ents=()):
    """ents: iterable of (dx, state_code)."""
    x = np.zeros(OBS_LEN, dtype=np.float32)
    x[0] = px
    x[1] = float(score)
    x[2] = float(php)
    x[3] = float(gren)
    x[4] = 1.0 if alive else 0.0
    x[5] = 1.0
    for i, (dx, sc) in enumerate(ents[:5]):
        x[6 + 3 * i] = dx
        x[7 + 3 * i] = float(sc)
    return GameObservation(values=x, frame_seq=1,
                           frame_id="t", timestamp=0.0, valid=True,
                           diagnostics={})


class TestStateCodes:
    def test_state_code_map(self):
        assert state_code(ST_SOFT) == 1
        assert state_code(ST_WOUND) == 2
        assert state_code(0x3F48) == 3
        assert state_code(0x2B74) == 3
        assert state_code(ST_TRANSPARENT) == 4
        assert state_code(ST_AE7C) == 5
        assert state_code(0x1234) == 6
        assert state_code(0x9E88) == 7      # THE TRUCK (R67 probe)
        assert 0x5B0C in CORPSE_ST


class TestCorridorPredicate:
    """THE R66 fix: only absorbing/registering mortals block."""

    def _run(self, ents, n=40):
        pol = Mission1Policy()
        pol.reset()
        acts = []
        o = obs_from(ents=ents)
        for _ in range(n):
            d = pol.predict(o)
            acts.append(d.action)
        return acts

    def test_transparent_does_not_block(self):
        # a transparent wasp (code 4) between player and a soft
        # target (code 1): the R66 predicate still engages.
        acts = self._run([(60.0, 4), (150.0, 1)])
        assert "FIRE" in acts

    def test_nearest_mortal_engaged(self):
        # the nearest front mortal IS the target: firing at it is
        # correct even with another mortal behind it (the bullet is
        # absorbed by the nearest).
        acts = self._run([(60.0, 1), (150.0, 1)])
        assert "FIRE" in acts

    def test_transparent_never_targeted(self):
        # ONLY a transparent entity present -> no engagement fire.
        acts = self._run([(150.0, 4)])
        assert "FIRE" not in acts

    def test_transparent_then_mortal_fires_at_mortal(self):
        # transparent at 60 (code 4), mortal at 150: the R66
        # predicate engages the mortal THROUGH the transparent row
        # (the n=4 piercing evidence: the bullet passes through).
        acts = self._run([(60.0, 4), (150.0, 1)])
        assert "FIRE" in acts

    def test_ae7c_engaged_when_nearest(self):
        # 0xae7c is mortal (it absorbs bullets) -> it can be targeted
        acts = self._run([(60.0, 5)])
        assert "FIRE" in acts

    def test_far_target_not_engaged(self):
        acts = self._run([(400.0, 1)])
        assert "FIRE" not in acts


class TestPolicyMechanics:
    def test_deterministic(self):
        ents = [(60.0, 1), (150.0, 4)]

        def stream():
            pol = Mission1Policy()
            pol.reset()
            out = []
            o = obs_from(ents=ents)
            for k in range(200):
                d = pol.predict(o)
                out.append(d.action)
            return out

        assert stream() == stream()

    def test_fire_cooldown(self):
        pol = Mission1Policy()
        pol.reset()
        o = obs_from(ents=[(100.0, 1)])
        acts = [pol.predict(o).action for _ in range(40)]
        fires = [i for i, a in enumerate(acts) if a == "FIRE"]
        assert fires, "expected at least one FIRE"
        for a, b in zip(fires, fires[1:]):
            assert b - a >= FIRE_COOLDOWN

    def test_stall_ladder_grenade_bounded(self):
        pol = Mission1Policy()
        pol.reset()
        # a flat px stream with a mortal far ahead (out of engage
        # range) and grenades available
        o = obs_from(ents=[(400.0, 1)], gren=10)
        acts = [pol.predict(o).action for _ in range(600)]
        n_gren = sum(1 for a in acts if a == "GRENADE")
        assert n_gren <= 3, "grenade budget exceeded"

    def test_identity(self):
        ident = Mission1Policy().identity()
        assert ident["deterministic"] is True
        assert ident["trained"] is False
        assert ident["corridor_predicate"] == "r66_corrected"
        assert len(ident["policy_sha256"]) == 64


class TestAdapterContract:
    def _adapter(self, mortal_tbl=None):
        ad = MetalSlugXAdapter(env=None)
        return ad

    def test_action_mapping(self):
        ad = self._adapter()
        assert ad.action_to_buttons("IDLE") == frozenset()
        assert ad.action_to_buttons("WALK") == frozenset({"RIGHT"})
        assert ad.action_to_buttons("BACK") == frozenset({"LEFT"})
        assert ad.action_to_buttons("FIRE") == frozenset({"Y"})
        assert ad.action_to_buttons("HOP") == frozenset({"RIGHT", "B"})
        assert ad.action_to_buttons("GRENADE") == frozenset({"A"})
        with pytest.raises(AdapterError):
            ad.action_to_buttons("FLAP")
        assert set(ad.legal_actions()) == {
            "IDLE", "WALK", "BACK", "FIRE", "HOP", "GRENADE"}

    def test_obs_len_and_features(self):
        ad = self._adapter()
        assert len(ad.FEATURE_NAMES) == OBS_LEN == 21


class TestRegistryPins:
    def test_registered(self):
        assert "metal_slug_x" in registered_games()
        assert progress_label_for("metal_slug_x") == "score"

    def test_disc_pins(self):
        assert "metal_slug_x" in GAME_DEFAULT_ISO
        assert GAME_DEFAULT_ISO["metal_slug_x"].endswith(
            "Metal Slug X (USA).cue")
        assert EXPECTED_ISO_SHA["metal_slug_x"].startswith("45cde149")
        assert len(EXPECTED_ISO_SHA["metal_slug_x"]) == 64


class TestScanMortals:
    """scan_mortals over a mocked verified entity table."""

    def _adapter_with_table(self, px_word, slots):
        """slots: {slot: (st, x_word, h, sx)}"""
        TABLE = 0x0CA268
        STRIDE = 0x14C
        import struct

        class FakeMem:
            def __init__(self):
                self.ram = bytearray(0x200000)

            def u16(self, a):
                return int.from_bytes(self.ram[a:a + 2], "little")

            def u32(self, a):
                return int.from_bytes(self.ram[a:a + 4], "little")

            def u8(self, a):
                return self.ram[a]

        mem = FakeMem()
        mem.ram[0x0CA2E0:0x0CA2E4] = \
            struct.pack("<I", int(px_word))
        mem.ram[0x0EE518:0x0EE51C] = struct.pack("<I", 0xFF)
        for s, row in slots.items():
            st, xw, h = row[0], row[1], row[2]
            sx = row[3] if len(row) > 3 else 40
            base = TABLE + s * STRIDE
            mem.ram[base:base + 2] = struct.pack("<H", st)
            mem.ram[base + 0x78:base + 0x7C] = \
                struct.pack("<I", xw)
            mem.ram[base + 0x7E:base + 0x80] = struct.pack("<H", h)
            mem.ram[base + 0x8E:base + 0x90] = \
                struct.pack("<H", sx)

        FakeP = type("FakeP", (), {"mem": mem})
        FakeEnv = type("FakeEnv", (), {"p": FakeP()})
        return MetalSlugXAdapter(env=FakeEnv())

    def test_scan_sorts_and_filters(self):
        px_w = 1000 << 16
        slots = {
            3: (ST_SOFT, (1000 + 150) << 16, 10),
            5: (ST_TRANSPARENT, (1000 + 50) << 16, 300),   # airborne
            7: (0x5B0C, (1000 + 80) << 16, 10),            # corpse
            9: (ST_WOUND, 0, 10),                          # x=0 dead
            11: (ST_WOUND, (1000 - 60) << 16, 10),         # behind
            13: (ST_WOUND, (1000 + 40) << 16, 10),         # nearest
        }
        ad = self._adapter_with_table(px_w, slots)
        out = ad.scan_mortals(1000.0)
        dxs = [round(e["dx"], 1) for e in out]
        assert dxs[0] == pytest.approx(40.0)    # nearest front mortal
        assert dxs[1] == pytest.approx(-60.0)   # then the behind one
        assert all(e["st"] != 0x5B0C for e in out)
        # the AIRBORNE transparent row (h=300) is never packed
        assert all(e["h"] <= 64 for e in out)
        assert len(out) <= 5

    def test_alive_word(self):
        ad = self._adapter_with_table(1000 << 16, {})
        assert ad.alive() is True
        ad2 = self._adapter_with_table(0, {})
        assert ad2.alive() is False


class TestIsolation:
    """The absolute law: the MSX package shares NOTHING with the
    other games."""

    def test_no_cross_game_imports(self):
        pkg = os.path.join(REPO, "ps1play", "adapters",
                           "metal_slug_x")
        bad = ("buzzybee", "flappybird", "tetrade")
        hits = []
        for fn in os.listdir(pkg):
            if not fn.endswith(".py"):
                continue
            src = open(os.path.join(pkg, fn)).read()
            for b in bad:
                if f"adapters.{b}" in src or f"adapters import {b}" \
                        in src:
                    hits.append((fn, b))
        assert not hits, f"cross-game imports found: {hits}"

    def test_runtime_core_has_no_msx_knowledge(self):
        core = os.path.join(REPO, "ps1play", "runtime")
        for fn in os.listdir(core):
            if not fn.endswith(".py"):
                continue
            src = open(os.path.join(core, fn)).read()
            assert "0x0CA268" not in src, \
                f"MSX entity table leaked into runtime/{fn}"
            assert "0x0EE318" not in src, \
                f"MSX score anchor leaked into runtime/{fn}"
            # the registry/session carry ONLY ids + disc paths/pins
            if fn != "session.py":
                assert "metal_slug" not in src.lower() or fn == \
                    "registry.py", f"MSX semantics in runtime/{fn}"


class TestTruckRulesR67:
    """THE R67 truck encounter rules (policy v1.2.0), offline on
    synthetic observations (the truck is state code 7 = SC_TRUCK;
    the R67 probe correction — ground soldiers also present as
    (6, h=64), so code 6 is NEVER the truck).

    The world FEED is MOVING (px advances every decision) so the
    v1.0.0 stall ladder never fires — each GRENADE observed here is
    attributable to a named rule via diagnostics."""

    def _obs(self, ents=(), gren=10, px=1000.0):
        """ents: iterable of (dx, state_code, h); dx is kept
        RELATIVE (the obs is rebuilt each decision)."""
        x = np.zeros(OBS_LEN, dtype=np.float32)
        x[0] = px
        x[3] = float(gren)
        x[4] = 1.0
        x[5] = 1.0
        for i, (dx, sc, h) in enumerate(ents[:5]):
            x[6 + 3 * i] = dx
            x[7 + 3 * i] = float(sc)
            x[8 + 3 * i] = float(h)
        return GameObservation(values=x, frame_seq=1,
                               frame_id="t", timestamp=0.0,
                               valid=True, diagnostics={})

    def _run(self, ents, gren=10, n=300):
        """Returns (actions, rules).  px advances +2/decision (the
        stall sensor resets; the ladder stays out of the way)."""
        pol = Mission1Policy()
        pol.reset()
        acts, rules = [], []
        for k in range(n):
            o = self._obs(ents, gren=gren, px=1000.0 + 2 * k)
            d = pol.predict(o)
            acts.append(d.action)
            rules.append(d.diagnostics.get("rule"))
        return acts, rules

    def test_truck_in_band_grenades(self):
        # truck in the lob band -> exactly 3 GRENADEs (the budget),
        # all from the truck_grenade rule, cooldown-spaced
        acts, rules = self._run([(90.0, 7, 64.0)])
        assert acts.count("GRENADE") == 3
        assert rules.count("truck_grenade") == 3

    def test_soldier_before_truck_gun(self):
        # a CLEAR escort (70, between player and truck at 90) holds
        # the lob: bullets go to the escort (truck_escort_first)
        # while it lives; NO truck grenade fires.  (In the real run
        # the escort dies to ~2 bullets — the frozen 0x4054 recipe —
        # and the lob schedule then starts; the synthetic escort
        # never dies, so the hold is observable as zero lobs.)
        acts, rules = self._run([(90.0, 7, 64.0),
                                 (70.0, 1, 44.0)])
        assert rules.count("truck_escort_first") > 0
        assert rules.count("truck_grenade") == 0
        assert acts.count("GRENADE") == 0

    def test_escort_behind_truck_does_not_hold_lob(self):
        # soldier BEHIND the truck (150 vs 100): corridor-blocked
        # (the R49 bullet-steal model) — T3 never fires, the lob is
        # the correct weapon and the full budget lands (from the
        # outer band — the v1.4.2 hold geometry).
        acts, rules = self._run([(100.0, 7, 64.0),
                                 (150.0, 1, 44.0)], n=320)
        assert rules.count("truck_escort_first") == 0
        assert rules.count("truck_grenade") == 3
        assert acts.count("GRENADE") == 3

    def test_truck_out_of_band_no_grenade(self):
        # truck at 200 (out of the lob band): T6 approach (walk to
        # it — the hold/chip take over inside the band), NO grenade.
        acts, rules = self._run([(200.0, 7, 64.0)], n=60)
        assert "truck_grenade" not in rules
        assert "GRENADE" not in acts
        assert "truck_approach" in rules

    def test_sc6_never_truck(self):
        # THE R67 PROBE FIX (pinned): ground soldiers in walk/throw
        # states present (sc=6, h=64, a4=0) — the v1.1.0 (6, h=64)
        # identity froze the T5 hold on a false truck at px 493.
        # Code 6 at ANY height never arms the truck rules.
        acts, rules = self._run([(90.0, 6, 64.0)])
        assert "truck_grenade" not in rules
        assert "truck_escort_first" not in rules
        assert "truck_hold" not in rules
        assert "GRENADE" not in acts

    def test_no_grenades_left_no_lob(self):
        acts, rules = self._run([(90.0, 7, 64.0)], gren=0)
        assert "truck_grenade" not in rules
        assert "GRENADE" not in acts

    def test_truck_budget_separate_from_stall(self):
        # the truck grenades come out of the TRUCK budget; the stall
        # ladder budget stays untouched during the truck fight.
        pol = Mission1Policy()
        pol.reset()
        for k in range(300):
            o = self._obs([(90.0, 7, 64.0)],
                          px=1000.0 + 2 * k)
            pol.predict(o)
        assert pol._truck_grenades_used == 3
        assert pol._grenades_used == 0

    def test_identity_v142(self):
        pol = Mission1Policy()
        ident = pol.identity()
        assert ident["policy_version"] == "1.4.2"
        assert ident["truck_rules"] == "r67_grenade_sequencing"

    def test_hold_backs_off_point_blank(self):
        # THE v1.4.2 PROBE LESSON (pinned): the dx-52 hold stood in
        # the truck gun's line and lost the duel.  Below 90 the
        # player backs off (a FRONT truck: BACK walks away) — the
        # back-off owns the whole sub-90 regime (no lob, no chip,
        # no flip-flop).
        acts, rules = self._run([(52.3, 7, 64.0)], n=30)
        assert rules.count("truck_hold_back_off") == 30
        assert "WALK" not in acts
        assert "GRENADE" not in acts

    def test_blast_retreat_after_budget(self):
        # THE v1.4.0 PRODUCT-RUN LESSON (pinned): the 3-lobs kill
        # took the truck to 0 hp_a4 and the death explosion killed
        # the player standing in the band.  Once the budget is
        # spent the player WALKS AWAY from the truck.
        pol = Mission1Policy()
        pol.reset()
        x = np.zeros(OBS_LEN, dtype=np.float32)
        x[0] = 1000.0
        x[3] = 10.0
        x[4] = 1.0
        x[5] = 1.0
        x[6] = -90.0          # the rear truck in band
        x[7] = 7.0
        x[8] = 64.0
        o = GameObservation(values=x, frame_seq=1, frame_id="t",
                            timestamp=0.0, valid=True,
                            diagnostics={})
        pol._truck_grenades_used = 3      # the budget spent
        d = pol.predict(o)
        assert d.action == "WALK"         # away from a REAR truck
        assert d.diagnostics["rule"] == "truck_blast_retreat"

    def test_no_reapproach_after_budget(self):
        # the truck behind at -226 (out of the blast margin) with
        # the budget spent: NO truck_approach (never re-approach).
        pol = Mission1Policy()
        pol.reset()
        x = np.zeros(OBS_LEN, dtype=np.float32)
        x[0] = 1000.0
        x[3] = 10.0
        x[4] = 1.0
        x[5] = 1.0
        x[6] = -226.5
        x[7] = 7.0
        x[8] = 64.0
        o = GameObservation(values=x, frame_seq=1, frame_id="t",
                            timestamp=0.0, valid=True,
                            diagnostics={})
        pol._truck_grenades_used = 3
        d = pol.predict(o)
        assert d.diagnostics.get("rule") != "truck_approach"

    def test_fire_cadence_v100_rhythm(self):
        # THE WAVE-FIGHT RHYTHM PIN (the v1.2.0 lesson): the generic
        # engage fires every FIRE_COOLDOWN + 1 decisions (the v1.0.0
        # bottom-tick cadence — the deterministic wave trajectory
        # depends on it).
        pol = Mission1Policy()
        pol.reset()
        x = np.zeros(OBS_LEN, dtype=np.float32)
        x[0] = 1000.0
        x[3] = 10.0
        x[4] = 1.0
        x[5] = 1.0
        x[6] = 100.0
        x[7] = 1.0
        x[8] = 44.0
        o = GameObservation(values=x, frame_seq=1, frame_id="t",
                            timestamp=0.0, valid=True,
                            diagnostics={})
        fires = [k for k in range(60)
                 if pol.predict(o).action == "FIRE"]
        assert len(fires) >= 4
        for a, b in zip(fires, fires[1:]):
            assert b - a == FIRE_COOLDOWN + 1, (a, b)

    def test_deterministic_with_truck(self):
        ents = [(90.0, 7, 64.0), (150.0, 1, 44.0)]
        assert self._run(ents) == self._run(ents)


class TestTruckHoldR67T5:
    """T5 THE HOLD: at or inside the lob band the player never
    advances (no WALK / forward HOP); chip-fire during cooldowns.
    The truck is code 7 (the R67 probe identity fix)."""

    def _obs(self, ents=(), gren=10, px=1000.0):
        x = np.zeros(OBS_LEN, dtype=np.float32)
        x[0] = px
        x[3] = float(gren)
        x[4] = 1.0
        x[5] = 1.0
        for i, (dx, sc, h) in enumerate(ents[:5]):
            x[6 + 3 * i] = dx
            x[7 + 3 * i] = float(sc)
            x[8 + 3 * i] = float(h)
        return GameObservation(values=x, frame_seq=1,
                               frame_id="t", timestamp=0.0,
                               valid=True, diagnostics={})

    def _run(self, ents, gren=10, n=120, advance=False):
        pol = Mission1Policy()
        pol.reset()
        acts, rules = [], []
        for k in range(n):
            px = 1000.0 + 2 * k if advance else 1000.0
            o = self._obs(ents, gren=gren, px=px)
            d = pol.predict(o)
            acts.append(d.action)
            rules.append(d.diagnostics.get("rule"))
        return acts, rules

    def test_hold_no_walk_no_hop_in_band(self):
        # a STATIC world with the truck in band: zero WALK, zero HOP
        # — the hold (the synthetic world is static, so the stall
        # ladder WILL fire late; only the pre-stall window counts)
        acts, rules = self._run([(90.0, 7, 64.0)], n=100)
        assert "WALK" not in acts
        assert "HOP" not in acts
        assert "truck_hold" in rules or "truck_grenade" in rules

    def test_hold_point_blank(self):
        # truck at dx 20 (BELOW the lob band, the ep1 death shape):
        # pure hold — no advance, no fire (dx < 8 band excluded at
        # <=8 only; 20 > 8 so chip-fire is legal), never WALK.
        acts, rules = self._run([(20.0, 7, 64.0)], n=60)
        assert "WALK" not in acts
        assert "HOP" not in acts

    def test_chip_fire_in_band(self):
        # in band with grenades exhausted: standing chip-fire
        acts, rules = self._run([(90.0, 7, 64.0)], gren=0, n=40)
        assert "truck_chip_fire" in rules
        assert "WALK" not in acts


class TestRearFightR67V140:
    """v1.4.0 THE REAR FIGHT: the pinned-player evidence — the wave
    and the parked truck are BEHIND the player at the section pin;
    the policy turns (BACK = LEFT, a legal pad button) and engages."""

    def _obs(self, ents=(), gren=10, px=1000.0):
        x = np.zeros(OBS_LEN, dtype=np.float32)
        x[0] = px
        x[3] = float(gren)
        x[4] = 1.0
        x[5] = 1.0
        for i, (dx, sc, h) in enumerate(ents[:5]):
            x[6 + 3 * i] = dx
            x[7 + 3 * i] = float(sc)
            x[8 + 3 * i] = float(h)
        return GameObservation(values=x, frame_seq=1,
                               frame_id="t", timestamp=0.0,
                               valid=True, diagnostics={})

    def _run(self, ents, gren=10, n=40):
        pol = Mission1Policy()
        pol.reset()
        acts, rules = [], []
        for k in range(n):
            o = self._obs(ents, gren=gren)
            d = pol.predict(o)
            acts.append(d.action)
            rules.append(d.diagnostics.get("rule"))
        return acts, rules

    def test_rear_soldier_turn_and_fire(self):
        # a fresh soft soldier BEHIND (dx -50), nothing in front:
        # BACK (face_rear) then FIRE (rear_engage) on cooldown.
        acts, rules = self._run([(-50.0, 1, 64.0)])
        assert acts[0] == "BACK"
        assert rules[0] == "face_rear"
        assert "rear_engage" in rules
        assert rules.count("FIRE") >= 0
        assert "rear_engage" in rules and "FIRE" in acts

    def test_front_target_wins_over_rear(self):
        # front soldier at 60 AND rear at -50: the v1.0.0 front
        # engage fires (no turn) — the stream is preserved.
        acts, rules = self._run([(60.0, 1, 44.0), (-50.0, 1, 64.0)])
        assert acts[0] == "FIRE"
        assert rules[0] == "engage"
        assert "face_rear" not in rules

    def test_rear_truck_in_band_turn_and_lob(self):
        # the parked truck BEHIND at dx -90 (the pin evidence):
        # turn (truck_turn) then 3 lobs (truck_grenade); the hold
        # fills between lobs (its own cooldown ticks).
        acts, rules = self._run([(-90.0, 7, 64.0)], n=320)
        assert rules[0] == "truck_turn"
        assert acts[0] == "BACK"
        assert rules.count("truck_grenade") == 3
        assert acts.count("GRENADE") == 3
        assert "truck_chip_fire" in rules

    def test_rear_truck_out_of_band_approach(self):
        # the truck behind at -226.5 (the probe's exact posture —
        # outside the old 220 window, inside the 400 scan window):
        # truck_approach walks BACK toward it (facing left).
        acts, rules = self._run([(-226.5, 7, 64.0)], n=6)
        assert rules[0] == "truck_approach"
        assert acts[0] == "BACK"

    def test_rear_soldier_outranks_rear_truck(self):
        # the escort behind at -50 AND the truck behind at -90:
        # the escort dies first (the D7 recipe), the lob waits.
        acts, rules = self._run([(-90.0, 7, 64.0), (-50.0, 1, 44.0)])
        assert rules[0] == "truck_escort_turn"
        assert acts[0] == "BACK"
        assert rules.count("truck_grenade") == 0
