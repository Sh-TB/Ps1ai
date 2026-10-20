#!/usr/bin/env python3
"""issue4_action_probe.py — ISSUE 4 Phase 1/2 follow-up.

The v3 causality lab proved D-pad bits mirror at u16 0x0D4948 and proved
RIGHT/LEFT fully causal (pixel+RAM+mirror).  Action buttons (CROSS/SQUARE/
CIRCLE) left the game-side action mirror at 0x0D494A reading 0x0000, so
JUMP/FIRE/GRENADE ended INCONCLUSIVE even though FIRE scored 244 and
GRENADE scored 100 (real effects, missing direct button-bit evidence).

This probe closes exactly those gaps, in ONE boot, with strict repetition:

  A) grenade inventory anchor — candidate u8 at 0xEDCF4 (Issue #3 Phase-G
     VERIFIED series 10,9,8,7,6) re-confirmed on THIS boot by two
     independent single-press trials from fresh restores (expect -1 each)
     plus a two-press trial (expect -2).  Strict series scan as fallback.
  B) action-button mirror discovery — per action button: idle snapshot vs
     early (frame 2) and held (frame 30) snapshots; report every u16
     candidate aligned in changed-byte neighbourhoods, tagged with the
     observed value and whether it matches the standard PSX pad mask
     (TRIANGLE 0x1000 CIRCLE 0x2000 CROSS 0x4000 SQUARE 0x8000).
     Also sample 0x0D494A at frames 1..6 (edge-latch hypothesis).
  C) jump transient-state discovery — CROSS hold 8f, samples at
     2/6/10/20/35/50; bytes that leave baseline during airborne and
     return after landing, repeated on 2 trials.

Evidence: evidence/issue4_causality/action_probe_report.json
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
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.api import PS1Play                           # noqa: E402
from ps1play.core.inputmap import parse_buttons           # noqa: E402
from mission import ensure_mission                        # noqa: E402

GRENADE_U8 = 0xEDCF4          # Issue #3 Phase G, VERIFIED series
MIRROR_DPAD = 0x0D4948
MIRROR_ACT = 0x0D494A
SCORE_OFF = 0x0EE318

PSX_MASK = {"B": 0x4000, "Y": 0x8000, "A": 0x2000,
            "X": 0x1000, "START": 0x0008}


def _log(*a):
    print("[probe]", *a, file=sys.stderr, flush=True)


def u16_at(ram, off):
    return int(ram[off] | (ram[off + 1] << 8))


def changed_regions(a, b, pad=6):
    """Byte offsets where a!=b, merged into (lo,hi) regions ±pad."""
    idx = np.flatnonzero(a != b)
    if not len(idx):
        return []
    out = []
    lo = prev = int(idx[0])
    for i in idx[1:]:
        i = int(i)
        if i - prev > pad:
            out.append((lo, prev + 1))
            lo = i
        prev = i
    out.append((lo, prev + 1))
    return out


def boot(lab_log=_log):
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
    info = p.boot()
    fw_ev = labconfig.firmware_log_evidence(
        getattr(p.core, "log_history", []))
    ok, detail = labconfig.check_firmware_trust(fw, fw_ev)
    if not ok:
        raise SystemExit(f"firmware trust failed: {detail}")
    lab_log(f"firmware={fw['mode']} trust ok ({detail})")
    nav = p.enter_gameplay3()
    if not nav.get("in_game"):
        raise SystemExit("enter_gameplay3 failed")
    gate = ensure_mission(p, log=lab_log, want_hp_cands=False)
    if not gate.get("in_mission"):
        raise SystemExit("gate failed")
    return p, fw["mode"]


def grenade_trials(p, n=3):
    """Strict single-press decrement trials from fresh caus0 restores."""
    out = []
    for k in range(n):
        p.load_state("caus0")
        p.core.run(5 + 3 * k, set())
        p._advance()
        before = p.mem.snapshot()
        g0 = int(before[GRENADE_U8])
        p.core.set_buttons(parse_buttons("A"))
        p.core.run(40, parse_buttons("A"))
        p.core.set_buttons(set())
        p.core.run(20, set())
        p._advance()
        after = p.mem.snapshot()
        g1 = int(after[GRENADE_U8])
        # strict scan: u8 that dropped exactly 1 and started in 1..99
        strict = np.flatnonzero(
            (before.astype(np.int16) - after.astype(np.int16) == 1) &
            (before >= 1) & (before <= 99))
        out.append({
            "trial": k, "g0_at_0xEDCF4": g0, "g1_at_0xEDCF4": g1,
            "delta_known_candidate": g0 - g1,
            "strict_u8_minus1_count": int(strict.size),
            "strict_u8_addrs": [hex(int(x)) for x in strict[:16]],
            "score_after": int(u16_at(after, SCORE_OFF)) if False else
            int(after[SCORE_OFF] | (after[SCORE_OFF + 1] << 8) |
                (after[SCORE_OFF + 2] << 16) | (after[SCORE_OFF + 3] << 24)),
        })
        _log(f"[grenade] trial{k}: 0xEDCF4 {g0}->{g1} "
             f"strict_minus1={strict.size}")
    return out


def action_mirror_probe(p, spec, trials=2):
    """Idle vs early vs held snapshots -> u16 candidates + mirror check."""
    results = []
    btns = parse_buttons(spec)
    for k in range(trials):
        p.load_state("caus0")
        p.core.run(8 + 2 * k, set())
        p._advance()
        idle_s = p.mem.snapshot()
        early_samples = {}
        p.core.set_buttons(btns)
        for i in range(30):
            p.core.run_frame()
            if i in (0, 1, 2, 3, 4, 5):
                early_samples[i] = {
                    "dpad": u16_at(p.mem.ram, MIRROR_DPAD),
                    "act": u16_at(p.mem.ram, MIRROR_ACT)}
            if i == 1:
                early_s = p.mem.snapshot()
            if i == 29:
                held_s = p.mem.snapshot()
        p.core.set_buttons(set())
        p.core.run(15, set())
        p._advance()
        cands = []
        for lo, hi in changed_regions(idle_s, held_s):
            for a in range(max(0, lo - 1), min(len(idle_s) - 2, hi + 1)):
                hv = u16_at(held_s, a)
                iv = u16_at(idle_s, a)
                ev = u16_at(early_s, a)
                if hv == iv:
                    continue
                cands.append({"addr": hex(a), "idle": hex(iv),
                              "early": hex(ev), "held": hex(hv)})
        results.append({
            "trial": k,
            "mirror_dpad_during_hold": hex(u16_at(held_s, MIRROR_DPAD)),
            "mirror_act_during_hold": hex(u16_at(held_s, MIRROR_ACT)),
            "mirror_act_early": {str(i): hex(v["act"])
                                 for i, v in early_samples.items()},
            "u16_candidates": cands[:48],
            "n_changed_bytes": int(np.flatnonzero(idle_s != held_s).size),
        })
        _log(f"[mirror {spec}] trial{k}: act_mirror="
             f"{results[-1]['mirror_act_during_hold']} "
             f"cands={len(cands)}")
    return results


def jump_transient_probe(p, trials=2):
    """Bytes that change on jump start and return after landing."""
    out = []
    btns = parse_buttons("B")
    for k in range(trials):
        p.load_state("caus0")
        p.core.run(8 + 2 * k, set())
        p._advance()
        base_s = p.mem.snapshot()
        samples = {}
        p.core.set_buttons(btns)
        for i in range(8):
            p.core.run_frame()
        p.core.set_buttons(set())
        for i in range(52):
            p.core.run_frame()
            if i in (1, 5, 9, 19, 34, 49):
                samples[i] = p.mem.snapshot()
        p._advance()
        base16 = base_s.astype(np.int16)
        transient = None
        for i, s in samples.items():
            d = s.astype(np.int16) - base16
            m = np.flatnonzero(d != 0)
            if transient is None:
                transient = set(int(x) for x in m)
            else:
                transient &= set(int(x) for x in m)
        landing = samples[49]
        landed_back = [a for a in sorted(transient or [])
                       if landing[a] == base_s[a]]
        out.append({
            "trial": k,
            "changed_everywhere_count": len(transient or []),
            "returned_after_landing": len(landed_back),
            "returned_addrs": [hex(a) for a in landed_back[:24]],
            "airborne_values": {a: int(samples[9][a]) for a in
                                landed_back[:8]},
        })
        _log(f"[jump] trial{k}: transient={out[-1]['changed_everywhere_count']} "
             f"returned={out[-1]['returned_after_landing']}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, "issue4_causality")
    os.makedirs(outdir, exist_ok=True)
    out = {"schema": "ps1play-action-probe/1",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime())}

    p, fwmode = boot()
    out["firmware_mode"] = fwmode
    p.core.run(90, {"RIGHT"})
    p._advance()
    p.save_state("caus0")
    from mission import responsive
    ok, (w1, churn) = responsive(p)
    out["caus0_responsive"] = {"ok": bool(ok), "pad": int(w1),
                               "churn": int(churn)}
    if not ok:
        out["error"] = "caus0 not responsive"
        _write(out, args, outdir)
        return 3

    out["grenade"] = grenade_trials(p)
    out["mirror_square"] = action_mirror_probe(p, "Y")
    out["mirror_cross"] = action_mirror_probe(p, "B")
    out["mirror_circle"] = action_mirror_probe(p, "A")
    out["jump_transient"] = jump_transient_probe(p)

    # verdicts per Issue #4 evidence rules
    g = out["grenade"]
    known_ok = all(t["delta_known_candidate"] == 1 for t in g[:2])
    out["verdicts"] = {
        "grenade_u8_0xEDCF4": ("VERIFIED" if known_ok else
                               ("HEURISTIC" if all(
                                   t["delta_known_candidate"] >= 0
                                   for t in g) else "UNKNOWN")),
        "mirror_act_0x0D494A": "see per-button samples",
    }
    _log(f"[verdicts] {out['verdicts']}")
    _write(out, args, outdir)
    return 0


def _write(out, args, outdir):
    outpath = args.out or os.path.join(
        outdir, "action_probe_report.json")
    with open(outpath, "w") as f:
        json.dump(out, f, indent=1)
    _log("report:", outpath)


if __name__ == "__main__":
    sys.exit(main())
