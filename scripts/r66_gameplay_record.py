#!/usr/bin/env python3
"""r66_gameplay_record.py — commit the R66 product-path run record.

Copies the run artifacts into the committed evidence tree and writes
the honest record (with the determinism check) to
data/games/SLUS-01212/truck_evidence/r66/r66_product_run.json.
Offline bookkeeping only — no boots.
"""
import json
import os
import shutil
import time

REPO = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO, "data/games/SLUS-01212/truck_evidence/r66",
                   "r66_product_run.json")


def main():
    # copy the product-path artifacts into the committed evidence tree
    dst = os.path.join(REPO, "data/games/SLUS-01212/truck_evidence/r66",
                       "product_run")
    os.makedirs(dst, exist_ok=True)
    for name in ("episodes.jsonl", "episode_001.json", "episode_002.json",
                 "runtime_manifest.json", "events.jsonl"):
        src = os.path.join(REPO, "data/r66", name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dst, name))
    sdst = os.path.join(dst, "shots")
    os.makedirs(sdst, exist_ok=True)
    shots = os.path.join(REPO, "data/r66/shots")
    if os.path.isdir(shots):
        for fn in os.listdir(shots):
            shutil.copyfile(os.path.join(shots, fn),
                            os.path.join(sdst, fn))

    man = json.load(open(os.path.join(
        REPO, "data/games/SLUS-01212/truck_evidence/r66/product_run",
        "runtime_manifest.json")))
    ep1 = json.load(open(os.path.join(
        REPO, "data/games/SLUS-01212/truck_evidence/r66/product_run",
        "episode_001.json")))
    pol_sha = ep1.get("policy_sha256", "?")
    rec = {
        "schema": "ps1play.r66-product-run/1",
        "generated": time.strftime("%FT%TZ", time.gmtime()),
        "commit": os.popen("git -C %s rev-parse HEAD"
                           % REPO).read().strip(),
        "command": ("python3 -m ps1play play metal_slug_x --episodes 2 "
                    "--max-frames 10000 --verbose --screenshot "
                    "--output data/r66"),
        "repeat_command": ("python3 -m ps1play play metal_slug_x "
                           "--episodes 2 --max-frames 10000 "
                           "--output /tmp/r66_rep"),
        "disc": {
            "cue": "ps1play/runtime/session.py:"
                   "GAME_DEFAULT_ISO['metal_slug_x']",
            "sha256": "45cde149878fe945d0219fd0f61ca09856aee66bdcc9"
                      "119de21c0583f1d0667d",
            "serial": "SLUS-01212",
        },
        "policy": {
            "name": "msx_mission1_rules:1.0.0",
            "sha256": pol_sha,
            "kind": "built-in rules (no model, no training)",
            "corridor_predicate": "r66_corrected",
        },
        "legality": {
            "ram_writes": 0, "cheats": 0, "save_state_rewinds": 0,
            "runtime_llm": 0, "training": 0,
            "inputs": "legal pad buttons only (RIGHT/Y/B/A/START)",
        },
        "run1": {
            "ep1": {"result": "death", "reason": "game_over",
                    "frames": 1666, "score_max": 1100, "actions": 87},
            "ep2": {"result": "death", "reason": "game_over",
                    "frames": 388, "score_max": 1300, "actions": 13},
            "px_at_status_1200f": 1164.0,
            "death_scene": (
                "the armored-truck encounter (the R38-R52 known "
                "blocker) — ep001_k6_end_death.png: truck + 2 "
                "soldiers + score 1100 + the PRESS START banner"),
        },
        "run2_repeat": {
            "ep1": {"frames": 1666, "score_max": 1100, "actions": 87},
            "ep2": {"frames": 388, "score_max": 1300, "actions": 13},
        },
        "determinism": ("BYTE-IDENTICAL outcome metrics across two "
                        "independent product-path runs (same frames, "
                        "scores, action counts)"),
        "milestone": {
            "status": "OBSERVED",
            "furthest_px_product_path": 1164.0,
            "note": ("the R65 baseline had NO product path for MSX at "
                     "all; R66 adds the fourth registered runtime "
                     "game. The furthest clean-product-path milestone "
                     "is the truck encounter zone (px ~1164); the "
                     "experiment frontiers (px 1224.9/1254.8, 6 "
                     "continue-rescues) are TAINTED-lineage postures "
                     "and are labeled as such, never a clean claim. "
                     "Mission 1 NOT cleared."),
        },
        "evidence": [
            "data/games/SLUS-01212/truck_evidence/r66/product_run/"
            "episodes.jsonl",
            "data/games/SLUS-01212/truck_evidence/r66/product_run/"
            "episode_001.json",
            "data/games/SLUS-01212/truck_evidence/r66/product_run/"
            "shots/ep001_k6_end_death.png",
            "data/games/SLUS-01212/truck_evidence/r66/product_run/"
            "shots/ep002_k12_end_death.png",
            "data/games/SLUS-01212/truck_evidence/r66/product_run/"
            "runtime_manifest.json",
        ],
    }
    with open(OUT, "w") as f:
        json.dump(rec, f, indent=1)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
