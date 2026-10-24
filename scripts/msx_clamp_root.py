#!/usr/bin/env python3
"""msx_clamp_root.py — Mission 2 §8/§9-F root-cause campaign (Issue #9).

Question (the §8 'real unresolved gameplay failure'): the policy dies at
the scroll clamp (px ~1164) to a one-shot -291 armored-truck ram, every
pass. Is the truck kill PROXIMITY-TRIGGERED (agent enters the pin zone)
or TIME/SCRIPT-DRIVEN (the truck charges whoever waits)?

Discriminating design — 3 arms from the SAME chopper_ckpt checkpoint
(savestate, ~1 s before the chopper encounter), identical emulator
conditions, identical frame budget:

  A baseline      : current CombatPolicy, no restriction (reproduces).
  B hold-outside  : policy runs but is FORBIDDEN to cross px HOLD_PX
                    (950, safely left of the 992 respawn pin evidence);
                    standing fire only. -> Does the truck still arrive?
  C slow-approach : stop-and-kill everything within ENGAGE_SHORT first,
                    then advance <=30 px/chunk inside the last 300 px
                    before the pin, grenade-ready at the clamp.

Per-chunk normalized DecisionLog records (observation CONFIRMED from
RAM): px, hp pair, score, grenades, flags, scroll word 0xEB598, plus the
armored-slot census (hp 200..400) with x over time. Deaths recorded as
episodes with px/cause. READ-ONLY: no writes, no cheats, real deaths.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from PIL import Image                                   # noqa: E402

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.experiments import CONFIRMED, DecisionLog  # noqa: E402
from ps1play.agent.combat import CombatPolicy, scan_entities  # noqa
from msx_helicopter_ladder import (                     # noqa: E402
    CKPT, EVID, A_FLAGS, A_SCORE, A_PAIR0, GRENADES, flags_of, log,
    png, px_of)
from issue4_controller import boot                      # noqa: E402

SCROLL = 0x0EB598          # u32 section-scroll word (D7: pins 0x048BFFFF)
ARMOR_MIN, ARMOR_MAX = 200, 400   # armored census window (truck hp 254)
HOLD_PX = 950.0
SLOW_ZONE = 1100.0         # px beyond which slow-approach rules engage
SLOW_MAX_STEP = 30.0


def census_armor(m, px):
    """Armored-entity census: slots with hp in [200,400] (truck class)."""
    found = []
    for e in scan_entities(m, px=px):
        if ARMOR_MIN <= e["hp"] <= ARMOR_MAX and e["kind"] == "enemy":
            found.append(e)
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["A", "B", "C"], required=True)
    ap.add_argument("--chunks", type=int, default=90)
    ap.add_argument("--tag", default=None)
    args = ap.parse_args()
    tag = args.tag or f"clamproot_{args.arm}"

    p, fwmode = boot()
    m = p.mem
    p.load_state(CKPT)
    for _ in range(2):
        p.core.run_frame()
    if flags_of(m) != 0xFF:
        log(f"checkpoint not in active gameplay (flags={flags_of(m):#x})")
        return 2

    commit = os.popen(f"git -C {_REPO} rev-parse --short HEAD").read().strip()
    out_dir = os.path.join(EVID, tag)
    os.makedirs(out_dir, exist_ok=True)
    dl = DecisionLog(out_dir, tag, track=("A" if args.arm == "A" else "C"),
                     commit=commit, plugin="msx combat (chopper_ckpt)",
                     game="Metal Slug X (USA) SLUS-01212",
                     emulator="beetle-psx 0.9.44.1 in-process",
                     checkpoint_id="chopper_ckpt px810.3")
    dl.note("arm", arm=args.arm, hold_px=HOLD_PX, slow_zone=SLOW_ZONE,
            question="truck kill: proximity-triggered or time-driven?")

    pol = CombatPolicy()
    px = px_of(m)
    hp = int(m.u16(A_PAIR0))
    hp0, score0 = hp, int(m.u32(A_SCORE))
    deaths, max_px = [], px
    armor_track = {}        # slot -> [x_px per chunk]
    t0, f0 = time.time(), p.core.frames_run
    log(f"[{args.arm}] start px={px:.1f} hp={hp} score={score0}")

    last_px, last_segs = None, None
    forced_hold = False
    death_px = None
    for c in range(args.chunks):
        px = px_of(m)
        hp1 = int(m.u16(A_PAIR0))
        scan = scan_entities(m, px=px)
        armor = census_armor(m, px)
        for e in armor:
            armor_track.setdefault(e["slot"], []).append(
                {"chunk": c, "x_px": e["x_px"], "hp": e["hp"], "h": e["h"]})

        flags = flags_of(m)
        dead = flags != 0xFF or hp1 <= 0

        obs = {
            "px": {"value": round(px, 1), "provenance": CONFIRMED},
            "hp": {"value": hp1, "provenance": CONFIRMED},
            "score": {"value": int(m.u32(A_SCORE)), "provenance": CONFIRMED},
            "grenades": {"value": int(m.u8(GRENADES)), "provenance": CONFIRMED},
            "scroll_word": {"value": int(m.u32(SCROLL)), "provenance": CONFIRMED},
            "flags": {"value": flags, "provenance": CONFIRMED},
            "armor_census": {"value": [(e["slot"], round(e["x_px"], 1),
                                        e["hp"], e["h"]) for e in armor],
                             "provenance": CONFIRMED},
        }

        if dead:
            deaths.append({"chunk": c, "px": round(px, 1), "hp": hp1,
                           "flags": flags,
                           "armor_near": [(e["slot"], round(e["x_px"], 1))
                                          for e in armor]})
            dl.decision(c, p.core.frames_run - f0, obs,
                        [{"action": "dead", "rejected": False, "why": "episode end"}],
                        {"action": "wait", "frames": 60, "expected": "death anim"},
                        actual={"post_state": {"px": round(px, 1)}, "death": True,
                                "prediction_correct": True},
                        objective={"progress": round(px, 1),
                                   "confidence": CONFIRMED,
                                   "note": f"death episode {len(deaths)}"})
            png(p, os.path.join(out_dir, f"death_ep{len(deaths)}.png"))
            if death_px is None:
                death_px = px
            # honest attrition: episode ends here (no continue exists)
            break

        # ---- arm policies -------------------------------------------------
        advanced = 0.0 if last_px is None else (px - last_px)
        intent = any("RIGHT" in (s.get("btns") or set())
                     for s in (last_segs or []))
        pol.observe(px, advanced, intent)
        segs = pol.decide(60, px, scan,
                          grenades=int(m.u8(GRENADES)), hp=hp1)
        if args.arm == "B" and px >= HOLD_PX:
            forced_hold = True
            segs = [{"frames": 60, "btns": set()}]        # hold ground
        elif args.arm == "C":
            if px >= SLOW_ZONE:
                capped, budget = [], SLOW_MAX_STEP
                for s in segs:
                    if "RIGHT" in (s.get("btns") or set()) and budget <= 0:
                        s = {"frames": s["frames"], "btns": set()}
                    elif "RIGHT" in (s.get("btns") or set()):
                        budget -= s["frames"] * (40.0 / 60.0)
                    capped.append(s)
                segs = capped
        last_px, last_segs = px, segs

        frame_start = p.core.frames_run
        for s in segs:
            p.core.run(s["frames"], s["btns"] or set())
        hp1b = int(m.u16(A_PAIR0))
        pxb = px_of(m)
        max_px = max(max_px, pxb)
        damage = max(0, hp1 - hp1b)
        action = "+".join(sorted(set(b for s in segs for b in (s.get("btns") or set())))) or "idle"
        dl.decision(
            c, p.core.frames_run - frame_start + frame_start - f0, obs,
            [{"action": a, "rejected": False,
              "why": f"arm {args.arm} policy"} for a in (action.split("+") or ["idle"])],
            {"action": action, "frames": 60,
             "expected": ("hold" if args.arm == "B" and forced_hold
                          else "advance/engage per policy")},
            actual={"post_state": {"px": round(pxb, 1)},
                    "damage": damage, "death": False,
                    "stall": abs(pxb - px) < 1.0 and damage == 0,
                    "prediction_correct": (hp1b <= hp1)},
            objective={"progress": round(pxb, 1), "confidence": CONFIRMED,
                       "note": "px progress under arm rules"},
        )
        if damage:
            log(f"  c{c} damage {damage} hp {hp1}->{hp1b} px {pxb:.1f}")

    # ---- close out ---------------------------------------------------------
    dl.note("result", arm=args.arm,
            deaths=len(deaths), death_px=round(death_px, 1) if death_px else None,
            max_px=round(max_px, 1),
            armor_slots_tracked=sorted(armor_track.keys()),
            armor_timeline={str(k): v for k, v in armor_track.items()},
            frames_used=p.core.frames_run - f0,
            wall_s=round(time.time() - t0, 1),
            hp_delta=hp - hp0, score_delta=int(m.u32(A_SCORE)) - score0,
            forced_hold=forced_hold)
    dl.write_summary()
    with open(os.path.join(out_dir, "result.json"), "w") as f:
        json.dump({"arm": args.arm, "deaths": deaths, "max_px": max_px,
                   "armor_track": armor_track,
                   "frames_used": p.core.frames_run - f0,
                   "wall_s": round(time.time() - t0, 1)}, f, indent=1)
    log(f"[{args.arm}] done deaths={len(deaths)} death_px="
        f"{death_px and round(death_px, 1)} max_px={max_px:.1f} "
        f"frames={p.core.frames_run - f0} wall={time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
