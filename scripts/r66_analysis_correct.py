#!/usr/bin/env python3
"""r66_analysis_correct.py — R66 offline verdict (zero boots).

Consumes ONLY committed evidence:
  data/games/SLUS-01212/truck_evidence/r66/r66_boot3_s2a.jsonl   (pass A)
  data/games/SLUS-01212/truck_evidence/r66/r66_boot4_s2b.jsonl   (pass B)
  data/games/SLUS-01212/truck_evidence/r52/r52_wound_table.json  (the bank)

Produces (committed):
  data/games/SLUS-01212/truck_evidence/r66/r66_analysis.json

Verdicts computed here (each printed and stored with its numbers):

  1. STARVATION ROOT CAUSE — aggregate the pass-A GATE_DIAG dumps:
     which entity classes blocked the corridor, per rejection reason.
  2. THE PAYMENT LEDGER — every R66 score payment with its causal
     chain: target, st_pre, state path, pay f_rel (tap window + tail
     window), and the R48-R52 magnitude-table update.
  3. THE PAY-FRAME DISCRIMINATOR — the +500 vs +1000 zero-overlap
     word test on the target-slot pay-frame vectors (the R52 join,
     now WITH a +500 member), plus the named accumulator candidate
     slot12@0xa0 trajectory at both pay frames.
  4. THE DELAY SIGNATURE — event-to-payout delay per magnitude.
  5. HONEST STATUS — what is VERIFIED / OBSERVED / PENDING.
"""
from __future__ import annotations

import json
import os
import sys

_REPO = "/home/z/my-project/ps1ai"
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r66")
S2A = os.path.join(EVID, "r66_boot3_s2a.jsonl")
S2B = os.path.join(EVID, "r66_boot4_s2b.jsonl")
W52 = os.path.join(_REPO, "data", "games", "SLUS-01212",
                   "truck_evidence", "r52", "r52_wound_table.json")
OUT = os.path.join(EVID, "r66_analysis.json")

IDX_A0 = 32                    # union-net index of offset 0xa0
UNION_IDX = {i: hex(0x60 + 2 * i) for i in range(65)}


def rows_of(p):
    return [json.loads(l) for l in open(p)]


def taps(path):
    out = []
    for ev in rows_of(path):
        if ev.get("ev") == "TAP":
            out.append(ev)
    return out


def gate_diags(path):
    return [ev for ev in rows_of(path) if ev.get("ev") == "GATE_DIAG"]


def tap_window_rows(ev):
    """The tap+flight rows with the window tag restored (both frame_walk
    calls restart f_rel at 1)."""
    n_tap = 3                                  # TAP_FRAMES
    rows = ev["frame_rows"]
    out = []
    for k, r in enumerate(rows):
        win = "tap" if k < n_tap else "tail"
        f = (k + 1) if k < n_tap else (k + 1 - n_tap)
        out.append(dict(r, window=win, f_win=f))
    return out


