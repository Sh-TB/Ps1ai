#!/usr/bin/env python3
"""r52_analysis_correct.py — the R52 offline analysis (authoritative,
no boot).  The capsule lever: the discriminator reads the PAY-FRAME
word state (not the tap-window churn).

Inputs: the r52 boot-4 jsonl (the first fully-proven pay-frame
telemetry path; boots 2-3 are preserved defect partials with controls
only).

Analyses:
  A. PAYMENT TABLE — every TAP with a score change: the pay frame
     (f_rel), the amount, the class (CONNECT/KILL/PIERCE), the target
     slot + pre-state, the state path (the R48/R50 transitions).
  B. THE WOUND-SHAPE HUNT — for every live slot, every union-net
     offset: a decrement-then-recovery shape co-timed with the pay
     frame (v[f-1] - v[f] >= 1 AND v returns to the pre-value within
     8 frames) = the accumulator signature the capsule named.
  C. THE PAY-FRAME SIGNATURE — per payment, the full pay-frame word
     vector per live slot (committed artifact: r52_wound_table.json)
     + the consistency check across the two +1000 connects (same
     offset, same value-band at the pay frame?).
  D. THE MAGNITUDE TABLE — the cross-round connect magnitude ledger
     (+500 x3 vs +1000 x7 across R48-R52) + the honest status of the
     discriminator (a +500 connect has NOT yet been captured under
     pay-frame telemetry — the R53 lever).
  E. CONTROLS — the zero-input + movement-only dscore (the
     movement-inclusive churn baseline, the 5th round).
"""
from __future__ import annotations

import json
import os
import sys

_REPO = "/home/z/my-project/ps1ai"
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r52")
BOOT4 = os.path.join(EVID, "r52_boot4_s2.jsonl")
OUT = os.path.join(EVID, "r52_wound_table.json")

CONNECT_ST = 0x42BC
REG_ST = 0x515C


def load_taps():
    taps = []
    frontier = None
    for line in open(BOOT4):
        ev = json.loads(line)
        if ev.get("ev") == "TAP":
            ev["_frontier"] = frontier
            taps.append(ev)
        elif ev.get("ev") == "FRONTIER_RESTORED":
            frontier = ev.get("frontier")
    return taps


def pay_frames(tap):
    """The frame-exact score increments inside the tap window."""
    fr = tap.get("frame_rows") or []
    out = []
    prev = None
    for r in fr:
        sc = r["sc"]
        if prev is not None and sc != prev:
            out.append({"f_rel": r["f_rel"], "from": prev, "to": sc,
                        "amount": sc - prev})
        prev = sc
    return out


def word_vec_at(rows, f_rel):
    for r in rows:
        if r["f_rel"] == f_rel:
            return r
    return None


def wound_shapes(rows, slot, pay_f, net):
    """Offsets with a decrement-then-recovery shape co-timed with the
    pay frame (within +/-2f)."""
    hits = []
    seq = {}
    for r in rows:
        v = (r.get("words") or {}).get(str(slot))
        if v is not None:
            seq[r["f_rel"]] = v
    if not seq:
        return hits
    fs = sorted(seq)
    for i, f in enumerate(fs):
        if abs(f - pay_f) > 2 or i == 0:
            continue
        v_prev, v_cur = seq[fs[i - 1]], seq[f]
        for oi in range(len(net)):
            d = v_prev[oi] - v_cur[oi]
            if d < 1:
                continue
            # recovery: returns to within 1 of v_prev within 8 frames
            rec = None
            for f2 in fs[i + 1:i + 9]:
                if abs(seq[f2][oi] - v_prev[oi]) <= 1:
                    rec = f2 - f
                    break
            hits.append({"slot": slot, "off": net[oi],
                         "f_rel": f, "drop": d,
                         "from": v_prev[oi], "to": v_cur[oi],
                         "recover_frames": rec})
    return hits


