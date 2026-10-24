#!/usr/bin/env python3
"""pincorr1 — live validation of the instrument-pin policy wiring.

The sectioncorr1 run correlated scan_section() with the D7 pin
(read-only sensor, policy unchanged). This run executes the SAME
scenario with the NEW observe_section() wiring active:

  pin signature (state 0xA x2) must engage clamp_clear IMMEDIATELY
  (attribution: section_pinned=True with clamp_streak<2), one chunk
  before the derived px-stall streak can, and must survive the c28
  transient pattern.

Per chunk the decisions ledger records: px, hp, score, section
(state/flags), the policy mode, section_pinned, clamp_streak ->
instrument-vs-derived attribution is derivable from the artifact.

Evidence: download/mission2_section_pin/<tag>/result.json (+ JSONL).
Local-only run (savestate chopper_ckpt is never committed).
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
from msx_helicopter_ladder import CKPT, A_PAIR0, A_SCORE, GRENADES, flags_of, log, px_of  # noqa
from issue4_controller import boot  # noqa

SCROLL = 0x0EB598


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=40)
    ap.add_argument("--tag", default="pincorr1")
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

    out_dir = os.path.join(_REPO, "download", "mission2_section_pin", tag)
    os.makedirs(out_dir, exist_ok=True)

    pol = CombatPolicy()
    px = px_of(m)
    last_px = None
    rows = []
    death = None
    first_instrument = None       # first chunk clamp_clear via instrument
    first_derived = None          # first chunk clamp_clear via derived
    t0, f0 = time.time(), p.core.frames_run
    log(f"[{tag}] start px={px:.1f}")

    for c in range(args.chunks):
        px = px_of(m)
        hp1 = int(m.u16(A_PAIR0))
        scan = scan_entities(m, px=px)
        sec = scan_section(m)
        row = {
            "chunk": c, "px": round(px, 1), "hp": hp1,
            "score": int(m.u32(A_SCORE)),
            "scroll": int(m.u32(SCROLL)),
            "sec_state": sec["state"], "sec_flags": sec["flags"],
            "mode_before": pol.mode,
            "section_pinned": pol.section_pinned,
            "clamp_streak": pol.clamp_streak,
        }
        flags = flags_of(m)
        if flags != 0xFF or hp1 <= 0:
            death = {"chunk": c, "px": round(px, 1), "hp": hp1,
                     "flags": flags}
            row["death"] = True
            rows.append(row)
            break

        advanced = 0.0 if last_px is None else (px - last_px)
        pol.observe(px, advanced, True)
        pol.observe_section(sec)
        segs = pol.decide(60, px, scan,
                          grenades=int(m.u8(GRENADES)), hp=hp1)
        row["mode"] = pol.mode
        row["section_pinned"] = pol.section_pinned
        row["clamp_streak"] = pol.clamp_streak
        rows.append(row)
        print(json.dumps(row))
        if (pol.mode == "clamp_clear" and pol.section_pinned
                and first_instrument is None):
            first_instrument = c
        if (pol.mode == "clamp_clear" and not pol.section_pinned
                and pol.clamp_streak >= 2 and first_derived is None):
            first_derived = c
        last_px = px
        for s in segs:
            p.core.run(s["frames"], s["btns"] or set())

    pin_chunks = [r["chunk"] for r in rows
                  if r.get("sec_state") == 0xA]
    result = {
        "tag": tag,
        "commit": os.popen(f"git -C {_REPO} rev-parse --short HEAD").read().strip(),
        "checkpoint": "chopper_ckpt px810.3",
        "chunks_requested": args.chunks,
        "chunks_run": len(rows),
        "frames": p.core.frames_run - f0,
        "wall_s": round(time.time() - t0, 1),
        "death": death,
        "first_clamp_clear_instrument": first_instrument,
        "first_clamp_clear_derived": first_derived,
        "pin_state_chunks": pin_chunks,
        "stats": pol.stats,
        "timeline": rows,
        "wiring": ("observe_section() -> CombatPolicy.section_pinned; "
                   "signature = section walker state 0xA (2-consecutive "
                   "confirm, transients ignored); clamped = derived "
                   "streak>=2 OR instrument pin"),
    }
    with open(os.path.join(out_dir, "result.json"), "w") as f:
        json.dump(result, f, indent=1)
    log(f"[{tag}] done chunks={len(rows)} death={death} "
        f"instrument@{first_instrument} derived@{first_derived} "
        f"stats={ {k: v for k, v in pol.stats.items() if v} }")
    return 0


if __name__ == "__main__":
    sys.exit(main())
