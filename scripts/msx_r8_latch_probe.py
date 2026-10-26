#!/usr/bin/env python3
"""msx_r8_latch_probe.py — Issue #5 session 11 / round 8, the bounded
STEP-3 write-probe from the diff-of-diffs.

The diff (msx_m1end_m2side_diff.py windows A-E + analyze) showed:
  * 0x0EB5FC is a WORLD-ALIVE latch: 0xFF in every live mission world
    (A M2-live, D M1-live), 0x00 within 30f after every m1_end restore
    (B/C/E) and it stays 0 while the ladder dies into attract.
  * The restored m1_end ladder NEVER spawns M2 (3/3 -> attract;
    FLAGS_WORD 0x0EE518 dies to 0 at ~f2400).
  * Natural fresh-boot ladders DO spawn M2 (m2t7, m2t9 — 2/10).

Probe (all DISCLOSED EXPLORATION writes, GS-code constant holds, one
boot, savestate restore per arm — never a second boot):
  arm ctrl        restore m1_end, no writes, 4800f  (expect attract)
  arm latch       hold u16 @0x0EB5FC = 0xFFFF the whole window
  arm latch_late  hold from f2100 only (just before the FLAGS_WORD death)
  arm latch_sec   hold 0x0EB5FC=0xFFFF AND u16 @0x0EB5F6 (SECTION_FLAGS)
                  = 0x0009 (the M2-side sec value (11,9))

Success signature (the m2t9 anchor shape): score 3300 -> 0 with a fresh
px<100 spawn, php>0, gren 10->20, FLAGS_WORD stays 0xFF.  Any arm that
shows it = CAUSAL (write-forced M2 entry, honestly labeled as
RAM-write-forced, not natural play).  No arm shows it = a documented
negative: the gate's missing state is not (latch + section-flags) in
main RAM.
"""
import argparse
import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _REPO)

from ps1play.agent.cheatprof import CheatSession, CHEAT_ASSISTED  # noqa
from ps1play.agent.gameshark import GSCode                        # noqa
from issue4_controller import boot                                # noqa
from e2e_policy_trial import snap, DISC                           # noqa

SCRATCH = "/home/z/my-project/ps1ai/scratch/issue6_round8_msx"
LATCH = 0x0EB5FC
SECFLAGS = 0x0EB5F6
FLAGS_WORD = 0x0EE518
GRENADES = 0x0EDCF4
WINDOW_F = 4800
SAMPLE = 30


def log(*a):
    print("[probe]", *a, file=sys.stderr, flush=True)


def classify(m):
    s = snap(m)
    if s["px"] == 0.0 and s["php"] == 0:
        return ("countdown" if s["sec"] == (11, 1) and s["flags"] == 255
                and s["score"] > 0 else "scene_dark"), s
    if s["flags"] != 0xFF:
        return "scene_dark", s
    if s["sec"][0] == 0xC and 10.0 <= s["px"] <= 60.0:
        return "banner", s
    if s["score"] == 0 and 0.0 < s["px"] < 100.0 and s["php"] > 0:
        return "m2_spawn", s
    if s["px"] > 800.0:
        return "endzone", s
    return "world", s


def png(p, tag, name):
    try:
        rgb = p.core.frame_rgb()
        if rgb is not None:
            from PIL import Image
            Image.fromarray(rgb).save(
                os.path.join(SCRATCH, f"{tag}_{name}.png"))
    except Exception as e:                                  # noqa: BLE001
        log("png failed:", repr(e)[:120])


