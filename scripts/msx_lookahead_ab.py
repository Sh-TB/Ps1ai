#!/usr/bin/env python3
"""msx_lookahead_ab.py — Mission 2 §5/§6 (Deliverable D): the jev-style
shadow-lookahead + predicted-death filter, A/B tested from the SAME
checkpoint through the normalized harness.

Track A (algorithm-off): CombatPolicy decides; segments commit directly.
Track D (combined): the same CombatPolicy plan is SIMULATED first
(savestate -> run -> evaluate); if the prediction is fatal/very costly,
alternatives are tried in order and the least-damage plan commits.

Mechanism provenance (jev-game-agent, mechanisms only — no code copied,
that repo has no license and a paid API we do not use):
  - shadow-emulator lookahead with RAM fingerprints (lookahead.py:56-133)
  - predicted-death eligibility gate (lookahead.py:18-20,124-125)
  - bounded factual death episodes (death_memory.py:15-108)

Both tracks: identical checkpoint, emulator conditions, chunk budget.
The harness records every decision; scorecard.compare_runs() produces
the §5 verdict. Read-only gameplay: real deaths, no cheats.
"""
from __future__ import annotations

import argparse
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

LOOKAHEAD_DAMAGE_GATE = 24   # predicted hp loss >= this -> try alternatives
LOOKAHEAD_ALT_FRAMES = 60


def _snapshot_state(p, m):
    return {"px": round(px_of(m), 1), "hp": int(m.u16(A_PAIR0)),
            "score": int(m.u32(A_SCORE)),
            "flags": flags_of(m)}


