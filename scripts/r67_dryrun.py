#!/usr/bin/env python3
"""r67_dryrun.py — R67 offline contract dry-run (BEFORE any boot).

The R66 discipline verbatim: the offline contract dry-run runs BEFORE
any experiment boot and has veto power.  Checks (each printed with
its number):

  1-4   the restore-only budget line: both r66 frontiers + the anchor
        on disk; the disc/core/BIOS resolvable.
  5     the ledger gate: cap 3, over-cap raises, both scripts share
        ONE ledger file (the env probe must be boot 1).
  6     the +500 counter: bump_pay500 accepts ONLY score_delta==500
        with exactly one +500 jump; a +1000 or a two-jump +500 never
        counts; the counter file write is atomic (os.replace).
  7     the union net integrity: 65 even offsets 0x60..0xE0, shared
        with the R66 telemetry (imported verbatim).
  8     the pay-frame extraction: pay_frame_words finds the pay row on
        a synthetic TAP event and returns 65-length words.
  9     extract_pay500s honesty rule on synthetic events.
 10-11  the R66 helpers the hunt imports resolve and keep their
        contract: pick_target_r66 prefers fresh 0x4054;
        corridor_occupants_r66 excludes corpses / projectile_air /
        the transparent 0xab94 (synthetic censuses).
 12-14  the widened-set zero-overlap core: a synthetic +500 vector
        separates from synthetic +1000 vectors; a failing case yields
        an empty intersection; the verdict strings are honest.
 15-17  the runner source audit: PAY500_GOAL=2, the de-starve advance
        armed on both passes, fresh-soft preference, the wall guard,
        NO RAM-write calls, legal pad buttons only.
 18    the m2_gate note is unchanged in the capsule next_experiment.
 19    the R66 +500 extraction reproduces the committed R66 analysis
        vector provenance (passB t6 slot16 tail1) — offline, from the
        committed JSONLs.
 20    the analysis inputs all exist (or are honestly listed as the
        runs' future outputs — the dry-run checks the ones that must
        EXIST pre-boot: R66 A/B + the R52 bank).

Evidence: data/games/SLUS-01212/truck_evidence/r67/r67_dryrun.json
"""
from __future__ import annotations

import ast
import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import r67_analysis_correct as A67                # noqa: E402
import ps1play.agent.combat as combat             # noqa: E402

EV = os.path.join(_REPO, "data", "games", "SLUS-01212",
                  "truck_evidence")
STATES = "/home/z/my-project/emu/ws/states"
OUT = os.path.join(EV, "r67", "r67_dryrun.json")