def run_arm(p, m, tag, arms, window_f=WINDOW_F):
    """One arm: restore m1_end, optional GS holds, quiet watch."""
    p.load_state("m1_end")
    for _ in range(10):
        p.core.run(1, set())
    s0 = snap(m)
    png(p, tag, f"{tag}_restore")
    log(f"{tag}: restore px={s0['px']} score={s0['score']} sec={s0['sec']}")
    session = None
    if arms:
        session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
        codes = []
        if "latch" in arms or "latch_late" in arms or "latch_sec" in arms:
            codes.append(GSCode(f"8{LATCH & 0x7FFFFFF:07X} FFFF"))
        if "latch_sec" in arms:
            codes.append(GSCode(f"8{SECFLAGS & 0x7FFFFFF:07X} 0009"))
        session.enable(f"probe_{tag}", codes)
        log(f"{tag}: DISCLOSED holds armed: {[c.raw for c in codes]}")
    evs = []
    f, spawn_f = 0, None
    late_done = "latch_late" not in arms
    while f < window_f:
        if not late_done and f >= 2100:
            session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
            session.enable(f"probe_{tag}_late",
                           [GSCode(f"8{LATCH & 0x7FFFFFF:07X} FFFF")])
            late_done = True
            log(f"{tag}: late hold armed at f={f}")
        p.core.run(SAMPLE, set())
        f += SAMPLE
        cls, s = classify(m)
        latch_v = int(m.u16(LATCH))
        fw = int(m.u32(FLAGS_WORD)) & 0xFF
        evs.append({"f": f, "cls": cls, "latch": latch_v, "fw": fw, **s})
        if cls == "m2_spawn" and spawn_f is None:
            spawn_f = f
            png(p, tag, f"{tag}_m2spawn_f{f}")
            log(f"{tag}: M2 SPAWN at f={f} px={s['px']} php={s['php']} "
                f"gren={s['gren']}")
        if f % 1200 == 0:
            png(p, tag, f"{tag}_f{f}")
    s_end = snap(m)
    png(p, tag, f"{tag}_end")
    if session is not None:
        session.disable(f"probe_{tag}")
    log(f"{tag}: end cls={classify(m)[0]} px={s_end['px']} "
        f"score={s_end['score']} fw={int(m.u32(FLAGS_WORD)) & 0xFF} "
        f"latch={int(m.u16(LATCH))}")
    return {"tag": tag, "arms": arms, "restore": s0,
            "spawn_f": spawn_f, "end": s_end, "events": evs}


def summarize(evs):
    out, cur, start, n = [], None, 0, 0
    for e in evs:
        if e["cls"] != cur:
            if cur is not None:
                out.append({"cls": cur, "f0": start, "f1": e["f"], "n": n})
            cur, start, n = e["cls"], e["f"], 1
        else:
            n += 1
    if cur is not None:
        out.append({"cls": cur, "f0": start, "f1": evs[-1]["f"], "n": n})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--arms", type=str,
                    default="ctrl,latch,latch_late,latch_sec")
    args = ap.parse_args()
    os.makedirs(SCRATCH, exist_ok=True)
    tag = f"probe{args.run}_{time.strftime('%H%M%S')}"
    want = [a.strip() for a in args.arms.split(",") if a.strip()]

    p, fw = boot()
    m = p.mem
    log(f"booted ({fw}); disc sha {sha_file(DISC) if False else 'n/a'}")

    results = {}
    for arm in want:
        r = run_arm(p, m, f"{tag}_{arm}", [arm] if arm != "ctrl" else [])
        r["timeline"] = summarize(r["events"])
        results[arm] = r
        log(f"{arm} timeline: " + "; ".join(
            f"{t['cls']} f{t['f0']}-{t['f1']}" for t in r["timeline"]))

    report = {"tag": tag, "disclosed": "GS-code constant holds (exploration)",
              "arms": {k: {"restore": v["restore"], "spawn_f": v["spawn_f"],
                           "end": v["end"], "timeline": v["timeline"]}
                       for k, v in results.items()}}
    path = os.path.join(SCRATCH, f"report_{tag}.json")
    with open(path, "w") as fh:
        json.dump(report, fh, indent=1)
    with open(os.path.join(SCRATCH, f"events_{tag}.json"), "w") as fh:
        json.dump({k: v["events"] for k, v in results.items()}, fh)
    log(f"report -> {path}")

    spawns = {k: v["spawn_f"] for k, v in results.items()
              if v["spawn_f"] is not None}
    print("SPAWNS:", spawns if spawns else "none (documented negative)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