def run_track(p, m, track, chunks, dl):
    """One controlled pass. track: 'A' (commit) or 'D' (lookahead)."""
    pol = CombatPolicy()
    f0 = p.core.frames_run
    t0 = time.time()
    hp0 = int(m.u16(A_PAIR0))
    score0 = int(m.u32(A_SCORE))
    deaths = 0
    max_px = px_of(m)
    la_stats = {"simulated": 0, "rejections": 0, "accepted_alt": 0,
                "predictions_correct": 0, "predictions_wrong": 0}
    ckpt_seq = 0

    last_px, last_segs = None, None
    for c in range(chunks):
        px = px_of(m)
        hp = int(m.u16(A_PAIR0))
        flags = flags_of(m)
        if flags != 0xFF or hp <= 0:
            dl.decision(c, p.core.frames_run - f0,
                        {"px": {"value": round(px, 1), "provenance": CONFIRMED},
                         "hp": {"value": hp, "provenance": CONFIRMED},
                         "flags": {"value": flags, "provenance": CONFIRMED}},
                        [{"action": "dead", "rejected": False, "why": "episode end"}],
                        {"action": "wait", "frames": 60, "expected": "death"},
                        actual={"post_state": {"px": round(px, 1)}, "death": True,
                                "prediction_correct": True},
                        objective={"progress": round(px, 1),
                                   "confidence": CONFIRMED,
                                   "note": f"death episode {deaths + 1}"})
            deaths += 1
            png(p, os.path.join(EVID, f"lookahead_{track}",
                                f"death_ep{deaths}.png")
                if os.path.isdir(os.path.join(EVID, f"lookahead_{track}"))
                else None) if False else None
            break

        scan = scan_entities(m, px=px)
        advanced = 0.0 if last_px is None else (px - last_px)
        intent = any("RIGHT" in (s.get("btns") or set())
                     for s in (last_segs or []))
        pol.observe(px, advanced, intent)
        segs = pol.decide(60, px, scan,
                          grenades=int(m.u8(GRENADES)), hp=hp)
        last_px, last_segs = px, segs
        action = "+".join(sorted(set(
            b for s in segs for b in (s.get("btns") or set())))) or "idle"

        committed = segs
        la = None
        if track == "D":
            # ---- shadow lookahead (mechanisms-only jev port) --------
            ckpt_seq += 1
            cpath = os.path.join(EVID, f"lookahead_D", f"probe_{ckpt_seq % 4}")
            p.save_state(cpath)
            s0 = _snapshot_state(p, m)
            for s in segs:
                p.core.run(s["frames"], s["btns"] or set())
            s1 = _snapshot_state(p, m)
            pred_damage = s0["hp"] - s1["hp"]
            pred_death = s1["flags"] != 0xFF or s1["hp"] <= 0
            la_stats["simulated"] += 1
            if pred_death or pred_damage >= LOOKAHEAD_DAMAGE_GATE:
                la_stats["rejections"] += 1
                # alternatives: hold+aimed-fire; then retreat-fire
                alts = [
                    ("hold_fire", [{"frames": 4,
                                    "btns": {"RIGHT"} if True else set()},
                                   {"frames": 26, "btns": {"Y"}},
                                   {"frames": 30, "btns": set()}]),
                    ("retreat_fire", [{"frames": 10, "btns": {"LEFT"}},
                                      {"frames": 24, "btns": {"LEFT", "Y"}},
                                      {"frames": 26, "btns": set()}]),
                ]
                for alt_name, alt_segs in alts:
                    p.load_state(cpath)
                    for s in alt_segs:
                        p.core.run(s["frames"], s["btns"] or set())
                    s2 = _snapshot_state(p, m)
                    alt_damage = s0["hp"] - s2["hp"]
                    alt_death = s2["flags"] != 0xFF or s2["hp"] <= 0
                    if not alt_death and alt_damage < max(1, pred_damage):
                        la_stats["accepted_alt"] += 1
                        committed, la = alt_segs, {
                            "rejected_plan": action,
                            "predicted_damage": pred_damage,
                            "predicted_death": pred_death,
                            "alt": alt_name,
                            "alt_damage": alt_damage}
                        break
                else:
                    p.load_state(cpath)          # keep the plan anyway
                    la = {"rejected_plan": None,
                          "predicted_damage": pred_damage,
                          "predicted_death": pred_death,
                          "kept_plan_despite_cost": True}
            else:
                p.load_state(cpath)
                la = {"predicted_damage": pred_damage,
                      "predicted_death": pred_death}
            # prediction quality bookkeeping (verified post-commit below)

        # commit the winning plan for real
        frame_start = p.core.frames_run
        for s in committed:
            p.core.run(s["frames"], s["btns"] or set())
        hp1 = int(m.u16(A_PAIR0))
        px1 = px_of(m)
        max_px = max(max_px, px1)
        damage = max(0, hp - hp1)
        actual_death = flags_of(m) != 0xFF or hp1 <= 0
        if la is not None and "predicted_damage" in la:
            ok = ((la.get("predicted_death") or False) == actual_death
                  and abs(la["predicted_damage"] - damage) <= 12)
            la_stats["predictions_correct" if ok else "predictions_wrong"] += 1
        dl.decision(
            c, p.core.frames_run - f0,
            {"px": {"value": round(px, 1), "provenance": CONFIRMED},
             "hp": {"value": hp, "provenance": CONFIRMED},
             "score": {"value": int(m.u32(A_SCORE)), "provenance": CONFIRMED},
             "near_threat": {"value": (scan[0]["slot"], scan[0]["hp"],
                                       scan[0]["dx_px"]) if scan else None,
                             "provenance": CONFIRMED}},
            ([{"action": action, "rejected": False, "why": "policy plan"}]
             + ([{"action": la["alt"], "rejected": False,
                  "why": f"lookahead: plan predicted {la['predicted_damage']} dmg"}]
                if la and la.get("alt") else [])
             + ([{"action": la["rejected_plan"], "rejected": True,
                  "why": f"predicted damage {la['predicted_damage']}"
                         + (" death" if la.get("predicted_death") else "")}]
                if la and la.get("rejected_plan") else [])),
            {"action": "+".join(sorted(set(
                b for s in committed for b in (s.get("btns") or set()))))
                or "idle",
             "frames": sum(s["frames"] for s in committed),
             "expected": "policy plan (simulated)" if track == "D"
                         else "policy plan"},
            actual={"post_state": {"px": round(px1, 1)},
                    "damage": damage, "death": actual_death,
                    "stall": abs(px1 - px) < 1.0 and damage == 0,
                    "recovery": None,
                    "prediction_correct": None},
            objective={"progress": round(px1, 1), "confidence": CONFIRMED,
                       "note": "px progress"},
            evidence=[{"lookahead": la}] if la else [],
        )
        if damage:
            log(f"  [{track}] c{c} dmg {damage} hp {hp}->{hp1} px {px1:.1f}")

    dl.note("result", track=track, deaths=deaths, max_px=round(max_px, 1),
            hp_delta=int(m.u16(A_PAIR0)) - hp0,
            score_delta=int(m.u32(A_SCORE)) - score0,
            frames_used=p.core.frames_run - f0,
            wall_s=round(time.time() - t0, 1), **la_stats)
    dl.write_summary()
    log(f"[{track}] done deaths={deaths} max_px={max_px:.1f} "
        f"frames={p.core.frames_run - f0} la={la_stats}")
    return deaths, max_px


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=80)
    ap.add_argument("--tag", default="lookahead_ab")
    args = ap.parse_args()

    p, fwmode = boot()
    m = p.mem
    commit = os.popen(f"git -C {_REPO} rev-parse --short HEAD").read().strip()
    out = {}
    for track in ("A", "D"):
        p.load_state(CKPT)
        for _ in range(2):
            p.core.run_frame()
        if flags_of(m) != 0xFF:
            log("checkpoint not in active gameplay — aborting")
            return 2
        dl = DecisionLog(os.path.join(EVID, f"lookahead_{track}"),
                         f"{args.tag}_{track}", track=track, commit=commit,
                         plugin="msx combat (chopper_ckpt)",
                         game="Metal Slug X (USA) SLUS-01212",
                         emulator="beetle-psx 0.9.44.1 in-process",
                         checkpoint_id="chopper_ckpt px810.3")
        dl.note("boot", track=track, lookahead=track == "D",
                damage_gate=LOOKAHEAD_DAMAGE_GATE)
        deaths, max_px = run_track(p, m, track, args.chunks, dl)
        out[track] = {"deaths": deaths, "max_px": round(max_px, 1)}
    log("A/B:", json.dumps(out) if (json := __import__("json")) else out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
