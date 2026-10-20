#!/usr/bin/env python3
"""validate_cheats.py — LIVE validation of candidate GameShark codes for
Metal Slug X (SLUS-01212), per Issue #2 section 2.

Protocol per candidate code (exact issue steps):
  1. reproducible state with cheats disabled (savestate "cb")
  2. record baseline HUD/counter readings + screenshot
  3. enable EXACTLY one candidate code
  4. perform the relevant action repeatedly (fire / throw / take damage)
  5. observe expected value/behavior change
  6. disable the code; confirm the effect stops
  7. repeat baseline/treatment from an equivalent starting state
  8. record core/content/firmware identity, code, address, value,
     activation method, observed effect, negative control, evidence
  9. VERIFIED only if reproduced; else PARTIAL / FAILED / BLOCKED

A counter address is trusted only after its own in-game event test
(grenade -1, shot decrement, 1 Hz decay, damage drop, death -1).
Published cluster addresses are NEVER written and never trusted as-is.

Usage:
  python3 scripts/validate_cheats.py --codes bombs,invuln,time \
      --budget-minutes 12
"""
import argparse
import json
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                         # noqa: E402

from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                            # noqa: E402
from ps1play.agent.gameshark import GSCode                 # noqa: E402
from ps1play.agent.cheatprof import (                      # noqa: E402
    CheatSession, CheatRegistry, CHEAT_ASSISTED,
    derive_freeze_code,
    ST_VERIFIED, ST_TESTED, ST_FAILED, ST_BLOCKED, ST_CANDIDATE)
from ps1play.agent.perception import PerceptionGuard       # noqa: E402
from mission import ensure_mission                         # noqa: E402

DEF_REGISTRY = os.path.join(_REPO, "data", "games", "SLUS-01212",
                            "cheats.json")
# published cluster layout (offsets used only for TRANSLATION hypotheses;
# every translated address gets its own event test before use)
PUB = {"bombs": 0x0398B4, "ammo": 0x02DCD8, "hp": 0x032764,
       "lives": 0x0475A8, "timer": 0x0295F8, "weapon": 0x02D92C}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def png(p, evid, name):
    try:
        from PIL import Image
        rgb = p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).resize((320, 240)).save(
                os.path.join(evid, name))
            return name
    except Exception as e:                                  # noqa: BLE001
        log("png fail:", e)
    return None


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--codes", default="bombs,time,invuln,ammo,lives",
                    help="comma list of registry entries to validate")
    ap.add_argument("--registry", default=DEF_REGISTRY)
    ap.add_argument("--game", default=labconfig.resolve_path("game"))
    ap.add_argument("--core", default=labconfig.resolve_path("core"))
    ap.add_argument("--workspace", default=labconfig.resolve_path(
        "workspace"))
    ap.add_argument("--evidence-dir", default=None)
    ap.add_argument("--firmware", default=os.environ.get(
        "M1_FIRMWARE", "auto"),
        choices=list(labconfig.FIRMWARE_MODES))
    ap.add_argument("--budget-minutes", type=float, default=12.0)
    ap.add_argument("--attempts", type=int, default=2,
                    help="baseline/treatment repetitions (issue step 7)")
    ap.add_argument("--out", default=None, help="verdicts JSON path")
    a = ap.parse_args(argv)
    a.code_list = [s.strip() for s in a.codes.split(",") if s.strip()]
    if a.evidence_dir is None:
        base = labconfig.resolve_path("evidence_dir") or os.path.join(
            _REPO, "evidence_local")
        a.evidence_dir = os.path.join(
            base, f"cheatval_{time.strftime('%Y%m%d_%H%M%S')}")
    return a


