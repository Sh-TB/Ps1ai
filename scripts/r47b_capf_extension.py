#!/usr/bin/env python3
"""r47b_capf_extension.py — R47 (buzzybee, the 40% track, Issue #6).

The capsule lever (R46 close-out): the CAP_F EXTENSION arm.  The R46
mechanism decision (PER_FRAME_TIME: score = survival climb-frames,
+1/frame after a 32f ready phase) predicts bot_policy5 at CAP_F 1700
reaches score >= 1550 (~1668 climb-frames available) — the climb
continues past f1500.  THE REAL RISK is not scoring but late-game
wasp density vs the guarantee planner: the first hit past the R45-B
1500f frontier would be the finding.

HYPOTHESIS (verbatim): bot_policy5 verbatim at CAP_F 1700 (extend to
1800 only if 1700 finishes with 0 hits) reaches score >= 1550 with
hits == 0.  Oracle line: score >= 1550 AND hits 0 AND caused >= 2.
The pass-table comparison vs the 1500f runs (passes 7-8 density,
min_sep trend) decides whether the dominance recipe scales with time
or the wasp spawn schedule breaks it.

Protocol: restore-only arms (the R45-B run_arm VERBATIM — protocol
parity: same checkpoint, same kw, the pass/pickup/attribution
machinery unchanged), arm A = bot_policy5 verbatim at 1700; arm A2
(the extension) = the same at 1800 ONLY if the 1700 arm finished
with 0 hits (the capsule clause).

PRE-RUN DISCLOSURE (the sandbox rollback): the r45b gs1 checkpoint
(scratch/r45b/state_r45b_gs1.bin) is LOST to the sandbox filesystem
reset — never committed (no-game-bytes).  The environment was
rebuilt INTERNET-FIRST sha-verified BEFORE any boot (the R45-B
precedent, 0 boots): upstream EXE 9b0bfc08...c909a8ba byte-identical
(re-fetched from the manifest URL, sha-verified), committed
wrap-script output 042b94bb...bb093 byte-identical.  boot 1 = the
core+rom load AND the gs1 checkpoint rebuild in-process (the r42b /
R45-B precedent) — cap 1 DISCLOSED PRE-RUN.  Restores are NOT boots
(r35 precedent).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(REPO, "scripts"))

import r35b_lib as L                       # noqa: E402
import r43b_planner as P                   # noqa: E402
import r45b_preposition_margin as R45B     # noqa: E402
from r45b_preposition_margin import run_arm  # noqa: E402

OUT = os.path.join(REPO, "scratch", "r47b")
L.OUT = OUT
L.SHOTS = os.path.join(OUT, "shots")
L.BOOTS = os.path.join(OUT, "boots_used.json")
L.CKPT_PATH = os.path.join(OUT, "state_r47b_gs1.bin")
os.makedirs(L.SHOTS, exist_ok=True)

T0 = time.time()
CAP_F = 1700               # the capsule lever (1500 -> 1700)
CAP_F_EXT = 1800           # only if 1700 finishes with 0 hits

# ---- internet-first environment verification (0 boots) -----------
EXE = "/home/z/my-project/emu/games_homebrew/candidates_r23/BuzzyBee.ps-exe"
DISC = "/home/z/my-project/emu/games_homebrew/patched/buzzybee_ntsc_lic.bin"
EXE_SHA = "9b0bfc089c33d6116f2e67436254a4ced6e26275a7cac83f5f0dda95c909a8ba"
DISC_SHA = "042b94bb29907e75b4eadd0699619eb770089bf8880adf31f26bcc591a1bb093"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_environment():
    e, d = sha256(EXE), sha256(DISC)
    ok = (e == EXE_SHA and d == DISC_SHA)
    return {"exe_sha256": e, "exe_ok": e == EXE_SHA,
            "disc_sha256": d, "disc_ok": d == DISC_SHA,
            "internet_first_verified": ok}


def main():
    env = verify_environment()
    assert env["internet_first_verified"], \
        f"environment sha mismatch: {env}"
    print("[r47b] environment verified internet-first:", env["exe_sha256"][:8],
          env["disc_sha256"][:8], flush=True)

    R, log, dump = L.make_logger(L.OUT, "boot_log_r47b.json", "r47b")
    if not os.path.exists(L.BOOTS):
        json.dump({"cap": 1, "count": 0, "log": [], "note":
                   "R47b ledger: cap 1 disclosed pre-run = the core+rom "
                   "load AND the gs1 checkpoint rebuild (DISCLOSED: the "
                   "sandbox rollback lost scratch/r45b/"
                   "state_r45b_gs1.bin; the environment was rebuilt "
                   "internet-first sha-verified BEFORE this boot: "
                   "upstream EXE 9b0bfc08... byte-identical, committed "
                   "wrap-script output 042b94bb... byte-identical — "
                   "the R45-B precedent, 0 boots); the arms are "
                   "restore-only (restores are NOT boots, r35 "
                   "precedent)",
                   "count_includes_core_load": True},
                  open(L.BOOTS, "w"), indent=1)
    led = L.ledger_use(1, "r47b_capf_extension.py",
                       note="boot 1: core+rom load -> gs1 checkpoint "
                            "rebuild (disclosed) -> arm A (bot_policy5 "
                            "verbatim at CAP_F 1700) -> arm A2 (1800) "
                            "only if A finished with 0 hits")
    log("ledger", count=led["count"], cap=led["cap"], out=L.OUT)
    log("environment", **env)
    bee = L.Bee("ws_r47b")
    av = bee.load_game()
    log("boot", core=bee.core.core_name, av=av)

    # ---- boot 1: rebuild the gs1 checkpoint (the r42b pattern) ------
    bee.run(900, set())
    st = bee.state()
    log("settled", f=bee.frames_run, gs=st["gs"], score=st["score"])
    if st["gs"] == 0:
        bee.set_buttons("START")
        bee.run_frame()
        bee.set_buttons(set())
        for _ in range(60):
            bee.run(1, set())
            if bee.i32(L.GS) == 1:
                break
    st = bee.state()
    assert st["gs"] == 1, f"expected gs1 after START, got {st['gs']}"
    bee.run(10, set())
    CKPT = bee.serialize()
    open(L.CKPT_PATH, "wb").write(CKPT)
    st = bee.state()
    log("checkpoint_saved", bytes=len(CKPT), score=st["score"],
        hp=st["hp"], f_abs=bee.frames_run, path=L.CKPT_PATH)
    bee.snap("r47b_checkpoint", R)

    # ---- arm A: bot_policy5 verbatim at CAP_F 1700 -------------------
    # protocol parity: the run_arm VERBATIM, only the module-global
    # frame cap changes (1500 -> 1700)
    kwA = {"engage": 200, "margin": 16, "flower_hi": 170, "hover_y": 95}
    R45B.CAP_F = CAP_F
    mA = run_arm(bee, "A1700", P.bot_policy5, kwA, CKPT, log, R, dump)
    # ---- arm A2: the extension (only if A finished with 0 hits) ------
    mA2 = None
    if mA["enemy_hits"] == 0:
        log("extension_armed", a_hits=0, cap_f=CAP_F_EXT,
            reason="the capsule clause: extend only if 1700 finished "
                   "with 0 hits")
        R45B.CAP_F = CAP_F_EXT
        mA2 = run_arm(bee, "A1800", P.bot_policy5, kwA, CKPT, log, R,
                      dump)
    else:
        log("extension_not_armed", a_hits=mA["enemy_hits"],
            reason="the first hit past the 1500f frontier IS the "
                   "finding (the capsule risk)")
    best = mA2 if (mA2 is not None and mA["enemy_hits"] == 0) else mA
    oracle = {
        "score_ge_1550": best["score"] >= 1550,
        "hits_zero": best["enemy_hits"] == 0,
        "caused_ge_2": best["pickups_caused"] >= 2,
    }
    oracle["CAPF_GOAL"] = bool(all(oracle.values()))
    metrics = {
        "schema": "ps1play.r47b-evidence/1",
        "round": "R47 (buzzybee, the 40% track)",
        "boot_ledger": led,
        "environment": env,
        "checkpoint": L.CKPT_PATH + " (rebuilt in boot 1, disclosed)",
        "cap_frames": CAP_F, "cap_frames_ext": CAP_F_EXT,
        "arm_A1700": mA, "arm_A1800": mA2,
        "oracle": oracle,
        "pass_density_compare": {
            "r45_1500f_policy5": {"passes": 6, "hits": 0,
                                  "score": 1401, "hp": 5666},
            "r47_1700f_policy5": {"passes": mA["passes"],
                                  "hits": mA["enemy_hits"],
                                  "score": mA["score"],
                                  "hp": mA["hp"]},
            "min_sep_1700": [round(p["min_sep"], 1)
                             for p in mA["pass_detail"]],
        },
        "wall_s": round(time.time() - T0, 1),
    }
    json.dump(metrics, open(os.path.join(L.OUT, "metrics_r47b.json"),
                            "w"), indent=1, default=str)
    log("r47b_verdict", capf_goal=oracle["CAPF_GOAL"],
        A1700_score=mA["score"], A1700_hits=mA["enemy_hits"],
        A1700_passes=mA["passes"], A1700_caused=mA["pickups_caused"],
        A1700_flaps=mA["flaps"],
        A1800_score=(mA2 or {}).get("score"),
        A1800_hits=(mA2 or {}).get("enemy_hits"),
        A1800_passes=(mA2 or {}).get("passes"))
    dump()
    sb = L.sync_back()
    if sb:
        log("sync_back", note=sb)
    print("[r47b] DONE wall=", round(time.time() - T0, 1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
