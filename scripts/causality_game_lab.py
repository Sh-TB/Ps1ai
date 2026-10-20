#!/usr/bin/env python3
"""causality_game_lab.py — ISSUE 4 Phase 1: per-button input causality on
the REAL game (SLUS-01212) from a known start state.  v2.

Lessons built in (v1 post-mortem, evidence issue4_causality/dbg_*.png):
  * v1 saved its base state on the "NOW LOADING!" screen (the mission-1
    opening killed the idle player during the calibration probe) — every
    leg then restored a static loading screen: pixels frozen, no input
    response, identical churn.  v2 therefore:
      a) boots with want_hp_cands=False (no lethal idle probe),
      b) re-derives the grenade anchor for THIS boot,
      c) saves the base state and VALIDATES it by round-trip: load ->
         responsive() must pass again before any leg runs,
      d) samples the pad-mirror (static RE: u16 @0x0D4948 / @0x0D494A)
         DURING each leg — direct button-bit -> RAM evidence, plus
      e) pixel + RAM-diff separation vs a same-state baseline leg.

Mapping (core source input.c): B->Cross A->Circle Y->Square X->Triangle.
Mirror bit expectations (PSX pad layout, verified live in this lab's
output — the report records the OBSERVED masks too):
  u16 @0x0D4948: UP 0x0010 RIGHT 0x0020 DOWN 0x0040 LEFT 0x0080
  u16 @0x0D494A: TRIANGLE 0x1000 CIRCLE 0x2000 CROSS 0x4000 SQUARE 0x8000

Usage:
  python3 scripts/causality_game_lab.py [--frames 60] [--repeat 2]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.api import PS1Play                           # noqa: E402
from ps1play.core.inputmap import parse_buttons, BTN_NAMES  # noqa: E402
from mission import ensure_mission, responsive            # noqa: E402

SCORE_OFF = 0x0EE318        # static RE, 9 xrefs (u32le)
MIRROR_DPAD = 0x0D4948      # static RE: injected pad bits during gameplay
MIRROR_ACT = 0x0D494A       # reads 0 during gameplay holds (v3 evidence)
ACTION_FLAG = 0x95790       # u8: 0 idle, 1 while ANY action btn held (2x2)
GRENADE_U8 = 0xEDCF4        # Issue #3 Phase G VERIFIED; re-proved x3 boot-local
ZONE = 0x1FC000

SPECS = [
    ("NO_INPUT", ""),
    ("RIGHT", "RIGHT"),
    ("LEFT", "LEFT"),
    ("UP", "UP"),
    ("DOWN", "DOWN"),
    ("JUMP_CROSS", "B"),
    ("FIRE_SQUARE", "Y"),
    ("GRENADE_CIRCLE", "A"),
    ("RIGHT_FIRE", "RIGHT+Y"),
    ("RIGHT_JUMP", "RIGHT+B"),
]

EXPECT = {  # spec-name -> (mirror_addr_off, mask)
    "RIGHT": (MIRROR_DPAD, 0x0020),
    "LEFT": (MIRROR_DPAD, 0x0080),
    "UP": (MIRROR_DPAD, 0x0010),
    "DOWN": (MIRROR_DPAD, 0x0040),
    "JUMP_CROSS": (MIRROR_ACT, 0x4000),
    "FIRE_SQUARE": (MIRROR_ACT, 0x8000),
    "GRENADE_CIRCLE": (MIRROR_ACT, 0x2000),
    "RIGHT_FIRE": (MIRROR_DPAD, 0x0020),      # dpad part; act mask 0x8000
    "RIGHT_JUMP": (MIRROR_DPAD, 0x0020),
}


def _log(*a):
    print(*a, file=sys.stderr, flush=True)


def derive_bombs_anchor(p, hot="anchor_hot", presses=3,
                        zone=(0xE0000, 0xF4000), tries=3):
    """Strict deterministic series for THIS boot, death-proof.

    The mission-1 opening kills an idler within seconds, so a long
    press/settle chain on live frames breaks the series (v2 lesson).
    Instead: from the hot state, each press runs from a FRESH restore
    of the same state, so the series 10,9,8,7(,6) is exact regardless
    of what happens after.  Returns strict u8 candidates.
    """
    lo, hi = zone
    for attempt in range(tries):
        p.load_state(hot)
        base = p.mem.ram[lo:hi].copy()
        snaps = [base]
        for _ in range(presses):
            p.load_state(hot)
            p.core.run(30 + attempt * 10, set())     # stagger origin
            p.core.set_buttons({"A"})
            for _ in range(30):
                p.core.run_frame()
            p.core.set_buttons(set())
            p.core.run(20, set())
            snaps.append(p.mem.ram[lo:hi].copy())
        p._advance()
        cands = []
        for i in range(1, hi - lo):
            series = [int(s[i]) for s in snaps]
            if all(series[k] - series[k + 1] == 1
                   for k in range(len(series) - 1)) and 0 <= series[-1] <= 60:
                cands.append({"addr": lo + i, "series": series})
        if cands:
            # strict confirm: one more press, fresh restore, later origin
            good = []
            for c in cands[:64]:
                p.load_state(hot)
                p.core.run(40 + attempt * 10, set())
                p.core.set_buttons({"A"})
                for _ in range(30):
                    p.core.run_frame()
                p.core.set_buttons(set())
                p.core.run(20, set())
                p._advance()
                if c["series"][0] - int(p.mem.u8(c["addr"])) == presses + 1:
                    good.append(c)
            _log(f"[anchor] attempt{attempt}: cands={len(cands)} "
                 f"strict={len(good)} "
                 f"{[hex(c['addr']) for c in good[:6]]}")
            if good:
                return good
        _log(f"[anchor] attempt{attempt}: no candidates")
    return []


def _leg(p, state, frames, spec, sample_at=(10, 30, 50)):
    """One leg: restore `state`, hold spec, sample mirror, return metrics."""
    p.load_state(state)
    s0 = p.mem.snapshot()
    btns = parse_buttons(spec) if spec else set()
    p.core.set_buttons(btns)
    mirrors = []
    for i in range(frames):
        p.core.run_frame()
        if i in sample_at:
            mirrors.append((p.mem.u16(MIRROR_DPAD), p.mem.u16(MIRROR_ACT)))
    p._advance()
    s1 = p.mem.snapshot()
    return {
        "buttons": sorted(BTN_NAMES[b] for b in btns),
        "bits": sorted(int(b) for b in btns),
        "mirror_samples": [f"{a:04X}/{b:04X}" for a, b in mirrors],
        "ram_changed_bytes": int(np.flatnonzero(s0 != s1).size),
        "score_after": int(p.mem.u32(SCORE_OFF)),
        "action_flag_after": int(p.mem.u8(ACTION_FLAG)),
        "grenade_after": int(p.mem.u8(GRENADE_U8)),
        "rgb": p.core.frame_rgb(),
    }


def jump_state_experiment(p, state, reps=2, hold=8):
    """Bytes in AIRBORNE state that return to baseline after landing.

    Proper same-timeline comparison (v4 fix): baseline idle leg sampled
    at frames 9 and 49; treatment leg (CROSS held `hold` frames then
    released) sampled at the same frames.  A jump-state byte differs
    from the baseline AT frame 9 (airborne) and matches it again at
    frame 49 (landed).  Bytes consistent across both reps are reported.
    """
    results = []
    for rep in range(reps):
        p.load_state(state)
        p.core.run(2 * rep, set())
        base = {}
        for i in range(50):
            p.core.run_frame()
            if i in (9, 49):
                base[i] = p.mem.snapshot()
        p._advance()
        p.load_state(state)
        p.core.run(2 * rep, set())
        air = {}
        p.core.set_buttons(parse_buttons("B"))
        for i in range(hold):
            p.core.run_frame()
        p.core.set_buttons(set())
        for i in range(50 - hold):
            p.core.run_frame()
            if i + hold in (9, 49):
                air[i + hold] = p.mem.snapshot()
        p._advance()
        d9 = air[9].astype(np.int16) - base[9].astype(np.int16)
        d49 = air[49].astype(np.int16) - base[49].astype(np.int16)
        cands = np.flatnonzero((d9 != 0) & (d49 == 0))
        results.append({"rep": rep,
                        "airborne_changed": int(np.flatnonzero(d9).size),
                        "airborne_only_addrs":
                            [hex(int(x)) for x in cands[:32]],
                        "airborne_only_count": int(cands.size)})
    common = None
    for r in results:
        s = set(r["airborne_only_addrs"])
        common = s if common is None else (common & s)
    return {"reps": results, "consistent_addrs": sorted(common or [])}


def _pix(a, b):
    if a is None or b is None:
        return None
    return round(float(np.abs(a.astype(np.int16)
                              - b.astype(np.int16)).mean()), 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--evidence-dir", default=labconfig.resolve_path(
        "evidence_dir") or os.path.join(_REPO, "evidence_local"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    outdir = os.path.join(args.evidence_dir, "issue4_causality")
    os.makedirs(outdir, exist_ok=True)
    out = {"schema": "ps1play-causality-game/2",
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                          time.gmtime()),
           "frames": args.frames, "mapping_source":
               "beetle_psx input.c: B->Cross A->Circle Y->Square X->Triangle",
           "experiments": []}

    # v3 boot: SAME sequence as route_timed_run.py (the flow that
    # actually reached IN MISSION on 2026-10-20). The v2 failure
    # ("gameplay lost after anchor derivation", gate idle=32 self-play)
    # came from skipping enter_gameplay3(): without adaptive boot
    # navigation the game sits on the attract loop, where the demo
    # feeds its own RIGHT bit and the gate can never pass.
    ws = labconfig.resolve_path("workspace")
    fw = labconfig.resolve_firmware(
        os.environ.get("M1_FIRMWARE", "openbios"), ws)
    kw = {}
    core_path = labconfig.resolve_path("core")
    if core_path:
        kw["core"] = core_path
    if ws:
        kw["workspace"] = ws
    if fw["override_vars"]:
        kw["var_overrides"] = fw["override_vars"]
    p = PS1Play(labconfig.resolve_path("game"), **kw)
    out["boot_info"] = p.boot()
    out["firmware_mode"] = fw["mode"]
    fw_ev = labconfig.firmware_log_evidence(
        getattr(p.core, "log_history", []))
    trust_ok, trust_detail = labconfig.check_firmware_trust(fw, fw_ev)
    out["firmware_trust"] = {"ok": bool(trust_ok), "detail": str(trust_detail)}
    _log(f"[causality] firmware={fw['mode']} trust={trust_ok} "
         f"({trust_detail})")
    if not trust_ok:
        out["error"] = f"firmware trust failed: {trust_detail}"
        _write(out, args, outdir)
        return 3
    nav = p.enter_gameplay3()
    out["enter_gameplay3"] = nav
    if not nav.get("in_game"):
        out["error"] = "adaptive boot navigation failed"
        _log("[causality] FATAL: enter_gameplay3 not in_game")
        _write(out, args, outdir)
        return 3
    gate = ensure_mission(p, log=_log, want_hp_cands=False)
    out["gate"] = gate
    if not gate.get("in_mission"):
        out["error"] = "could not reach active mission gameplay"
        _log("[causality] FATAL: no active gameplay")
        _write(out, args, outdir)
        return 3

    # HOT state: walk right briefly (the opening is lethal to idlers),
    # then save.  v4: the grenade anchor is CONFIRMED on this boot by
    # strict decrement trials inside the GRENADE verdict (v2's
    # derive_bombs_anchor re-derivation proved fragile and is no longer
    # load-bearing; Issue #3 Phase-G already VERIFIED the series).
    p.core.run(90, {"RIGHT"})
    p._advance()
    p.save_state("anchor_hot")
    bombs_addr = None

    # caus0 = the hot state itself (pre-anchor, in gameplay). Restore it
    # and VALIDATE by round-trip before any leg runs.
    p.load_state("anchor_hot")
    p.save_state("caus0")
    # ROUND-TRIP VALIDATION: the state must restore to live gameplay
    ok, (w1, churn) = responsive(p)
    out["state_roundtrip"] = {"responsive_ok": bool(ok),
                              "pad_word": int(w1), "churn": int(churn)}
    if not ok:
        out["error"] = "saved state does not restore to live gameplay"
        _write(out, args, outdir)
        return 3
    out["bombs_at_start"] = None
    out["score_at_start"] = int(p.mem.u32(SCORE_OFF))
    out["grenade_at_start"] = int(p.mem.u8(GRENADE_U8))
    _log(f"[causality] base state ok: bombs={out['bombs_at_start']} "
         f"score={out['score_at_start']}")

    for name, spec in SPECS:
        exp = {"name": name, "spec": spec, "legs": []}
        base_rgb = None
        for rep in range(args.repeat):
            b = _leg(p, "caus0", args.frames, "")
            t = _leg(p, "caus0", args.frames, spec)
            n = _leg(p, "caus0", args.frames, "")
            pd = _pix(b["rgb"], t["rgb"])
            nd = _pix(b["rgb"], n["rgb"])
            if base_rgb is None:
                base_rgb = b["rgb"]
            for leg in (b, t, n):
                leg.pop("rgb")
            exp["legs"].append({
                "rep": rep, "baseline": b, "treatment": t, "noise": n,
                "pixel_treat_vs_base": pd, "pixel_noise_floor": nd,
            })
        if name == "JUMP_CROSS":
            exp["jump_state"] = jump_state_experiment(
                p, "caus0", reps=args.repeat)
        # ---- verdicts ----
        per_rep = []
        for leg in exp["legs"]:
            pdt = leg["pixel_treat_vs_base"] or 0
            pdn = leg["pixel_noise_floor"] or 0
            px = pdt > max(2.0, 3 * pdn)
            ram = leg["treatment"]["ram_changed_bytes"] > max(
                64, 2 * leg["baseline"]["ram_changed_bytes"])
            # pad mirror: expected bit set in EVERY treatment sample
            bits_ok = None
            if name in EXPECT:
                off, mask = EXPECT[name]
                samples = [int(s.split("/")[0 if off == MIRROR_DPAD else 1],
                               16) for s in leg["treatment"]["mirror_samples"]]
                bits_ok = all(s & mask for s in samples)
            per_rep.append({"pixel": bool(px), "ram": bool(ram),
                            "mirror_bits": bits_ok})
        exp["per_rep"] = per_rep
        if name == "NO_INPUT":
            # v4 fix: 0.0 noise floor is VALID (falsy-zero bug in v3 made
            # a perfectly deterministic world read as INCONCLUSIVE).
            exp["verdict"] = ("CAUSAL" if all(
                leg["pixel_noise_floor"] is not None
                and leg["pixel_noise_floor"] < 2.0
                and leg["baseline"]["mirror_samples"].count(
                    "0000/0000") == len(leg["baseline"]["mirror_samples"])
                for leg in exp["legs"]) else "INCONCLUSIVE")
        elif name in ("JUMP_CROSS", "FIRE_SQUARE", "GRENADE_CIRCLE"):
            # v5: verdicts come from GAME-EFFECT chains only.
            #   * the u8 @0x95790 flag is a STICKY "action pressed once"
            #     latch (it is 1 in post-responsive baselines too), so it
            #     is NOT usable as a held-state signal — dropped from the
            #     chain (v4 lesson).
            #   * pixel/RAM thresholds are noise-relative: the idle world
            #     already churns ~4400 bytes, and a muzzle flash moves few
            #     pixels, so absolute thresholds never fire (v4 lesson).
            fx = all(
                (leg["pixel_treat_vs_base"] is not None and
                 leg["pixel_treat_vs_base"] > max(0.2, 3 * (
                     leg["pixel_noise_floor"] or 0.0))) or
                (leg["treatment"]["ram_changed_bytes"] -
                 leg["baseline"]["ram_changed_bytes"]) > 32
                for leg in exp["legs"])
            if name == "GRENADE_CIRCLE":
                # strict decrement: main leg + 2 dedicated fresh restores
                dec_main = [leg["baseline"]["grenade_after"] -
                            leg["treatment"]["grenade_after"]
                            for leg in exp["legs"]]
                dec = []
                for rep in range(2):
                    p.load_state("caus0")
                    p.core.run(4 + 3 * rep, set())
                    g0 = int(p.mem.u8(GRENADE_U8))
                    p.core.run(40, parse_buttons(spec))
                    p.core.run(20, set())
                    p._advance()
                    dec.append(g0 - int(p.mem.u8(GRENADE_U8)))
                exp["grenade_delta_per_rep"] = {"main_legs": dec_main,
                                                "dedicated": dec}
                exp["verdict"] = ("CAUSAL_STRONG" if fx and
                                  all(d == 1 for d in dec_main + dec) else
                                  "CAUSAL" if fx and
                                  any(d >= 1 for d in dec_main + dec) else
                                  "INCONCLUSIVE")
            elif name == "FIRE_SQUARE":
                scored = all(leg["treatment"]["score_after"] >
                             leg["baseline"]["score_after"]
                             for leg in exp["legs"])
                exp["score_increase"] = scored
                exp["verdict"] = ("CAUSAL_STRONG" if fx and scored else
                                  "CAUSAL" if fx else "INCONCLUSIVE")
            else:  # JUMP_CROSS — airborne state bytes + pixel/ram effect
                js = exp.get("jump_state") or {}
                n_state = len(js.get("consistent_addrs", []))
                exp["jump_state_addrs"] =\
                    js.get("consistent_addrs", [])[:12]
                exp["verdict"] = ("CAUSAL_STRONG" if fx and n_state >= 5
                                  else "CAUSAL" if fx
                                  else "INCONCLUSIVE")
        elif name in EXPECT:
            exp["verdict"] = ("CAUSAL" if all(
                c["mirror_bits"] and (c["pixel"] or c["ram"])
                for c in per_rep) else
                ("CAUSAL_MIRROR_ONLY" if all(c["mirror_bits"]
                                             for c in per_rep)
                 else "INCONCLUSIVE"))
        else:
            exp["verdict"] = ("CAUSAL" if all(
                c["pixel"] or c["ram"] for c in per_rep)
                else "INCONCLUSIVE")
        out["experiments"].append(exp)
        _log(f"[causality] {name}: {exp['verdict']}")

    outpath = args.out or os.path.join(outdir, "causality_report.json")
    with open(outpath, "w") as f:
        json.dump(out, f, indent=1)
    _log("[causality] report:", outpath)
    return 0 if all(e["verdict"].startswith("CAUSAL")
                    for e in out["experiments"]) else 2


def _write(out, args, outdir):
    outpath = args.out or os.path.join(outdir, "causality_report.json")
    with open(outpath, "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    sys.exit(main())