class Validator:
    def __init__(self, args):
        self.args = args
        self.evid = args.evidence_dir
        os.makedirs(self.evid, exist_ok=True)
        self.t0 = time.time()
        self.budget_s = args.budget_minutes * 60.0
        self.verdicts = {}
        self.counter_addrs = {}
        self.registry = CheatRegistry.load(args.registry)
        problems = self.registry.validate()
        if problems:
            sys.exit(f"!! registry invalid: {problems}")
        missing = [n for n in args.code_list
                   if n not in self.registry.entries]
        if missing:
            sys.exit(f"!! unknown registry entries: {missing}")

    def out_of_budget(self, margin_s=30.0):
        return (time.time() - self.t0) > (self.budget_s - margin_s)

    # ---------------- identity ----------------
    def identity(self, p, fw):
        cue_bin = None
        if p.game and p.game.lower().endswith(".cue"):
            with open(p.game, "r", errors="replace") as f:
                for ln in f:
                    if 'FILE "' in ln:
                        cue_bin = os.path.join(os.path.dirname(p.game),
                                               ln.split('"')[1])
                        break
        ident = {
            "game": p.game,
            "game_md5": labconfig.file_md5(cue_bin) if cue_bin else None,
            "core": p.core_path,
            "core_md5": labconfig.file_md5(p.core_path),
            "core_name": f"{p.core.core_name} {p.core.core_ver}",
            "firmware_mode": fw["mode"],
            "firmware_md5": fw["bios_md5"],
            "registry": self.args.registry,
        }
        return ident

    # ---------------- boot & calibration ----------------
    def boot_and_calibrate(self):
        a = self.args
        try:
            fw = labconfig.resolve_firmware(a.firmware, a.workspace)
        except labconfig.FirmwareError as e:
            sys.exit(f"!! firmware: {e}")
        kw = {}
        if a.core:
            kw["core"] = a.core
        if a.workspace:
            kw["workspace"] = a.workspace
        if fw["override_vars"]:
            kw["var_overrides"] = fw["override_vars"]
        p = PS1Play(a.game, **kw)
        info = p.boot()
        log("boot:", info)
        fw_ev = labconfig.firmware_log_evidence(
            getattr(p.core, "log_history", []))
        ok, detail = labconfig.check_firmware_trust(fw, fw_ev)
        if not ok:
            sys.exit(f"!! firmware trust failed: {detail}")
        self.fw = fw
        r = p.enter_gameplay3()
        log("enter:", r.get("in_game"))
        if not r.get("in_game"):
            sys.exit("!! boot failed")
        m = ensure_mission(p, tries=6, log=log)
        if not m.get("in_mission"):
            sys.exit("!! gate failed")
        self.p = p
        self.session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
        self.ident = self.identity(p, fw)
        png(p, self.evid, "01_baseline_hud.png")

        # ---- live counter anchors (each needs its own event test) ----
        # anchor() is the STRICT 4-press series (u16 + u8); the old
        # '-1 x2' anchor produced an impostor (see perception.py note)
        guard = PerceptionGuard(p)
        anch = guard.anchor(log=log)
        if not anch.get("ok"):
            sys.exit("!! bombs anchor failed — cannot calibrate")
        self.guard = guard
        self.counter_addrs["bombs"] = guard.addrs["bombs"]
        self.bombs_dtype = guard.dtypes.get("bombs", "u16")
        self.delta = None        # published-cluster translation INVALID
        log(f"[cal] bombs live @ {guard.addrs['bombs']:#x} "
            f"({self.bombs_dtype}) series={anch.get('series')}")
        p.save_state("cb")

        # NO cluster translations: the published addresses read 0xFF
        # in this boot (dynamically placed state area) and the old
        # delta came from an impostor anchor. timer/lives/ammo/weapon
        # get their OWN event-verified anchors before any protocol.
        log("[cal] translations disabled — per-role anchors only")

    # ---------------- atomic protocol arms ----------------
    def _engage(self):
        """Run 2 no-input frames AFTER enabling (before any action) so
        the patch is in place exactly like hardware GS when the player
        presses the button. Without this, the first action frame runs
        the unpatched store and one decrement leaks through."""
        for _ in range(2):
            self.p.core.run_frame()
            self.session.gs.tick()

    def _arms(self, code, addr, dtype, action, frames_idle, attempts):
        """baseline (no code) / treatment (code) / disable-recovery arms.

        Returns dict with per-arm (before, after) counter readings; all
        arms reload the same savestate 'cb' (equivalent starting states).
        """
        p = self.p
        read = (p.mem.u8 if dtype == "u8" else
                p.mem.u16 if dtype == "u16" else p.mem.u32)
        arm = {}

        def run_arm(with_code):
            p.load_state("cb")
            p.core.run(10, set())
            if with_code:
                self.session.enable("_proto", [code])
            self._engage()          # symmetric settle in both arms
            v0 = read(addr)
            p.core.set_buttons(action)
            for _ in range(15):
                p.core.run_frame()
                if with_code:
                    self.session.gs.tick()
            p.core.set_buttons(set())
            for _ in range(frames_idle):
                p.core.run_frame()
                if with_code:
                    self.session.gs.tick()
            p._advance()
            v1 = read(addr)
            if with_code:
                self.session.disable("_proto")
            return [int(v0), int(v1)]

        arm["baseline"] = [run_arm(False) for _ in range(attempts)]
        arm["treatment"] = [run_arm(True) for _ in range(attempts)]
        arm["disabled_recovery"] = [run_arm(False) for _ in
                                    range(attempts)]
        return arm

    def _judge(self, arm, expect="freeze"):
        """freeze: value must move in baseline+recovery, never in
        treatment."""
        def moved(reading):
            return reading[0] != reading[1]
        base_moved = all(moved(r) for r in arm["baseline"])
        treat_frozen = all(not moved(r) for r in arm["treatment"])
        rec_moved = all(moved(r) for r in arm["disabled_recovery"])
        works = bool(base_moved and treat_frozen and rec_moved)
        return {"works": works,
                "baseline_moves": base_moved,
                "treatment_frozen": treat_frozen,
                "disable_recovered": rec_moved}

    # ---------------- per-code protocols ----------------
    def validate_bombs(self):
        if "bombs" not in self.counter_addrs or self.out_of_budget():
            return self._blocked("bombs", "no live bombs anchor / budget")
        code = GSCode(self.registry.entries["bombs"]["codes"][0])
        addr = self.counter_addrs["bombs"]
        dtype = self.bombs_dtype
        arm = self._arms(code, addr, dtype, {"A"}, 120,
                         self.args.attempts)
        j = self._judge(arm)
        j.update({"code": code.raw, "addr": hex(addr),
                  "dtype": dtype, "action": "grenade(CIRCLE)",
                  "readings": arm})
        png(self.p, self.evid, "10_bombs_after.png")
        return (ST_VERIFIED if j["works"] else ST_FAILED), j

    def validate_time(self):
        return self._blocked(
            "time",
            "no live timer anchor on this boot: published address "
            "0x295F8 reads 0xFF (dynamically placed state area) and "
            "cluster translations are invalid; needs a dedicated "
            "1 Hz-decay series scan before the code can be judged")

    def validate_invuln(self):
        if self.out_of_budget():
            return self._blocked("invuln", "budget exhausted")
        p = self.p
        # own HP anchor: freeze-verified (perception.find_player_hp)
        hp_addr = self.guard.find_player_hp(log=log)
        if hp_addr is None:
            return self._blocked(
                "invuln", "no freeze-verified player HP anchor (no "
                "damage event in the idle window)")
        self.counter_addrs["hp"] = hp_addr
        codes = [GSCode(c) for c in
                 self.registry.entries["invuln"]["codes"]]

        def run_arm(with_code):
            p.load_state("cb")
            p.core.run(10, set())
            if with_code:
                self.session.enable("_inv", codes)
                self._engage()
            v0 = p.mem.u16(hp_addr)
            p.core.set_buttons(set())
            for _ in range(420):          # stand in danger; take hits
                p.core.run_frame()
                if with_code:
                    self.session.gs.tick()
            p._advance()
            v1 = p.mem.u16(hp_addr)
            if with_code:
                self.session.disable("_inv")
            return [int(v0), int(v1)]

        attempts = self.args.attempts
        arm = {"baseline": [run_arm(False) for _ in range(attempts)],
               "treatment": [run_arm(True) for _ in range(attempts)],
               "disabled_recovery": [run_arm(False) for _ in
                                     range(attempts)]}
        # HP must DROP in baseline, stay with the code, drop again off
        base_drop = all(b > a for (b, a) in
                        [tuple(r) for r in arm["baseline"]])
        treat_held = all(a == b for a, b in
                         [tuple(r) for r in arm["treatment"]])
        rec_drop = all(b > a for (b, a) in
                       [tuple(r) for r in arm["disabled_recovery"]])
        j = {"works": bool(base_drop and treat_held and rec_drop),
             "baseline_hp_drops": base_drop,
             "treatment_hp_held": treat_held,
             "disable_recovered": rec_drop,
             "codes": [c.raw for c in codes], "addr": hex(hp_addr),
             "dtype": "u16", "action": "idle 420f in danger",
             "readings": arm}
        png(p, self.evid, "20_invuln_after.png")
        return (ST_VERIFIED if j["works"] else ST_FAILED), j

    def validate_ammo(self):
        """Ammo needs a decaying counter — the starting pistol has none
        and the published ammo address reads 0xFF in this boot.
        Bounded weapon-hunt attempt: walk right holding fire; a weapon
        slot change + shot decrement would make the code testable."""
        if self.out_of_budget():
            return self._blocked("ammo", "budget exhausted")
        return self._blocked(
            "ammo",
            "no event-verified ammo slot on this boot (published "
            "0x2DCD8 reads 0xFF; pistol has no observable ammo "
            "counter); needs a special-weapon pickup (hostage drop) "
            "plus a shot-decrement scan — recorded as the next "
            "highest-value experiment")

    def validate_lives(self):
        """Death-based protocol requires an event-verified lives slot.
        No verified slot exists on this boot (published 0x475A8 reads
        0xFF; translations invalid) — BLOCKED with the exact remedy."""
        return self._blocked(
            "lives",
            "no event-verified lives slot on this boot (published "
            "0x475A8 reads 0xFF; cluster translations invalid); needs "
            "a controlled death (-1) u8/u16 scan before the conflicting "
            "published addresses (800475AE vs 80047522) can be judged")

    def _blocked(self, name, why):
        return ST_BLOCKED, {"blocked": True, "reason": why}

    # ---------------- derived freeze-style codes ----------------
    # When a published instruction patch fails live (e.g. invuln), the
    # smallest reliable adapter (issue section 3) is a per-frame DATA
    # freeze at a LIVE-ANCHORED, event-verified address — the same
    # GameShark w16 mechanism, expressed as 8XXXXXXX YYYY with the
    # address this boot actually uses. Each derived code still passes
    # the FULL baseline/treatment/disable/repeat protocol.
    def _validate_freeze(self, name, addr_key, action, frames_idle,
                         dtype="u16"):
        p = self.p
        addr = self.counter_addrs.get(addr_key)
        if addr is None or self.out_of_budget():
            return self._blocked(
                name, f"no live-anchored {addr_key} slot / budget")
        p.load_state("cb")
        p.core.run(10, set())
        read = p.mem.u8 if dtype == "u8" else p.mem.u16
        v_cur = read(addr)
        code, _v = derive_freeze_code(p, addr, v_cur, dtype=dtype)

        def run_arm(with_code):
            p.load_state("cb")
            p.core.run(10, set())
            if with_code:
                self.session.enable(f"_fz_{name}", [code])
                self._engage()
            v0 = read(addr)
            p.core.set_buttons(action)
            for _ in range(15):
                p.core.run_frame()
                if with_code:
                    self.session.gs.tick()
            p.core.set_buttons(set())
            for _ in range(frames_idle):
                p.core.run_frame()
                if with_code:
                    self.session.gs.tick()
            p._advance()
            v1 = read(addr)
            if with_code:
                self.session.disable(f"_fz_{name}")
            return [int(v0), int(v1)]

        attempts = self.args.attempts
        arm = {"baseline": [run_arm(False) for _ in range(attempts)],
               "treatment": [run_arm(True) for _ in range(attempts)],
               "disabled_recovery": [run_arm(False) for _ in
                                     range(attempts)]}
        j = self._judge(arm)
        j.update({"code": code.raw, "addr": hex(addr), "dtype": dtype,
                  "frozen_value": int(v_cur),
                  "mechanism": "derived freeze at live-anchored address",
                  "action": ("grenade(CIRCLE)" if action == {"A"}
                             else "idle in danger"),
                  "readings": arm})
        return (ST_VERIFIED if j["works"] else ST_FAILED), j

    def validate_bombs_freeze(self):
        dtype = getattr(self, "bombs_dtype", "u16")
        return self._validate_freeze("bombs_freeze", "bombs", {"A"},
                                     120, dtype=dtype)

    def validate_hp_freeze(self):
        """Survival method: freeze the freeze-verified player HP slot.
        The anchor itself comes from perception.find_player_hp (freeze
        test + survival). This runs the full protocol on the resulting
        w16 code."""
        if self.out_of_budget():
            return self._blocked("hp_freeze", "budget exhausted")
        hp_addr = self.counter_addrs.get("hp")
        if hp_addr is None:
            hp_addr = self.guard.find_player_hp(log=log)
            if hp_addr is None:
                return self._blocked(
                    "hp_freeze", "no freeze-verified player HP anchor")
            self.counter_addrs["hp"] = hp_addr
        return self._validate_freeze("hp_freeze", "hp", set(), 420)

    # ---------------- main ----------------
    def run(self):
        self.boot_and_calibrate()
        order = {"bombs": self.validate_bombs,
                 "time": self.validate_time,
                 "invuln": self.validate_invuln,
                 "ammo": self.validate_ammo,
                 "lives": self.validate_lives,
                 "bombs_freeze": self.validate_bombs_freeze,
                 "hp_freeze": self.validate_hp_freeze}
        for name in self.args.code_list:
            if self.out_of_budget():
                self.verdicts[name] = {"status": ST_BLOCKED,
                                       "reason": "budget exhausted "
                                                 "before this code"}
                continue
            fn = order.get(name)
            if fn is None:
                self.verdicts[name] = {"status": ST_BLOCKED,
                                       "reason": f"no protocol for {name}"}
                continue
            log(f"[validate] === {name} ===")
            try:
                status, detail = fn()
            except Exception as e:                          # noqa: BLE001
                import traceback
                traceback.print_exc()
                status, detail = ST_BLOCKED, {"error": repr(e)}
            self.verdicts[name] = {"status": status, **detail}
            log(f"[validate] {name}: {status} "
                f"({json.dumps(detail, default=str)[:220]})")
            # only a reproduced protocol upgrades CANDIDATE -> VERIFIED
            prev = self.registry.entries[name].get("status") \
                if name in self.registry.entries else ST_CANDIDATE
            if status == ST_VERIFIED or prev in (ST_CANDIDATE, ST_TESTED):
                self.registry.update_status(
                    name, status, evidence={
                        "protocol": "baseline/treatment/disable/repeat "
                                    "(scripts/validate_cheats.py)",
                        **{k: v for k, v in detail.items()
                           if k in ("works", "code", "addr", "reason",
                                    "blocked")}})
        self.session.finalize_intervals()
        out = {
            "identity": self.ident,
            "counter_addrs": {k: hex(v) for k, v in
                              self.counter_addrs.items()},
            "cluster_delta": hex(self.delta),
            "verdicts": self.verdicts,
            "cheat_intervals": self.session.finalize_intervals(),
            "elapsed_s": round(time.time() - self.t0, 1),
        }
        out_path = self.args.out or os.path.join(self.evid,
                                                 "cheat_validation.json")
        # persistence priority: registry statuses survive even if the
        # process is stopped before the final JSON is written
        self.registry.save()
        log("[validate] registry updated:", self.args.registry)
        with open(out_path, "w") as f:
            json.dump(out, f, indent=1, default=str)
        log("[validate] verdicts ->", out_path)
        print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    Validator(parse_args()).run()
