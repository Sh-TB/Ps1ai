#!/usr/bin/env python3
"""Live correlation run for the section-walker sensor (Issue #9 debugger dive).

Question: which section-walker state/flags values coincide with the D7 clamp
(pin at px ~992 / camera lock) and its release?

Runs the baseline combat policy from chopper_ckpt (px 810.3) and logs per
chunk: px, hp, scroll word, and the NEW scan_section() readings
(state 0x0EB5F4, flags 0x0EB5D0, progress 0x0EB5D4). Read-only sensor run —
no policy changes; the walk is the same arm-A behaviour as msx_clamp_root.

Evidence: download/mission2_section_correlate/<tag>/result.json + decisions JSONL.
"""
import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.agent.combat import CombatPolicy, scan_entities, scan_section  # noqa
from msx_helicopter_ladder import CKPT, EVID, A_FLAGS, A_PAIR0, A_SCORE, GRENADES, flags_of, log, png, px_of  # noqa
from issue4_controller import boot  # noqa

SCROLL = 0x0EB598


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=34)
    ap.add_argument("--tag", default="sectioncorr")
    args = ap.parse_args()
    tag = args.tag

    p, _fwmode = boot()
    m = p.mem
    p.load_state(CKPT)
    for _ in range(2):
        p.core.run_frame()
    if flags_of(m) != 0xFF:
        log(f"checkpoint not in active gameplay (flags={flags_of(m):#x})")
        return 2

    out_dir = os.path.join("/home/z/my-project/ps1ai/download",
                           "mission2_section_correlate", tag)
    os.makedirs(out_dir, exist_ok=True)

    pol = CombatPolicy()
    px = px_of(m)
    last_px = None
    timeline = []
    death = None
    t0, f0 = time.time(), p.core.frames_run
    log(f"[{tag}] start px={px:.1f}")

    for c in range(args.chunks):
        px = px_of(m)
        hp1 = int(m.u16(A_PAIR0))
        scan = scan_entities(m, px=px)
        sec = scan_section(m)
        row = {
            "chunk": c,
            "px": round(px, 1),
            "hp": hp1,
            "score": int(m.u32(A_SCORE)),
            "scroll": int(m.u32(SCROLL)),
            "section_state": sec["state"],
            "section_flags": sec["flags"],
            "section_progress": sec["progress"],
            "section_complete": sec["complete"],
            "n_entities": len(scan),
            "entities": [(e["slot"], round(e["x_px"], 1), e["hp"], e["h"],
                          e["kind"]) for e in scan[:6]],
        }
        timeline.append(row)
        print(json.dumps(row))

        flags = flags_of(m)
        if flags != 0xFF or hp1 <= 0:
            death = {"chunk": c, "px": round(px, 1), "hp": hp1, "flags": flags}
            png(p, os.path.join(out_dir, "death.png"))
            break

        advanced = 0.0 if last_px is None else (px - last_px)
        pol.observe(px, advanced, True)
        segs = pol.decide(60, px, scan,
                          grenades=int(m.u8(GRENADES)), hp=hp1)
        last_px = px
        for s in segs:
            p.core.run(s["frames"], s["btns"] or set())

    result = {
        "tag": tag,
        "commit": os.popen(f"git -C {_REPO} rev-parse --short HEAD").read().strip(),
        "checkpoint": "chopper_ckpt px810.3",
        "chunks_requested": args.chunks,
        "chunks_run": len(timeline),
        "wall_s": round(time.time() - t0, 1),
        "frames": p.core.frames_run - f0,
        "death": death,
        "timeline": timeline,
        "sensor_provenance": ("scan_section: state 0x0EB5F4 / flags 0x0EB5D0 / "
                              "progress 0x0EB5D4 — Ghidra FUN_80021898 decompile, "
                              "semantics OBSERVED-from-static; this run correlates "
                              "them live with the D7 clamp (read-only)"),
    }
    with open(os.path.join(out_dir, "result.json"), "w") as f:
        json.dump(result, f, indent=1)
    log(f"[{tag}] done chunks={len(timeline)} death={death} "
        f"wall={result['wall_s']}s")

    # compact state/flags summary
    states = {}
    for r in timeline:
        key = (r["section_state"], r["section_flags"])
        states.setdefault(key, []).append(
            {"chunk": r["chunk"], "px": r["px"],
             "progress": r["section_progress"]})
    print("\n--- section walker summary (state, flags) -> chunks ---")
    for key, rows in sorted(states.items()):
        pxs = [r["px"] for r in rows]
        print(f"state={key[0]:#06x} flags={key[1]:#06x}: chunks "
              f"{rows[0]['chunk']}..{rows[-1]['chunk']} px "
              f"{min(pxs)}..{max(pxs)} progress {rows[0]['progress']}"
              f".." f"{rows[-1]['progress']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
