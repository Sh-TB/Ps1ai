#!/usr/bin/env python3
"""r68_gameplay_record.py — commit the R68 product-path run record.

Copies the FINAL (v1.6.2) run artifacts into the committed evidence
tree and writes the honest record (with the full iteration lineage)
to data/games/SLUS-01212/truck_evidence/r68/r68_product_run.json.
Offline bookkeeping only — no boots.

THE ITERATION LINEAGE (each step probe-pinned; the intermediate
probe artifacts were overwritten in place by the fixed-path probe —
disclosed; the pinned numbers + the surviving artifacts carry the
evidence):

  v1.5.0  W8/W9 (the kill transition + the hazard retreat).  The
          product run reproduced the R67 v1.4.2 ep1 trace
          BYTE-IDENTICAL (1462f / 2300 / 91 acts, the same
          trace_sha256 0afe95b2...) — the W8/W9 chain never fired:
          the truck NEVER left the observation (it never died).
  v1.6.0  T2' the unlimited lob budget + T6' the chase.  ep1
          1318f / 2800 = the score RECORD (prior best 2300).  The
          probe: the lobs LANDED in the band (dx -133.5, px 1071):
          a4 300 -> 230 -> 110 -> 100 -> 80, then FROZE at 80 when
          the truck crossed the band edge (-135.4) and the chase
          walked against the scroll (px 1071 -> 1105.8 while
          pressing BACK) — the band window closed.
  v1.6.1  T6' the stand-ground chip-fire (the R38 sustained-fire
          model, |dx| <= 220).  ep1 1218f / 1400 = a REGRESSION.
          The probe: the a4 sat at 300 FROZEN through five 12f chip
          windows — the bullets DO NOT reach a truck behind the pin
          (the wave soldiers + the pin scenery eat the shot).  The
          v1.6.1 artifact survives:
          r68_postkill_probe_v161_chipstand.jsonl.
  v1.6.2  T6' the chase restored + the R38 gre40 cadence
          (TRUCK_GRENADE_CD=40).  ep1 1318f / 2800 (the record
          tied) — the same band window and the same a4 floor: the
          CONNECT RATE (~1/10, the R38 chopper evidence) is the
          named R69 blocker, not the cadence.

THE R67 CORRECTION (probe-pinned, the honest-registry law): the R67
"THE ARMORED TRUCK KILLED ON THE PRODUCT PATH (score 2300)" reading
is REFUTED — the truck row sat at a4=160 (0x9E88, x 937.5, slot 14)
from f1160 to the v1.4.2 death at f1462; the score 2300 came from
the wave kills + chip events; the truck was NEVER killed on the
product path.  The R67 report's "truck AIRBORNE" death-shot reading
is likewise corrected (the airborne object in the shot is the
encounter's follower, not the truck's death animation).
"""
import json
import sys
import os
import shutil
import time

REPO = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO, "data/games/SLUS-01212/truck_evidence/r68",
                   "r68_product_run.json")


def main():
    dst = os.path.join(REPO, "data/games/SLUS-01212/truck_evidence/r68",
                       "product_run")
    os.makedirs(dst, exist_ok=True)
    for name in ("episodes.jsonl", "episode_001.json",
                 "episode_002.json", "runtime_manifest.json",
                 "events.jsonl"):
        src = os.path.join(REPO, "data/r68", name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dst, name))
    sdst = os.path.join(dst, "shots")
    os.makedirs(sdst, exist_ok=True)
    shots = os.path.join(REPO, "data/r68/shots")
    if os.path.isdir(shots):
        for fn in os.listdir(shots):
            shutil.copyfile(os.path.join(shots, fn),
                            os.path.join(sdst, fn))

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
            "score": r.get("pipes"), "px_max": r.get("px_max"),
            "policy": r.get("policy_name"),
        })
    pol_sha = final[0].get("policy_sha256", "?")
    man = json.load(open(os.path.join(
        dst, "runtime_manifest.json")))

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
        "schema": "ps1play.r68-product-run/1",
        "generated": time.strftime("%FT%TZ", time.gmtime()),
        "commit": os.popen("git -C %s rev-parse HEAD"
                           % REPO).read().strip(),
        "command": ("python3 -m ps1play play metal_slug_x --episodes 2 "
                    "--max-frames 12000 --verbose --screenshot "
                    "--output data/r68"),
        "repeat_command": ("python3 -m ps1play play metal_slug_x "
                           "--episodes 2 --max-frames 12000 "
                           "--output /tmp/r68_rep"),
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
            "identity": ("deterministic rules; the R68 truck rules "
                         "T2'/T6' + W8/W9 (unlimited lobs at the R38 "
                         "gre40 cadence, the chase, the dead-row kill "
                         "signature, the hazard retreat); no model, "
                         "no training, zero RAM writes"),
        },
        "adapter_version": man.get("adapter_version")
        if isinstance(man, dict) else None,
        "episodes": eps,
        "iteration_lineage_full": lineage,
        "results": {
            "ep1": ("death (game_over) at 1318f, score 2800 — TIED "
                    "with the v1.6.0 run as the product-path RECORD "
                    "(the previous committed best 2300, R67); the "
                    "truck NOT killed (the probe: a4 floor 80 inside "
                    "the band window; the connect rate ~1/10 is the "
                    "named R69 blocker)"),
            "ep2": ("death 414f, score 2800 — the continue respawn "
                    "at the section start"),
            "mission_1_clear": "NOT ACHIEVED (not claimed)",
        },
        "r67_correction": (
            "the R67 'truck KILLED, score 2300' reading is REFUTED "
            "(the R68 probe: a4=160 at the v1.4.2 death; the score "
            "came from the wave kills + chip events); the truck has "
            "NEVER been killed on the product path"),
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