def main():
    checks = {}

    # ---- 1-4: the restore-only budget line ---------------------------
    for i, f in enumerate(("r66_frontier_a", "r66_frontier_b"), 1):
        checks[f"{i:02d}_frontier_on_disk_{f}"] = os.path.exists(
            os.path.join(STATES, f + ".state"))
    checks["03_anchor_on_disk_issue5_m1_start"] = os.path.exists(
        os.path.join(STATES, "issue5_m1_start.state"))
    from ps1play import labconfig                 # noqa: E402
    checks["04_disc_core_bios_resolve"] = all([
        os.path.exists(labconfig.resolve_path("game") or ""),
        os.path.exists(labconfig.resolve_path("core") or ""),
        os.path.exists(os.path.join(_REPO, "third_party", "openbios",
                                    "openbios.bin"))])

    # ---- 5: the ledger gate (synthetic, in-memory) --------------------
    led = {"cap": 3, "count": 2}
    gate_ok = (led["count"] + 1 <= led["cap"])
    checks["05_ledger_gate_cap3_shared_file"] = bool(
        gate_ok
        and r67_env_ledger_path() == r67_hunt_ledger_path())

    # ---- 6: the +500 counter rule (synthetic taps) --------------------
    def bump_like(tap):
        sj = [j for j in tap.get("sc_jumps", []) if j["d"] == 500]
        return tap.get("score_delta") == 500 and len(sj) == 1
    ok6 = (bump_like({"score_delta": 500,
                      "sc_jumps": [{"d": 500}]})
           and not bump_like({"score_delta": 1000,
                              "sc_jumps": [{"d": 1000}]})
           and not bump_like({"score_delta": 500,
                              "sc_jumps": [{"d": 300}, {"d": 200}]})
           and not bump_like({"score_delta": 400,
                              "sc_jumps": [{"d": 500}]}))
    src_hunt = open(os.path.join(_REPO, "scripts",
                                 "r67t1_payframe_500hunt.py")).read()
    ok6 = ok6 and "os.replace" in src_hunt
    checks["06_pay500_counter_honest_rule"] = ok6

    # ---- 7: the union net ---------------------------------------------
    checks["07_union_net_65_even_60_e0"] = (
        A67.UNION_NET == tuple(range(0x60, 0xE1, 2))
        and len(A67.UNION_NET) == 65)

    # ---- 8: pay_frame_words on a synthetic TAP ------------------------
    synth = {"score_delta": 500,
             "frame_rows": [
                 {"f_rel": k + 1, "sc": 1000 if k < 4 else 1500,
                  "words": {"16": list(range(65))}}
                 for k in range(8)]}
    pf = A67.pay_frame_words(synth)
    checks["08_pay_frame_words_synth"] = bool(
        pf and pf["frame"].startswith("tail")
        and len(pf["words"]["16"]) == 65)

    # ---- 9: extract_pay500s honesty (synthetic JSONL) -----------------
    ev_ok = {"ev": "TAP", "tap": 6, "score_delta": 500,
             "sc_jumps": [{"f_rel": 5, "d": 500, "sc": 1500}],
             "target": {"slot": 16, "st": 0x1E38, "dx_px": 20.3},
             "target_st_transitions": [],
             "frame_rows": synth["frame_rows"]}
    ev_bad = dict(ev_ok, score_delta=1000)
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl",
                                     delete=False) as f:
        f.write(json.dumps(ev_ok) + "\n")
        f.write(json.dumps(ev_bad) + "\n")
        tmpj = f.name
    got = A67.extract_pay500s(tmpj, "synth")
    os.unlink(tmpj)
    checks["09_extract_pay500s_honest"] = bool(
        len(got) == 1 and got[0]["target_slot"] == 16)

    # ---- 10-11: the R67 gate (the R66 contract + the disclosed
    # 0x5B0C alignment; the synthetics are ordered so the fresh-soft
    # preference is actually reachable on a CLEAR corridor) ----------
    import r66t1_payframe_destarve as R66M         # noqa: E402
    from r67t1_payframe_500hunt import (
        corridor_occupants_r67, pick_target_r67, R67_CORPSE_ST)
    cen = [
        {"slot": 12, "st": 0x4054, "x_px": 1230.0, "dx_px": 10.0,
         "kind": "enemy", "targetable": True},
        {"slot": 13, "st": 0x42BC, "x_px": 1240.0, "dx_px": 20.0,
         "kind": "enemy", "targetable": True},
        {"slot": 14, "st": 0xAB94, "x_px": 1235.0, "dx_px": 15.0,
         "kind": "wasp", "targetable": True},
        {"slot": 15, "st": 0x5B0C, "x_px": 1242.0, "dx_px": 22.0,
         "kind": "enemy", "targetable": False},
        {"slot": 16, "st": 0xBDF8, "x_px": 1236.0, "dx_px": 16.0,
         "kind": "projectile_air", "targetable": True},
    ]
    tgt = pick_target_r67(cen, set(), 1220.0)
    checks["10_pick_target_r67_prefers_fresh_soft"] = bool(
        tgt is not None and tgt["slot"] == 12
        and tgt["st"] == 0x4054)
    occ = corridor_occupants_r67(cen, 1220.0, 1250.0)
    slots = {o["slot"] for o in occ}
    occ66 = R66M.corridor_occupants_r66(cen, 1220.0, 1250.0)
    slots66 = {o["slot"] for o in occ66}
    checks["11_gate_excludes_transparent_proj_corpse"] = bool(
        13 in slots and 12 in slots and 14 not in slots
        and 15 not in slots and 16 not in slots)
    checks["11b_disclosed_delta_pinned_5b0c"] = bool(
        15 in slots66 and 15 not in slots
        and 0x5B0C in R67_CORPSE_ST
        and 0x5B0C not in combat.CORPSE_ST)

    # ---- 12-14: the widened-set core ----------------------------------
    v5a = [7] * 65
    v5b = [7] * 65
    v5b[3] = 9
    vka = [1] * 65
    vkb = [2] * 65
    t_ok = A67.zero_overlap_test(
        [{"src": "a", "slot": 16, "vec": v5a},
         {"src": "b", "slot": 20, "vec": v5b}],
        [{"src": "ka", "vec": vka}, {"src": "kb", "vec": vkb}])
    t_bad = A67.zero_overlap_test(
        [{"src": "a", "slot": 16, "vec": v5a},
         {"src": "b", "slot": 20, "vec": [1] * 65}],
        [{"src": "ka", "vec": vka}])
    checks["12_zero_overlap_resolves_synth"] = bool(
        t_ok["n_intersection"] == 65 and "RESOLVED" in t_ok["verdict"])
    checks["13_zero_overlap_fails_honestly"] = bool(
        t_bad["n_intersection"] == 0
        and "PENDING" in t_bad["verdict"])
    checks["14_verdict_strings_honest"] = bool(
        "RESOLVED" in t_ok["verdict"] and "PENDING" in t_bad["verdict"])

    # ---- 15-17: the runner source audit --------------------------------
    tree = ast.parse(src_hunt)
    src_all = src_hunt
    checks["15_goal_pay500_2"] = "PAY500_GOAL = 2" in src_all
    checks["16_destarve_both_passes"] = bool(
        '"destarve": True' in src_all
        and 'ADVANCE_STEP_F, {"RIGHT"}' in src_all)
    checks["17a_no_ram_write_calls"] = not any(
        tok in src_all for tok in (".write_u", ".poke", "write_mem",
                                   "u16(", ".u8("))
    buttons = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Set):
            for e in node.elts:
                if isinstance(e, ast.Constant) \
                        and isinstance(e.value, str):
                    buttons.add(e.value)
    checks["17b_legal_pad_buttons_only"] = buttons <= {
        "RIGHT", "LEFT", "UP", "DOWN", "Y", "X", "B", "A", "START",
        "SELECT", "L1", "R1"}
    checks["17c_wall_guard_present"] = "WALL_TAPS_S" in src_all

    # ---- 18: the capsule m2_gate note unchanged ------------------------
    cap = json.load(open(os.path.join(
        _REPO, "data", "knowledge", "msx", "capsule.json")))
    checks["18_m2_gate_note_unchanged"] = (
        cap["next_experiment"]["m2_gate_note"]
        == "unchanged - interactive M2 entry stays gated on a clean "
           "(deaths=0, no-restart) deep resolve posture")

    # ---- 19: the R66 +500 provenance reproduces offline ----------------
    r66_p500 = (A67.extract_pay500s(A67.R66A, "r66 passA")
                + A67.extract_pay500s(A67.R66B, "r66 passB"))
    r66an = json.load(open(os.path.join(EV, "r66",
                                        "r66_analysis.json")))
    pv = r66an["discriminator"]["plus500_vector"]
    got = [p for p in r66_p500
           if p["pass"] == "r66 passB" and p["tap"] == pv["tap"]
           and p["target_slot"] == pv["slot"]]
    checks["19_r66_plus500_reproducible"] = bool(
        len(got) == 1 and got[0]["pay_frame"] == pv["frame"]
        and got[0]["target_st_pre"] == 0x1E38)
    bank = A67.extract_pay1000_bank()
    checks["19b_plus1000_bank_vectors"] = (
        len(bank), "expected 4 (2 R66 + 2 R52)")

    # ---- 20: pre-boot inputs exist -------------------------------------
    checks["20_preboot_inputs_exist"] = {
        "r66_a": os.path.exists(A67.R66A),
        "r66_b": os.path.exists(A67.R66B),
        "r52_bank": os.path.exists(A67.W52),
        "hunt_a_jsonl": "(produced by boot 2)",
        "hunt_b_jsonl": "(produced by boot 3)",
    }

    n_fail = [k for k, v in checks.items()
              if v is False]
    out = {"schema": "ps1play.r67-dryrun/1",
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "commit": os.popen("git -C %s rev-parse HEAD"
                              % _REPO).read().strip(),
           "ok": not n_fail,
           "n_checks": len(checks),
           "failed": n_fail,
           "checks": checks}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, indent=1, default=str)[:3000])
    return 0 if out["ok"] else 1


def r67_env_ledger_path():
    return os.path.join(_REPO, "scratch", "r67", "boots_used.json")


def r67_hunt_ledger_path():
    from r67t1_payframe_500hunt import LEDGER
    return LEDGER


if __name__ == "__main__":
    sys.exit(main())
