#!/usr/bin/env python3
"""r69_gameplay_record.py — commit the R69 product-path run record.

Copies the FINAL (v1.7.1) run artifacts into the committed evidence
tree and writes the honest record (with the full iteration lineage)
to data/games/SLUS-01212/truck_evidence/r69/r69_product_run.json.
Offline bookkeeping only — no boots.

THE ITERATION LINEAGE (each step probe-pinned):
  v1.7.0  C1 the connect window [125, 140] (the capsule's numbers).
          ep1 1154f / 2200 — a REGRESSION vs the record.  The probe
          (r69_connect_probe.jsonl): 3 in-window throws at dx
          -139.5/-136.5/-136.5 ALL MISSED — the truck a4 FROZEN at
          300 through the whole fight (0 connects); the ~+12px/throw
          animation drift + the section scroll re-created the R68
          window-closure failure (px 1074 -> 1108.8 pinned; the
          death at 1154f with the truck at dx -171.3).
  v1.7.1  C1 tightened to [130, 135] (bracketing the only observed
          connect, the R68 record's -133.5).  ep1 1318f / 1700 —
          THE CONNECT WINDOW IS REAL: 7 gre40 throws (the capsule's
          "up to 7 throws" EXACT), EVERY throw at dx -133.5 EXACTLY
          (px 1071.0, the record posture verbatim), the truck a4
          300 -> 200 (f989) -> 100 (f1153) = TWO CONFIRMED CONNECTS
          (throws 3 and 7; the rate 2/7 = 29% vs the R38 ~1/10
          baseline).  ONE connect short of the kill: the SECTION
          SCROLL shoved the player out of the window mid-cooldown
          (px 1071 -> 1105.8 pinned, truck_dx -168.3, 3 grenades
          unspendable); the death at f1318 = the record frame (the
          scroll-timed pin death).  The T5 chip-fire withdrawal
          held: the truck damage is PURE lob connects.
          ep2 (k=12) 386f / 1700 — the R68 v1.6.0 ep2 frame-exact
          (the wave section dominates before the truck).

NEW FACTS (the R70 leads):
  * the connect is (posture x PHASE)-gated: 2/7 connects from the
    IDENTICAL throw posture; the connects landed 164f apart
    (f989/f1153) — the truck vulnerability-cycle lead;
  * the truck-fight window is scroll-capped (~280f, 7 gre40 throws
    max); the kill needs the connect rate >= 3/7 = 43%.
"""
import json
import os
import shutil
import time

REPO = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO, "data/games/SLUS-01212/truck_evidence/r69",
                   "r69_product_run.json")


def main():
    dst = os.path.join(REPO, "data/games/SLUS-01212/truck_evidence/r69",
                       "product_run")
    os.makedirs(dst, exist_ok=True)
    for name in ("episodes.jsonl", "episode_001.json",
                 "episode_002.json", "runtime_manifest.json",
                 "events.jsonl"):
        src = os.path.join(REPO, "data/r69b", name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dst, name))
    sdst = os.path.join(dst, "shots")
    os.makedirs(sdst, exist_ok=True)
    shots = os.path.join(REPO, "data/r69b/shots")
    if os.path.isdir(shots):
        for fn in os.listdir(shots):
            shutil.copyfile(os.path.join(shots, fn),
                            os.path.join(sdst, fn))

    rows = [json.loads(l) for l in
            open(os.path.join(dst, "episodes.jsonl"))]
    eps = []
    for r in rows:
        eps.append({
            "episode": r.get("episode"), "seed_k": r.get("seed_k"),
            "result": r.get("result"),
            "death_reason": r.get("death_reason"),
            "frames": r.get("frames"), "actions": r.get("actions"),
            "score": r.get("pipes"),
            "policy": r.get("policy_name"),
            "trace_sha256": r.get("trace_sha256"),
        })
    commit = os.popen("git -C %s rev-parse HEAD" % REPO).read().strip()
    out = {
        "schema": "ps1play.r69-product-run/1",
        "generated": time.strftime("%FT%TZ", time.gmtime()),
        "commit": commit,
        "command": ("python3 -m ps1play play metal_slug_x --episodes 2 "
                    "--max-frames 10000 --verbose --screenshot "
                    "--output data/r69b"),
        "disc": {
            "cue": "ps1play/runtime/session.py:"
                   "GAME_DEFAULT_ISO['metal_slug_x']",
            "sha256": "45cde149878fe945d0219fd0f61ca09856aee66bdcc9"
                      "119de21c0583f1d0667d",
            "serial": "SLUS-01212",
        },
        "policy": {
            "name_version": "msx_mission1_rules:1.7.1",
            "identity": ("deterministic rules; the R69 connect-window "
                         "rule C1 (the lob ONLY while |dx| in "
                         "[130, 135], gre40, the hold/retreat "
                         "discipline; the T5 chip-fire withdrawn for "
                         "the window test) + the R68 T2'/T6'/W8/W9 "
                         "lineage; no model, no training, zero RAM "
                         "writes"),
        },
        "results": {
            "ep1": "death (game_over) at 1318f, score 1700 — the "
                   "RECORD FRAME tied (1318f); the truck a4 300 -> "
                   "100 = TWO CONFIRMED LOB CONNECTS at the exact "
                   "posture (2/7); ONE connect short — the section "
                   "scroll shoved the player out of the window "
                   "(the truck NOT killed, honestly recorded)",
            "ep2": "death (game_over) at 386f, score 1700 — the R68 "
                   "v1.6.0 ep2 frame-exact (the pre-truck wave "
                   "section dominates)",
        },
        "episodes": eps,
        "probes": {
            "v1.7.0": ("truck_evidence/r69/r69_connect_probe.jsonl "
                       "(the [125,140] falsification: 0/3 connects, "
                       "a4 frozen at 300)"),
            "v1.7.1": ("truck_evidence/r69/r69b_connect_probe.jsonl "
                       "(the [130,135] verification: 7 throws ALL at "
                       "dx -133.5, a4 300->200->100)"),
        },
        "iteration_lineage_full": [
            {"policy": "msx_mission1_rules:1.7.0", "episode": 1,
             "frames": 1154, "actions": 77, "score": 2200,
             "result": "death",
             "probe": "0/3 connects (dx -139.5/-136.5/-136.5), a4 "
                      "frozen at 300 — the outer window falsified"},
            {"policy": "msx_mission1_rules:1.7.1", "episode": 1,
             "frames": 1318, "actions": 67, "score": 1700,
             "result": "death",
             "probe": "7/7 throws at dx -133.5, 2 connects (a4 "
                      "300->100), one short — the scroll closed the "
                      "window"},
            {"policy": "msx_mission1_rules:1.7.1", "episode": 2,
             "frames": 386, "actions": 6, "score": 1700,
             "result": "death"},
        ],
        "r68_lineage_note": ("the R68 record 1318f/2800 (v1.6.0/"
                             "v1.6.2) stands as the best SCORE; the "
                             "R69 v1.7.1 ties the death FRAME with "
                             "the first confirmed truck-connect "
                             "evidence on the product path (a4 "
                             "300->100, pure lob connects)"),
        "zero_overlap": "NOT re-run — no new +500 capture (the wave "
                        "paid +300/+100 only; the truck never died)",
        "legality": ("legal inputs only, zero RAM writes, no "
                     "training, no runtime LLM; the disc pin "
                     "enforced by preflight"),
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print("record ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