def main():
    taps = load_taps()
    net = None
    payments = []
    for t in taps:
        rows = t.get("frame_rows") or []
        if rows and rows[0].get("net"):
            net = rows[0]["net"]
        for p in pay_frames(t):
            pf = word_vec_at(rows, p["f_rel"])
            tgt = (t.get("target") or {})
            payments.append({
                "frontier": t.get("_frontier"), "tap": t.get("tap"),
                "kind": t.get("kind"),
                "amount": p["amount"], "f_rel": p["f_rel"],
                "target_slot": tgt.get("slot"),
                "target_st_pre": tgt.get("st"),
                "target_dx": tgt.get("dx_px"),
                "state_path": [x["to"] for x in
                               (t.get("target_st_transitions") or [])],
                "corpses": t.get("corpses"),
                "pay_frame_words": (pf or {}).get("words"),
                "pay_frame_px": (pf or {}).get("px")})
    # ---- B. the wound-shape hunt per payment -------------------------
    shapes = []
    for t in taps:
        rows = t.get("frame_rows") or []
        if not rows or not (rows[0].get("net")):
            continue
        for p in pay_frames(t):
            slots = set((rows[0].get("words") or {}).keys())
            for s in sorted(slots):
                shapes.extend([h for h in
                               wound_shapes(rows, int(s), p["f_rel"],
                                            net)])
    # ---- the consistency check across the two +1000 connects ---------
    cons = [p for p in payments if p["kind"] == "AIMED_Y_CONNECT"
            and p["amount"] > 0]
    consist = None
    if len(cons) >= 2:
        a, b = cons[0], cons[1]
        wa, wb = a["pay_frame_words"], b["pay_frame_words"]
        common = sorted(set(wa) & set(wb))
        diff = []
        for s in common:
            va, vb = wa[s], wb[s]
            for oi in range(len(net)):
                if va[oi] != vb[oi]:
                    diff.append({"slot": s, "off": net[oi],
                                 "a": va[oi], "b": vb[oi]})
        consist = {"pairs": [ (p["frontier"], p["tap"]) for p in cons ],
                   "pay_frame_equal_words": len(diff),
                   "differing": diff[:40],
                   "note": "identical pay-frame word vectors across "
                           "the two +1000 connects would mean the "
                           "magnitude is NOT a function of any "
                           "union-net word VALUE at the pay frame"}
    # ---- D. the cross-round magnitude table ---------------------------
    magnitude = {
        "plus500": [
            {"round": "R48", "n": 1, "evidence": "slot20 connect, "
             "st 0x42bc, survives; pay frame f_rel 2"},
            {"round": "R49", "n": 1, "evidence": "the +500 replicated "
             "frame-exact; the strong class-keyed form falsified"},
            {"round": "R50", "n": 1, "evidence": "+500 x3 cumulative"}],
        "plus1000": [
            {"round": "R50", "n": 1, "evidence": "the +1000 class "
             "opened (3 vs 3 after R50)"},
            {"round": "R51", "n": 2, "evidence": "st_pre 0x42bc AND "
             "0x3f48 both paid +1000 (deterministic across both "
             "frontiers)"},
            {"round": "R52", "n": 2, "evidence": "st_pre 0x42bc "
             "(frontier_a tap2, pay f_rel 3) AND 0x3f48 (frontier_b "
             "tap2, pay f_rel 4) both paid +1000 — the R51 pattern "
             "REPLICATED under pay-frame telemetry"}],
        "cumulative": "+500 x3 vs +1000 x7 across R48-R52",
        "discriminator_status":
            "PENDING a +500 capture under pay-frame telemetry (the "
            "R52 gate starved before a +500 connect landed; the two "
            "R52 connects both paid +1000) — the R53 lever",
    }
    # ---- E. controls ---------------------------------------------------
    controls = []
    for t in taps:
        if t.get("kind") in ("CONTROL_ZERO_INPUT", "CONTROL_MOVE_ONLY",
                             "CONTROL_MOVE"):
            controls.append({"frontier": t.get("_frontier"),
                             "tap": t.get("tap"),
                             "kind": t.get("kind"),
                             "dscore": t.get("score_delta"),
                             "corpses": t.get("corpses")})
    out = {
        "schema": "ps1play.r52-wound-table/1",
        "generated": __import__("time").strftime("%FT%TZ",
                                                 __import__("time")
                                                 .gmtime()),
        "commit": os.popen("git -C %s rev-parse HEAD"
                           % _REPO).read().strip(),
        "net": net, "payments": payments,
        "wound_shapes": shapes,
        "connect_consistency": consist,
        "magnitude": magnitude,
        "controls": controls,
    }
    json.dump(out, open(OUT, "w"), indent=1, default=str)
    # ---- the verdict lines -------------------------------------------
    print("[r52-analysis] payments:")
    for p in payments:
        print(f"  {p['frontier']} tap{p['tap']} {p['kind']} "
              f"amount={p['amount']} pay_f={p['f_rel']} "
              f"tgt_slot={p['target_slot']} "
              f"st_pre={hex(p['target_st_pre']) if p['target_st_pre'] else None} "
              f"path={[hex(x) if x else None for x in p['state_path']]}")
    print(f"[r52-analysis] wound shapes co-timed with payments: "
          f"{len(shapes)}")
    for h in shapes[:12]:
        print(f"   slot{h['slot']} {h['off']} drop {h['from']}->"
              f"{h['to']} @f{h['f_rel']} rec={h['recover_frames']}")
    if consist:
        print(f"[r52-analysis] connect pay-frame word equality: "
              f"{consist['pay_frame_equal_words']} differing "
              f"slot/offsets across the two +1000 connects")
    print(f"[r52-analysis] controls dscore: "
          f"{[c['dscore'] for c in controls]} (the movement-inclusive "
          f"baseline, 5th round)")
    print(f"[r52-analysis] magnitude: {magnitude['cumulative']}")
    print(f"[r52-analysis] wound table -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
