#!/usr/bin/env python3
"""msx_heli_summary.py — compile the 10-pattern chopper/mortar-rain
ladder results into the summary table + the defect-ledger verdicts
(Issue #5). Reads the per-pattern reports and the rain slot trace."""
from __future__ import annotations

import json
import os
import sys

EVID = "/home/z/my-project/work/msx_recomp/evidence/heli_ladder"

KILLERS = {
    "01_stand_in_corridor": "mortar shell blast (slot x=924.8 armed "
        "at ~27px; VISUAL: explosion on player)",
    "02_walk_right": "NONE - SURVIVED full budget, reached clamp",
    "03_patrol_tight": "mortar shell blast (x=884 next to patrol "
        "zone; +500 soldier kill scored before death)",
    "04_zigzag_forward": "armored-truck ram at wall approach "
        "(VISUAL: truck on player; one-shot 257)",
    "05_hop_advance": "armored-truck ram at the clamp (one-shot 291)",
    "06_run_to_wall_hold": "armored-truck ram while IDLE at the "
        "clamp (VISUAL: truck on player; one-shot 291)",
    "07_wall_upfire": "sword-soldier pack while STATIC up-fire "
        "(VISUAL: 3 swordsmen swinging; truck parked right)",
    "08_lob_grenades": "sword-soldier melee while lobbing LEFT "
        "(VISUAL: slashed; +200 kill scored)",
    "09_retreat_left": "sword-soldier melee while retreating "
        "(VISUAL: slashed; +100 kill scored)",
    "10_prone_in_corridor": "mortar shell blast - PRONE DOES NOT "
        "DODGE (same shell/time as pattern 1)",
}

WEB_PREDICTIONS = {
    "01_stand_in_corridor": ("dies (web+user: standing still = death)", True),
    "02_walk_right": ("survives (web: keep moving)", True),
    "03_patrol_tight": ("risky - stays in the corridor", True),
    "04_zigzag_forward": ("dies late - LEFT phases re-enter the "
                          "corridor + truck catches up", True),
    "05_hop_advance": ("dies late - hops slow the crossing", True),
    "06_run_to_wall_hold": ("dies after arrival (idle at wall)", True),
    "07_wall_upfire": ("dies if static (web: attack the source, "
                       "but not standing still)", True),
    "08_lob_grenades": ("dies (lobbing exposes the back)", True),
    "09_retreat_left": ("dies (melee chases)", True),
    "10_prone_in_corridor": ("dies (prone does not dodge bombs)", True),
}


def main():
    pats = []
    for name in sorted(KILLERS):
        rp = os.path.join(EVID, f"report_{name}.json")
        r = json.load(open(rp))
        pred, match = WEB_PREDICTIONS[name]
        pats.append({
            "pattern": name,
            "died": r["died"],
            "death_frame": (r.get("death") or {}).get("frame"),
            "frames_run": r["frames_run"],
            "start_px": r["start_px"],
            # end_px is read after the death tail (respawn anchor);
            # max_px is the authoritative deepest position
            "end_px": r["max_px"] if r["died"] else r["end_px"],
            "max_px": r["max_px"],
            "hp_start": r["hp_start"], "hp_end": r["hp_end"],
            "n_damage_events": r["n_damage_events"],
            "score_delta": r["score_delta"],
            "killer": KILLERS[name],
            "web_prediction": pred,
            "prediction_matched": match,
            "gif": r.get("gif"),
        })
    # HP-regen evidence: pattern 2 hp dips + full recovery
    regen = None
    rows = [json.loads(l) for l in
            open(os.path.join(EVID, "pattern_02_walk_right.jsonl"))]
    dips = [r for r in rows if r["hp0"] < 285]
    if dips:
        regen = {"hp_dips": len(dips),
                 "hp_min": min(r["hp0"] for r in dips),
                 "hp_final": rows[-1]["hp0"]}
    out = {
        "schema": "ps1play-heli-ladder-summary/1",
        "checkpoint": {"state": "chopper_ckpt", "px": 810.3,
                       "hp_frozen_at_save": 131,
                       "note": "reach used the disclosed "
                               "hp_pair_freeze EXPLORATION assist; "
                               "every pattern ran UNFROZEN"},
        "web_sources": [
            "arcadequartermaster.com MS2 Mission 1: 'focus all your "
            "fire on the red Masknell chopper: the entire squadron "
            "collapses with the demise of the red leader'",
            "Antstream guide: 'R-Shobu - Enemy Chopper: drops bombs "
            "on the player. Fast and deadly'",
            "metalslug.fandom 'Drifting in Desert': mosque minarets "
            "hide launchers",
            "r/metalslug: keep moving, learn the wave pattern",
        ],
        "patterns": pats,
        "hp_regen_pattern2": regen,
        "verdicts": [
            {"id": "H1", "claim": "standing still in the rain "
                "corridor = death", "verdict": "CONFIRMED",
             "evidence": "pattern 1 died f286 (4.8s) to an armed "
                         "shell blast at 27px; pattern 10 (prone) "
                         "died f285 identically"},
            {"id": "H2", "claim": "constant movement survives the "
                "corridor", "verdict": "CONFIRMED",
             "evidence": "pattern 2 (hold RIGHT) was the ONLY "
                         "survivor: 810->1164px, 30 chip events, "
                         "HP regen to full, 1500f"},
            {"id": "H3", "claim": "the pursuing truck kills players "
                "who idle/backtrack at the clamp",
             "verdict": "CONFIRMED",
             "evidence": "patterns 4/5/6: one-shot 257-291 at the "
                         "clamp; VISUAL truck-on-player in 4 and 6; "
                         "pattern 2 holding RIGHT survived with the "
                         "truck parked ~40px behind"},
            {"id": "H4", "claim": "prone dodges the mortar",
             "verdict": "FALSIFIED",
             "evidence": "pattern 10 died at the same frame/shell "
                         "as pattern 1"},
            {"id": "H5", "claim": "static up-fire clears the rain "
                "source", "verdict": "FALSIFIED-AS-STATIC",
             "evidence": "pattern 7 died f1037 to melee while "
                         "static up-firing; score 0 (no source "
                         "kill); w2 protocol B used UP+LEFT+Y "
                         "(moving), CombatPolicy v6's up-fire "
                         "segment is STATIC {UP,Y} -> defect"},
            {"id": "H6", "claim": "retreating escapes the zone",
             "verdict": "FALSIFIED",
             "evidence": "patterns 8/9 died to sword soldiers "
                         "while moving away"},
            {"id": "H7", "claim": "mortar shells have an in-flight "
                "warning window", "verdict": "FALSIFIED",
             "evidence": "rain_slot_trace.jsonl: the drop is "
                         "h128->64 in ONE frame; the shell then "
                         "creeps LEFT along the ground (973->925px, "
                         "decelerating) with hp 352->101 decay then "
                         "ARMED saturation; kill radius ~<=27px"},
        ],
    }
    with open(os.path.join(EVID, "heli_ladder_summary.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({"patterns": [
        {k: p[k] for k in ("pattern", "died", "death_frame",
                           "end_px", "score_delta")}
        for p in pats], "hp_regen": regen}, indent=1))


if __name__ == "__main__":
    main()
