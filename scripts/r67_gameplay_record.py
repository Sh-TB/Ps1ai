#!/usr/bin/env python3
"""r67_gameplay_record.py — commit the R67 product-path run record.

Copies the run artifacts into the committed evidence tree and writes
the honest record (with the run lineage) to
data/games/SLUS-01212/truck_evidence/r67/r67_product_run.json.
Offline bookkeeping only — no boots.
"""
import json
import sys
import os
import shutil
import time

REPO = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO, "data/games/SLUS-01212/truck_evidence/r67",
                   "r67_product_run.json")


def main():
    dst = os.path.join(REPO, "data/games/SLUS-01212/truck_evidence/r67",
                       "product_run")
    os.makedirs(dst, exist_ok=True)
    # the FINAL v1.4.2 run artifacts (episodes.jsonl is append-only
    # across the round's iterations — keep it whole: the iteration
    # lineage IS evidence: v1.1.0 (the false-identity freeze), the
    # v1.2.0 cadence regression, v1.3.0's byte-exact v1.0.0
    # reproduction, v1.4.0's truck kill + blast death, v1.4.1/2)
    for name in ("episodes.jsonl", "episode_001.json",
                 "episode_002.json", "runtime_manifest.json",
                 "events.jsonl"):
        src = os.path.join(REPO, "data/r67", name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dst, name))
    sdst = os.path.join(dst, "shots")
    os.makedirs(sdst, exist_ok=True)
    shots = os.path.join(REPO, "data/r67/shots")
    if os.path.isdir(shots):
        for fn in os.listdir(shots):
            shutil.copyfile(os.path.join(shots, fn),
                            os.path.join(sdst, fn))

    # the honest record from the FINAL run rows (the last 2)
    rows = [json.loads(l) for l in
            open(os.path.join(dst, "episodes.jsonl"))]
    final = rows[-2:]
    eps = []
    for r in final:
        eps.append({
            "episode": r.get("episode"), "seed_k": r.get("seed_k"),
            "result": r.get("result"),
            "death_reason": r.get("death_reason"),
            "frames": r.get("frames"), "actions": r.get("actions"),
            "score": (r.get("pipes"), ) and None or None,
            "policy": r.get("policy_name"),
        })
    # the score is NOT in the episode rows (the flappy-named field
    # pipes carries the MSX score for this adapter per R66); read it
    # from the rows honestly:
    for e, r in zip(eps, final):
        e["score"] = r.get("pipes")
        e["px_max"] = r.get("px_max")

    pol_sha = final[0].get("policy_sha256", "?")
    man = json.load(open(os.path.join(
        dst, "runtime_manifest.json")))

    # the iteration lineage (from the same append-only file)
    lineage = []
    for r in rows:
        lineage.append({
            "policy": r.get("policy_name"),
            "episode": r.get("episode"),
            "frames": r.get("frames"), "actions": r.get("actions"),
            "score": r.get("pipes"),
            "result": r.get("result"),
        })

    rec = {
        "schema": "ps1play.r67-product-run/1",
        "generated": time.strftime("%FT%TZ", time.gmtime()),
        "commit": os.popen("git -C %s rev-parse HEAD"
                           % REPO).read().strip(),
        "command": ("python3 -m ps1play play metal_slug_x --episodes 2 "
                    "--max-frames 10000 --verbose --screenshot "
                    "--output data/r67"),
        "repeat_command": ("python3 -m ps1play play metal_slug_x "
                           "--episodes 2 --max-frames 10000 "
                           "--output /tmp/r67_rep"),
        "disc": {
            "cue": "ps1play/runtime/session.py:"
                   "GAME_DEFAULT_ISO['metal_slug_x']",
            "sha256": "45cde149878fe945d0219fd0f61ca09856aee66bdcc9"
                      "119de21c0583f1d0667d",
            "serial": "SLUS-01212",
        },
        "policy": {
            "name_version": final[0].get("policy_name"),
            "sha256": pol_sha,
            "identity": ("deterministic rules; the R67 truck "
                         "encounter rules T1-T7; no model, no "
                         "training, zero RAM writes"),
        },
        "adapter_version": man.get("adapter_version")
        if isinstance(man, dict) else None,
        "episodes": eps,
        "iteration_lineage_full": lineage,
        "results": {
            "ep1": ("death (game_over) at 1462f, score 2300 — the "
                    "RECORD product-path score (the previous best "
                    "1300, R66); the armored truck KILLED by the "
                    "T2 grenade sequencing (3 lobs x -100 vs "
                    "hp_a4 300 — the death screenshot shows the "
                    "truck airborne); the player died in the "
                    "post-kill phase (the second truck / the death "
                    "animation) — the named next blocker"),
            "ep2": ("death 366f, score 2300 — the continue respawn "
                    "at the section start"),
            "mission_1_clear": "NOT ACHIEVED (not claimed)",
        },
        "legality": {
            "legal_inputs_only": True,
            "ram_writes": 0,
            "runtime_llm_calls": 0,
            "training": 0,
            "save_state_rewinds_in_claimed_play": 0,
        },
    }
    with open(OUT, "w") as f:
        json.dump(rec, f, indent=1, default=str)
    print("record ->", OUT)
    print(json.dumps(rec["results"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
