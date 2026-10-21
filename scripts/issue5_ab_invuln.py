#!/usr/bin/env python3
"""issue5_ab_invuln.py — DECISIVE controlled A/B for hp_pair_freeze
(issue #5 continuation §3).

Prior sessions reported the HP pair 0x800CA2F6/0x800CA2FE VERIFIED,
but the verdict artifact (cheval_20261021_*) is NOT present in the
workspace and the canonical exploration runner never ran. Per the
issue directive, the pair is NOT assumed authoritative — this script
REPRODUCES the original controlled experiment from one verified
checkpoint with a deterministic input schedule:

  one boot -> ensure_mission -> savestate `cb` (clean, no cheats)
  pair co-drop confirmation on THIS boot (>= 3 co-drops, else abort)

  Arm A (control)   : no cheats, identical schedule
  Arm B1/B2 (treat) : hp_pair freeze w16 @boot-derived values, GS tick
                      EVERY frame (hardware cadence, gs_run path)
  Arm C (treat+tel) : freeze + death/lives telemetry sensors recorded

  Schedule (identical all arms): RIGHT held; Y burst (g%45)<12;
  B hop (g%90) in [40,47]; global phase g — chunk-independent.

Recorded per frame: pair u16 x2, i-frame word, per-life accumulator,
flags word, score u32; screenshots at damage/death + every 600f;
sha256 manifest per arm; combined ab_summary.json.

Acceptance:
  A shows pair drops (damage) or a confirmed death;
  B shows the pair HELD + alive across the horizon;
  a successful B REPEATS (B2);
  C sensors agree with B. If B dies via a non-damage path, that is
  recorded as the instant-death path evidence (freeze != immortality).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np
from PIL import Image                                     # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.agent.cheatprof import CheatSession, CHEAT_ASSISTED  # noqa
from ps1play.agent.gameshark import GSCode                # noqa: E402
from mission import ensure_mission                        # noqa: E402
from issue4_controller import boot                        # noqa: E402
from issue5_explore_invuln import gs_run                  # noqa: E402
from validate_inv2 import PAIR, FLAGS, SCORE, read_flags   # noqa: E402

IFRAME = 0xCA30C
PER_LIFE = 0xCA2E0          # u16 per-life accumulator (resets on death)
Y_PERIOD, Y_LEN = 45, 12
HOP_PERIOD, HOP_A, HOP_B = 90, 40, 47


def _log(*a):
    print("[ab-invuln]", *a, file=sys.stderr, flush=True)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--opt-in", action="store_true")
    ap.add_argument("--frames", type=int, default=3600,
                    help="bounded horizon per arm (frames)")
    ap.add_argument("--tag", default="ab1")
    ap.add_argument("--evidence-dir", default=None)
    a = ap.parse_args(argv)
    if not a.opt_in:
        ap.error("--opt-in required: treatment arms use the VERIFIED "
                 "hp_pair_freeze and are never a no-cheat clear")
    if a.evidence_dir is None:
        base = labconfig.resolve_path("evidence_dir") or os.path.join(
            _REPO, "evidence_local")
        a.evidence_dir = os.path.join(
            base, f"ab_invuln_{a.tag}_{time.strftime('%Y%m%d_%H%M%S')}")
    return a


def schedule_button(g):
    """Deterministic advance schedule — function of GLOBAL phase only."""
    b = {"RIGHT"}
    if (g % Y_PERIOD) < Y_LEN:
        b.add("Y")
    if HOP_A <= (g % HOP_PERIOD) <= HOP_B:
        b.add("B")
    return b


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest(dirpath):
    out = {}
    for name in sorted(os.listdir(dirpath)):
        fp = os.path.join(dirpath, name)
        if os.path.isfile(fp):
            out[name] = {"bytes": os.path.getsize(fp),
                         "sha256": sha256_file(fp)}
    return out


def shot(p, outdir, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(outdir, name))


def read_state(p):
    return {
        "pair0": int(p.mem.u16(PAIR[0])),
        "pair1": int(p.mem.u16(PAIR[1])),
        "iframe": int(p.mem.u16(IFRAME)),
        "per_life": int(p.mem.u16(PER_LIFE)),
        "flags": int(p.mem.u32(FLAGS)) & 0xFF,
        "score": int(p.mem.u32(SCORE)),
    }


def confirm_codrops(p, danger_f=480):
    """No-cheat: the candidate pair must co-drop on hits THIS boot."""
    p.load_state("cb")
    p.core.run(10, set())
    p.core.set_buttons({"RIGHT"})
    for _ in range(300):
        p.core.run_frame()
    p.core.set_buttons(set())
    prev = (int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1])))
    codrops, traj = 0, []
    for _ in range(danger_f):
        p.core.run_frame()
        pr = (int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1])))
        if pr[0] < prev[0] and pr[1] < prev[1]:
            codrops += 1
        traj.append(pr)
        prev = pr
    p._advance()
    return codrops, traj


def run_arm(p, session, name, outdir, freeze, frames, trace):
    """One arm from the SAME cb state, identical schedule."""
    os.makedirs(outdir, exist_ok=True)
    p.load_state("cb")
    p.core.run(10, set())
    p._advance()
    codes = None
    if freeze:
        v0 = int(p.mem.u16(PAIR[0]))
        v1 = int(p.mem.u16(PAIR[1]))
        codes = [GSCode(f"8{PAIR[0]:07X} {v0 & 0xFFFF:04X}"),
                 GSCode(f"8{PAIR[1]:07X} {v1 & 0xFFFF:04X}")]
        session.enable(f"hp_pair_freeze_{name}", codes)
        for _ in range(2):                      # hardware-GS pre-engage
            p.core.run_frame()
            session.gs.tick()
        trace.write({"type": "cheats_enabled", "arm": name,
                     "codes": [c.raw for c in codes], "disclosed": True})
    start_vals = read_state(p)
    rows = []
    damage_events = []
    deaths = []
    stop = None
    t0 = time.time()
    prev_pair = (start_vals["pair0"], start_vals["pair1"])
    in_play = start_vals["flags"] == 0xFF
    shot(p, outdir, f"start_{name}.png")
    game_over_shots = 0
    for g in range(frames):
        p.core.set_buttons(schedule_button(g))
        p.core.run_frame()
        if freeze:
            session.gs.tick()
        st = read_state(p)
        pr = (st["pair0"], st["pair1"])
        row = {"g": g, **st}
        # damage = either pair word dropped vs previous frame
        if pr[0] < prev_pair[0] or pr[1] < prev_pair[1]:
            damage_events.append({"g": g, "from": list(prev_pair),
                                  "to": list(pr)})
            if len(damage_events) <= 3 or len(damage_events) % 20 == 0:
                shot(p, outdir, f"damage_{name}_g{g:05d}.png")
        # death transition: active-play word leaves 0xFF
        if in_play and st["flags"] != 0xFF:
            deaths.append({"g": g, "flags": st["flags"],
                           "pair": list(pr),
                           "per_life": st["per_life"],
                           "score": st["score"]})
            shot(p, outdir, f"death_{name}_g{g:05d}.png")
            trace.write({"type": "death", "arm": name, "g": g,
                         "flags": st["flags"], "pair": list(pr),
                         "disclosed": True})
            in_play = False
            # game-over loop -> stop the arm immediately (bounded)
            if game_over_shots == 0:
                shot(p, outdir, f"postdeath_{name}_g{g:05d}.png")
            game_over_shots += 1
            if game_over_shots > 600:
                stop = "STOP_GAME_OVER_LOOP"
                break
        elif (not in_play) and st["flags"] == 0xFF:
            in_play = True                    # respawned / continued
            trace.write({"type": "respawn", "arm": name, "g": g,
                         "per_life": st["per_life"], "disclosed": True})
        rows.append(row)
        prev_pair = pr
        if g % 600 == 599:
            shot(p, outdir, f"progress_{name}_g{g:05d}.png")
    if freeze:
        session.disable(f"hp_pair_freeze_{name}")
    p._advance()
    dur = time.time() - t0
    end_vals = read_state(p)
    held = (end_vals["pair0"] == start_vals["pair0"] and
            end_vals["pair1"] == start_vals["pair1"]) if freeze else None
    rep = {
        "arm": name, "freeze": freeze, "frames_target": frames,
        "frames_run": len(rows), "stop_reason": stop or "HORIZON_END",
        "duration_s": round(dur, 1),
        "start_state": start_vals, "end_state": end_vals,
        "codes": [c.raw for c in codes] if codes else None,
        "pair_held": held,
        "damage_events": len(damage_events),
        "damage_first": damage_events[:5],
        "deaths": deaths, "death_count": len(deaths),
        "disclosure": ("CHEAT_ASSISTED_EXPLORATION arm — never a "
                       "no-cheat clear") if freeze else
                      "control arm (no cheats)",
    }
    with open(os.path.join(outdir, "report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    with open(os.path.join(outdir, "frames.jsonl"), "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    rep["manifest"] = manifest(outdir)
    with open(os.path.join(outdir, "report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    trace.write({"type": "arm_end", **{k: rep[k] for k in
                 ("arm", "freeze", "frames_run", "stop_reason",
                  "pair_held", "damage_events", "death_count")}})
    _log(f"arm {name}: frames={len(rows)} damage={len(damage_events)} "
         f"deaths={len(deaths)} held={held} stop={rep['stop_reason']} "
         f"({dur:.0f}s)")
    return rep


def main():
    args = parse_args()
    os.makedirs(args.evidence_dir, exist_ok=True)
    trace_path = os.path.join(args.evidence_dir, "trace.jsonl")
    trace = JsonlTraceLocal(trace_path)

    _log("booting ...")
    t0 = time.time()
    p, fwmode = boot()
    _log(f"booted ({fwmode}) in {time.time() - t0:.0f}s")
    g = ensure_mission(p, tries=6, log=_log, want_hp_cands=False)
    if not g.get("in_mission"):
        sys.exit("!! mission gate failed")
    trace.write({"type": "run_start", "tag": args.tag,
                 "profile": CHEAT_ASSISTED, "opt_in": True,
                 "firmware_mode": fwmode, "game": p.game,
                 "frames_per_arm": args.frames,
                 "t": time.strftime("%Y-%m-%d %H:%M:%S")})
    p.save_state("cb")

    v0 = (int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1])))
    if v0[0] < 50 or v0[1] < 50:
        sys.exit(f"!! pair words look wrong at cb: {v0}")
    _log("confirming HP pair co-drop on hits THIS boot (no cheats) ...")
    codrops, traj = confirm_codrops(p)
    trace.write({"type": "pair_codrop_check", "pair": [hex(a) for a in
                 PAIR], "codrops": codrops,
                 "traj_head": traj[:8], "traj_tail": traj[-8:]})
    if codrops < 3:
        sys.exit(f"!! HP pair co-drop NOT reproduced this boot "
                 f"(codrops={codrops}) — refusing the A/B; return to "
                 "static analysis")
    _log(f"pair co-drop confirmed ({codrops}x) — proceeding to arms")

    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    reports = {}
    reports["A"] = run_arm(p, session, "A",
                           os.path.join(args.evidence_dir, "arm_A"),
                           freeze=False, frames=args.frames, trace=trace)
    reports["B1"] = run_arm(p, session, "B1",
                            os.path.join(args.evidence_dir, "arm_B1"),
                            freeze=True, frames=args.frames, trace=trace)
    reports["B2"] = run_arm(p, session, "B2",
                            os.path.join(args.evidence_dir, "arm_B2"),
                            freeze=True, frames=args.frames, trace=trace)
    reports["C"] = run_arm(p, session, "C",
                           os.path.join(args.evidence_dir, "arm_C"),
                           freeze=True, frames=args.frames, trace=trace)

    a, b1, b2, c = reports["A"], reports["B1"], reports["B2"], reports["C"]
    verdict = {
        "baseline_damage_or_death": bool(a["damage_events"] or
                                         a["death_count"]),
        "treatment_pair_held": bool(b1["pair_held"] and b2["pair_held"]
                                    and c["pair_held"]),
        "treatment_alive": bool(b1["death_count"] == 0 and
                                b2["death_count"] == 0 and
                                c["death_count"] == 0),
        "repeat_consistent": bool(
            b1["damage_events"] == b2["damage_events"] == 0),
        "telemetry_agrees": bool(c["pair_held"] and
                                 c["death_count"] == 0),
        "causal_reduction": None,   # filled below
    }
    verdict["causal_reduction"] = bool(
        verdict["baseline_damage_or_death"] and
        verdict["treatment_pair_held"] and verdict["treatment_alive"])
    summary = {
        "tag": args.tag, "t": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pair": [hex(x) for x in PAIR],
        "codrops_confirmed": codrops,
        "arms": {k: {kk: rr[kk] for kk in
                     ("freeze", "frames_run", "stop_reason", "pair_held",
                      "damage_events", "death_count", "duration_s")}
                 for k, rr in reports.items()},
        "verdict": verdict,
        "acceptance": "PASS" if verdict["causal_reduction"] else "FAIL",
        "disclosure": "CHEAT_ASSISTED_EXPLORATION experiment — the "
                      "treatment arms use hp_pair_freeze and are never "
                      "a no-cheat clear",
    }
    with open(os.path.join(args.evidence_dir, "ab_summary.json"),
              "w") as f:
        json.dump(summary, f, indent=1)
    trace.write({"type": "verdict", **summary})
    session.disable_all()
    _log("VERDICT:", summary["acceptance"],
         json.dumps(verdict))
    _log("summary:", os.path.join(args.evidence_dir, "ab_summary.json"))


class JsonlTraceLocal:
    """Minimal JSONL trace writer (no ps1play dependency here)."""

    def __init__(self, path):
        self.f = open(path, "a")

    def write(self, rec):
        rec["t"] = time.strftime("%H:%M:%S")
        self.f.write(json.dumps(rec, default=str) + "\n")
        self.f.flush()


if __name__ == "__main__":
    main()