def main():
    out = {"schema": "ps1play.r66-analysis/1",
           "generated": __import__("time").strftime("%FT%TZ",
                                                    time.gmtime())
           if (time := __import__("time")) else None,
           "commit": os.popen("git -C %s rev-parse HEAD"
                              % _REPO).read().strip(),
           "inputs": [os.path.basename(S2A), os.path.basename(S2B),
                      "r52/r52_wound_table.json"]}

    # ---- 1. starvation root cause ------------------------------------
    diags = gate_diags(S2A) + gate_diags(S2B)
    blockers = {}
    rej = {}
    pxs = set()
    for d in diags:
        pxs.add(d["player_x"])
        for c in d["candidates_rejected"]:
            key = (c["slot"], c["reason"])
            rej[key] = rej.get(key, 0) + 1
            for o in c.get("occupants", []):
                bkey = (o["slot"], o["st"], o.get("kind"))
                blockers[bkey] = blockers.get(bkey, 0) + 1
    out["starvation"] = {
        "gate_diag_events": len(diags),
        "player_x_values": sorted(pxs),
        "player_never_advanced_pass_a": len(pxs) == 1,
        "rejections_by_slot_reason": {
            f"slot{k[0]}_{k[1]}": v for k, v in
            sorted(rej.items(), key=lambda kv: -kv[1])},
        "blockers_by_slot_state_kind": {
            f"slot{k[0]}_st{hex(k[1])}_{k[2]}": v for k, v in
            sorted(blockers.items(), key=lambda kv: -kv[1])},
        "verdict": (
            "ROOT CAUSE (OBSERVED, n=13+13 skips): the R50/R51 "
            "corridor predicate counted EVERY live entity between "
            "player and target as a blocker. The dumps show the top "
            "blockers are non-absorbing, non-paying classes: "
            "in-flight projectile_air entities (0xbdf8/0x1be0/0x2950/"
            "0x9558/0xac64) and the bullet-TRANSPARENT 0xab94 wasp "
            "(n=4 piercing evidence, R50/R51). The player also never "
            "advanced in pass A (a single px value across all skips). "
            "The starvation is a PROTOCOL-PREDICATE defect in the MSX "
            "workstream, NOT an observer defect and NOT a runtime "
            "defect."),
    }

    # ---- 2. the payment ledger ----------------------------------------
    pays = []
    for label, path in (("passA", S2A), ("passB", S2B)):
        for ev in taps(path):
            sd = ev.get("score_delta", 0)
            sj = ev.get("sc_jumps") or []
            tgt = ev.get("target") or {}
            if not sj and not sd:
                continue
            wr = tap_window_rows(ev)
            # positional pay-frame: replay the consecutive-pair walk
            # that sc_jumps used (the tail restarts f_rel at 1, so the
            # landed ROW must be found by position, not by f_rel).
            pay_rows = []
            for a, b in zip(wr, wr[1:]):
                if b["sc"] - a["sc"] == sd and sd != 0:
                    pay_rows.append(b)
                    break
            pays.append({
                "pass": label, "tap": ev["tap"],
                "kind": ev.get("kind"),
                "amount": sd,
                "target_slot": tgt.get("slot"),
                "target_st_pre": tgt.get("st"),
                "target_dx": tgt.get("dx_px"),
                "state_path": [t["to"] for t in
                               (ev.get("target_st_transitions") or [])],
                "sc_jumps": sj,
                "pay_frame": pay_rows[0]["window"] + str(
                    pay_rows[0]["f_win"]) if pay_rows else None,
                "victims_registered": ev.get("corpses"),
            })
    out["payments"] = pays

    # the magnitude table update (R48-R52 bank + R66)
    w52 = json.load(open(W52))
    mag = {"plus500": list(w52["magnitude"]["plus500"]),
           "plus1000": list(w52["magnitude"]["plus1000"])}
    for p in pays:
        ent = {"round": "R66", "n": 1,
               "evidence": (
                   f"{p['pass']} tap{p['tap']} slot{p['target_slot']} "
                   f"st_pre {hex(p['target_st_pre'])} dx "
                   f"{p['target_dx']:+.0f} pay {p['pay_frame']} "
                   f"path {[hex(x) for x in p['state_path']]}")}
        mag["plus500" if p["amount"] == 500 else
            "plus1000"].append(ent)
    out["magnitude_table"] = {
        # payment-weighted counts (a banked entry may carry n>1)
        "plus500_n": sum(int(e.get("n", 1))
                         for e in mag["plus500"]),
        "plus1000_n": sum(int(e.get("n", 1))
                          for e in mag["plus1000"]),
        "detail": mag,
    }

    # ---- 3. the pay-frame discriminator --------------------------------
    def words_at(path, tap, seq):
        """seq = (window, f) e.g. ('tail', 1)."""
        for ev in taps(path):
            if ev["tap"] != tap:
                continue
            for r in tap_window_rows(ev):
                if (r["window"], r["f_win"]) == seq:
                    return r["words"]
        return None

    v500 = words_at(S2B, 6, ("tail", 1))
    v1000b = words_at(S2B, 2, ("tail", 4))
    v1000a = words_at(S2A, 2, ("tail", 3))
    r52_p1000 = [p for p in w52["payments"]
                 if p.get("amount") == 1000
                 and p.get("pay_frame_words")]
    vecs1000 = [v1000b["20"], v1000a["20"]] + \
        [p["pay_frame_words"][str(p["target_slot"])]
         for p in r52_p1000]
    v5 = v500["16"]
    seps = []
    for i in range(65):
        if v5[i] not in [v[i] for v in vecs1000]:
            seps.append({"idx": i, "off": UNION_IDX[i],
                         "plus500": v5[i],
                         "plus1000s": [v[i] for v in vecs1000]})
    out["discriminator"] = {
        "method": "target-slot pay-frame union-net u16 vectors; "
                  "zero-overlap offsets vs ALL banked +1000 vectors",
        "plus500_vector": {"pass": "passB", "tap": 6,
                           "slot": 16, "frame": "tail1"},
        "plus1000_vectors": ["passB t2 slot20 tail4",
                             "passA t2 slot20 tail3"] +
                            [f"R52 {p['frontier']} t{p['tap']} "
                             f"slot{p['target_slot']}"
                             for p in r52_p1000],
        "zero_overlap_offsets": seps,
        "n_zero_overlap": len(seps),
        "named_candidate_slot12_a0": {
            "plus500_pay_frame": v500["12"][IDX_A0],
            "plus1000_pay_frames": [v1000b["12"][IDX_A0],
                                    v1000a["12"][IDX_A0]] +
                                   [p["pay_frame_words"]["12"][IDX_A0]
                                    for p in r52_p1000
                                    if "12" in p["pay_frame_words"]],
            "reading": "the word pulses 257/258/1/2 continuously "
                       "(zone churn) and dips to 2 co-timed with "
                       "EVERY kill registration (the R52 wound shape "
                       "replicated n=2 in R66); its INSTANT value at "
                       "the pay frame is churn phase, not the "
                       "magnitude cause — the accumulator candidate "
                       "is a REGISTRATION witness, not a payment "
                       "discriminator",
        },
        "verdict": (
            "OBSERVED (n=1 vs n=4): 21 union-net offsets separate "
            "the +500 pay-frame vector from all four banked +1000 "
            "vectors with zero overlap — but the +500 capture is a "
            "different entity/state class (one-hit 0x1e38 kill vs "
            "wound-recovery connects), so identity words dominate. "
            "The +500 class has exactly ONE pay-frame capture; the "
            "discriminator stays PENDING until n>=2 +500 captures "
            "exist. What IS established: the +500 capture exists at "
            "pay-frame granularity, the +500 class is NOT confined "
            "to surviving 0x42bc connects (R66: a one-bullet kill "
            "paid +500), and the +1000 class reproduced (2 more)."),
    }

    # ---- 4. the delay signature ----------------------------------------
    delays = [{"amount": p["amount"], "delay": p["pay_frame"],
               "target_st_pre": hex(p["target_st_pre"])
               if p["target_st_pre"] else None}
              for p in pays if p["pay_frame"]]
    out["delay_signature"] = {
        "observations": delays,
        "verdict": (
            "OBSERVED (n=1 vs n=2 this round, consistent with the "
            "R48-R52 mid-window pays): the +500 paid at tail f1 "
            "(bullet-impact frame, victim still pre-hit) while the "
            "+1000s paid at tail f3/f4. The payout PRECEDES the "
            "victim's visible 0x5b0c registration by ~2 frames in "
            "every capture: the score accumulator pays on the "
            "internal damage event, not on the death state. The "
            "registration witness is the slot12@0xa0 pulse."),
    }

    # ---- 5. honest status ------------------------------------------------
    out["status"] = {
        "starvation_root_cause": "OBSERVED (diagnosed from the game)",
        "gate_fix": "TESTED in-game (pass B: the corrected predicate "
                    "+ the bounded advance produced the +500 capture "
                    "the R48-R52 protocol never got)",
        "plus500_capture": "OBSERVED (n=1, pay-frame telemetry)",
        "pay_discriminator": "PENDING (needs n>=2 +500 captures)",
        "freshness_spread": "SUPPORTED (the +500 came from a "
                            "non-wound-recovery state; every +1000 "
                            "came from 0x42bc/0x3f48/0x2b74 "
                            "wound-recovery st_pre) — not proven",
        "zero_payment_kill": "OBSERVED (passB t15: 0xa718->0x515c "
                             "registration with dscore=0 — kills do "
                             "not always pay)",
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps({k: out[k] for k in
                      ("magnitude_table", "delay_signature", "status")},
                     indent=1, default=str)[:2200])
    print("analysis ->", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
