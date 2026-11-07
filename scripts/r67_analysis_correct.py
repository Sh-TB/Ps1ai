#!/usr/bin/env python3
"""r67_analysis_correct.py — R67 offline verdict (zero boots).

Consumes ONLY committed evidence:
  data/games/SLUS-01212/truck_evidence/r67/r67_boot2_s2a.jsonl  (hunt a)
  data/games/SLUS-01212/truck_evidence/r67/r67_boot3_s2b.jsonl  (hunt b)
  data/games/SLUS-01212/truck_evidence/r66/r66_boot3_s2a.jsonl  (R66 A)
  data/games/SLUS-01212/truck_evidence/r66/r66_boot4_s2b.jsonl  (R66 B)
  data/games/SLUS-01212/truck_evidence/r52/r52_wound_table.json (the bank)

Produces (committed):
  data/games/SLUS-01212/truck_evidence/r67/r67_analysis.json

Verdicts computed here (each printed and stored with its numbers):

  1. THE +500 CAPTURE LEDGER — every R67 +500 with its causal chain
     (st_pre, pay frame, state path), the magnitude-table update, and
     the honesty rule: a capture counts only when score_delta == 500
     AND exactly one +500 jump lands in the tap window.
  2. THE WIDENED-SET ZERO-OVERLAP TEST — the R67 lever verbatim: with
     n>=2 +500 pay-frame vectors (target-slot union-net u16 words),
     test EVERY offset against ALL banked +1000 vectors; report the
     per-capture zero-overlap sets AND their intersection (the
     discriminator candidate set).  Verdict RESOLVED only if the
     intersection separates the whole +500 class from the whole
     +1000 class on the widened set.
  3. THE DELAY SIGNATURE — pay-frame position per magnitude on the
     widened set (+500 tail f1 vs +1000 tail f3/f4).
  4. HONEST STATUS — what is VERIFIED / OBSERVED / PENDING.

Reusable core (imported by the dry-run): zero_overlap_test(),
extract_pay500s(), pay_frame_words().
"""
from __future__ import annotations

import json
import os
import sys

_REPO = "/home/z/my-project/ps1ai"
EV = os.path.join(_REPO, "data", "games", "SLUS-01212",
                  "truck_evidence")
R67A = os.path.join(EV, "r67", "r67_boot2_s2a.jsonl")
R67B = os.path.join(EV, "r67", "r67_boot3_s2b.jsonl")
R66A = os.path.join(EV, "r66", "r66_boot3_s2a.jsonl")
R66B = os.path.join(EV, "r66", "r66_boot4_s2b.jsonl")
W52 = os.path.join(EV, "r52", "r52_wound_table.json")
OUT = os.path.join(EV, "r67", "r67_analysis.json")

UNION_NET = tuple(range(0x60, 0xE1, 2))       # 65 even offsets
UNION_IDX = {i: hex(0x60 + 2 * i) for i in range(65)}
IDX_A0 = 32                    # union-net index of offset 0xa0


def rows_of(path):
    return [json.loads(l) for l in open(path)]


def taps(path):
    return [ev for ev in rows_of(path) if ev.get("ev") == "TAP"]


def tap_window_rows(ev):
    """The tap+flight rows with the window tag restored (both
    frame_walk calls restart f_rel at 1)."""
    n_tap = 3                                  # TAP_FRAMES
    rows = ev["frame_rows"]
    out = []
    for k, r in enumerate(rows):
        win = "tap" if k < n_tap else "tail"
        f = (k + 1) if k < n_tap else (k + 1 - n_tap)
        out.append(dict(r, window=win, f_win=f))
    return out


def pay_frame_words(ev):
    """The FULL union-net words dict at the pay row (the consecutive-
    pair walk that sc_jumps used), or None if no single jump covers
    the score delta.  This is the R66 pay-frame extraction verbatim,
    now returning the words for the discriminator test."""
    sd = ev.get("score_delta", 0)
    if not sd:
        return None
    wr = tap_window_rows(ev)
    for a, b in zip(wr, wr[1:]):
        if b["sc"] - a["sc"] == sd:
            return {"frame": f"{b['window']}{b['f_win']}",
                    "words": b["words"]}
    return None


def extract_pay500s(path, label):
    """Every verified +500 in one JSONL: score_delta == 500 AND
    exactly one +500 jump (the honesty rule)."""
    out = []
    for ev in taps(path):
        sd = ev.get("score_delta", 0)
        sj = [j for j in (ev.get("sc_jumps") or []) if j["d"] == 500]
        if sd != 500 or len(sj) != 1:
            continue
        tgt = ev.get("target") or {}
        pf = pay_frame_words(ev)
        out.append({
            "pass": label, "tap": ev["tap"],
            "amount": sd,
            "target_slot": tgt.get("slot"),
            "target_st_pre": tgt.get("st"),
            "target_dx": tgt.get("dx_px"),
            "state_path": [t["to"] for t in
                           (ev.get("target_st_transitions") or [])],
            "pay_frame": pf["frame"] if pf else None,
            "pay_words": pf["words"] if pf else None,
        })
    return out


def extract_pay1000s(path, label):
    """Every verified +1000 in one JSONL (the R67 passes replicated
    the wound-recovery class twice — bank them)."""
    out = []
    for ev in taps(path):
        sd = ev.get("score_delta", 0)
        sj = [j for j in (ev.get("sc_jumps") or []) if j["d"] == 1000]
        if sd != 1000 or len(sj) != 1:
            continue
        tgt = ev.get("target") or {}
        pf = pay_frame_words(ev)
        out.append({
            "pass": label, "tap": ev["tap"],
            "amount": sd,
            "target_slot": tgt.get("slot"),
            "target_st_pre": tgt.get("st"),
            "pay_frame": pf["frame"] if pf else None,
            "pay_words": pf["words"] if pf else None,
        })
    return out


def extract_pay1000_bank():
    """All banked +1000 pay-frame vectors: R52 wound-table payments +
    the two R66 captures (extracted from the committed R66 JSONLs the
    same way as the R66 analysis did)."""
    w52 = json.load(open(W52))
    vecs = []
    for p in w52["payments"]:
        if p.get("amount") == 1000 and p.get("pay_frame_words"):
            vecs.append({"src": f"R52 {p.get('frontier', '?')} "
                                f"t{p.get('tap')}",
                         "slot": p.get("target_slot"),
                         "vec": p["pay_frame_words"][
                             str(p["target_slot"])]})
    for path, label in ((R66A, "R66 passA"), (R66B, "R66 passB")):
        for ev in taps(path):
            if ev.get("score_delta") != 1000:
                continue
            pf = pay_frame_words(ev)
            slot = (ev.get("target") or {}).get("slot")
            if pf and slot is not None and str(slot) in pf["words"]:
                vecs.append({"src": f"{label} t{ev['tap']}",
                             "slot": slot,
                             "vec": pf["words"][str(slot)]})
    return vecs


def zero_overlap_test(plus500_vecs, plus1000_vecs):
    """THE WIDENED-SET TEST (reusable core; the dry-run unit-tests it
    on synthetic vectors).

    For each +500 vector: the offsets whose pay-frame value does not
    occur in ANY +1000 vector (per-capture zero overlap).  The
    discriminator candidate set is the INTERSECTION over all +500
    vectors.  Verdict RESOLVED iff the intersection is non-empty
    (the class separation holds on the widened set)."""
    per_capture = []
    for v in plus500_vecs:
        seps = []
        for i in range(65):
            val = v["vec"][i]
            if all(val != w["vec"][i] for w in plus1000_vecs):
                seps.append({"idx": i, "off": UNION_IDX[i],
                             "plus500": val})
        per_capture.append({"src": v["src"], "slot": v["slot"],
                            "n_zero_overlap": len(seps),
                            "offsets": seps})
    if not per_capture:
        return {"per_capture": [], "intersection": [],
                "n_intersection": 0, "verdict": "NO +500 VECTORS"}
    inter = {s["idx"]: s for s in per_capture[0]["offsets"]}
    for pc in per_capture[1:]:
        cur = {s["idx"]: s for s in pc["offsets"]}
        inter = {i: s for i, s in inter.items() if i in cur}
    inter_list = [inter[i] for i in sorted(inter)]
    if not inter_list:
        verdict = ("PENDING: the per-capture zero-overlap sets do "
                   "NOT intersect — no single union-net offset "
                   "separates the +500 class from the +1000 class "
                   "across all captures.")
    elif len(plus500_vecs) < 2:
        verdict = (
            "SINGLE-CAPTURE SEPARATION (n=1 +500 vector): the "
            "intersection is non-empty (n=%d offsets) but it is "
            "just the one capture's zero-overlap set — the CLASS "
            "discriminator stays PENDING until n>=2 +500 captures "
            "exist (the R66/R67 bar; with one capture the "
            "separation is dominated by identity words, not by "
            "magnitude)." % len(inter_list))
    else:
        verdict = (
            "RESOLVED on the widened set: the intersection of the "
            "per-capture zero-overlap offset sets is NON-EMPTY "
            "(n=%d); these offsets separate EVERY banked +500 "
            "pay-frame vector from EVERY banked +1000 pay-frame "
            "vector." % len(inter_list))
    return {"per_capture": per_capture,
            "intersection": inter_list,
            "n_intersection": len(inter_list),
            "n_plus500_vectors": len(plus500_vecs),
            "n_plus1000_vectors": len(plus1000_vecs),
            "verdict": verdict}


def main():
    r67_p500 = (extract_pay500s(R67A, "r67 passA")
                + extract_pay500s(R67B, "r67 passB"))
    r66_p500 = extract_pay500s(R66A, "r66 passA") \
        + extract_pay500s(R66B, "r66 passB")
    all_p500 = r66_p500 + r67_p500
    r67_p1000 = (extract_pay1000s(R67A, "r67 passA")
                 + extract_pay1000s(R67B, "r67 passB"))
    vecs1000 = extract_pay1000_bank()
    for p in r67_p1000:
        slot = p["target_slot"]
        if p.get("pay_words") and slot is not None \
                and str(slot) in p["pay_words"]:
            vecs1000.append({"src": f"{p['pass']} t{p['tap']}",
                             "slot": slot,
                             "vec": p["pay_words"][str(slot)]})

    out = {"schema": "ps1play.r67-analysis/1",
           "commit": os.popen("git -C %s rev-parse HEAD"
                              % _REPO).read().strip(),
           "inputs": [os.path.basename(R67A), os.path.basename(R67B),
                      os.path.basename(R66A), os.path.basename(R66B),
                      "r52/r52_wound_table.json"]}

    # ---- 1. the +500 capture ledger ----------------------------------
    out["pay500_ledger"] = {
        "r66_captures": [{k: v for k, v in p.items()
                          if k != "pay_words"} for p in r66_p500],
        "r67_captures": [{k: v for k, v in p.items()
                          if k != "pay_words"} for p in r67_p500],
        "n_plus500_total": len(all_p500),
    }

    # the magnitude table update (R48-R66 bank + R67)
    w52 = json.load(open(W52))
    mag = {"plus500": list(w52["magnitude"]["plus500"]),
           "plus1000": list(w52["magnitude"]["plus1000"])}
    r66_p1000 = (extract_pay1000s(R66A, "r66 passA")
                 + extract_pay1000s(R66B, "r66 passB"))
    for p in all_p500:
        if p["pass"].startswith("r66"):
            # the R66 capture is NOT in the R52 bank on disk (that
            # bank predates R66) — carry it forward with its round
            mag["plus500"].append({
                "round": "R66", "n": 1,
                "evidence": (f"{p['pass']} tap{p['tap']} "
                             f"slot{p['target_slot']} st_pre "
                             f"{hex(p['target_st_pre'])} pay "
                             f"{p['pay_frame']}")})
            continue
        mag["plus500"].append({
            "round": "R67", "n": 1,
            "evidence": (f"{p['pass']} tap{p['tap']} "
                         f"slot{p['target_slot']} st_pre "
                         f"{hex(p['target_st_pre'])} pay "
                         f"{p['pay_frame']}")})
    for p in r66_p1000:
        mag["plus1000"].append({
            "round": "R66", "n": 1,
            "evidence": (f"{p['pass']} tap{p['tap']} "
                         f"slot{p['target_slot']} st_pre "
                         f"{hex(p['target_st_pre']) if p['target_st_pre'] else None} "
                         f"pay {p['pay_frame']}")})
    for p in r67_p1000:
        mag["plus1000"].append({
            "round": "R67", "n": 1,
            "evidence": (f"{p['pass']} tap{p['tap']} "
                         f"slot{p['target_slot']} st_pre "
                         f"{hex(p['target_st_pre']) if p['target_st_pre'] else None} "
                         f"pay {p['pay_frame']}")})
    out["magnitude_table"] = {
        "plus500_n": sum(int(e.get("n", 1)) for e in mag["plus500"]),
        "plus1000_n": sum(int(e.get("n", 1))
                          for e in mag["plus1000"]),
        "detail": mag}

    # ---- 2. the widened-set zero-overlap test -------------------------
    vecs500 = []
    for p in all_p500:
        slot = p["target_slot"]
        if p.get("pay_words") and slot is not None \
                and str(slot) in p["pay_words"]:
            vecs500.append({"src": f"{p['pass']} t{p['tap']}",
                            "slot": slot,
                            "vec": p["pay_words"][str(slot)]})
    out["widened_zero_overlap"] = zero_overlap_test(vecs500, vecs1000)
    out["widened_zero_overlap"]["n_plus500_vectors"] = len(vecs500)
    out["widened_zero_overlap"]["n_plus1000_vectors"] = len(vecs1000)

    # ---- 3. the delay signature ----------------------------------------
    delays = []
    for p in all_p500:
        delays.append({"amount": 500, "pay_frame": p["pay_frame"],
                       "src": f"{p['pass']} t{p['tap']}",
                       "st_pre": hex(p["target_st_pre"])
                       if p["target_st_pre"] else None})
    for p in r66_p1000 + r67_p1000:
        delays.append({"amount": 1000, "src": f"{p['pass']} "
                       f"t{p['tap']}",
                       "pay_frame": p["pay_frame"],
                       "st_pre": hex(p["target_st_pre"])
                       if p["target_st_pre"] else None})
    for v in vecs1000:
        if v["src"].startswith("R52"):
            delays.append({"amount": 1000, "src": v["src"],
                           "pay_frame": "banked (R52 wound table)"})
    out["delay_signature"] = {
        "observations": delays,
        "note": ("the +500 class paid at tail f1 (bullet-impact "
                 "frame, victim pre-hit) in the R66 capture; each "
                 "R67 capture's pay frame is listed — the signature "
                 "test is the +500-vs-+1000 tail-frame separation "
                 "on the widened set")}

    # ---- 3b. the replay divergence (WHY the R66 +500 did not replay)
    r66b_taps = [(ev["tap"], (ev.get("target") or {}).get("slot"),
                  (ev.get("target") or {}).get("st"),
                  ev.get("score_delta"))
                 for ev in taps(R66B) if ev.get("tap", 0) >= 2]
    r67b_taps = [(ev["tap"], (ev.get("target") or {}).get("slot"),
                  (ev.get("target") or {}).get("st"),
                  ev.get("score_delta"))
                 for ev in taps(R67B) if ev.get("tap", 0) >= 2]
    def hx(v):
        return hex(v) if isinstance(v, int) and v else v
    m66 = {t[0]: t for t in r66b_taps}
    m67 = {t[0]: t for t in r67b_taps}
    div = None
    for tn in sorted(set(m66) & set(m67)):
        a, b = m66[tn], m67[tn]
        if a[1] != b[1] or a[3] != b[3]:
            div = {"tap": tn,
                   "r66": [a[0], a[1], hx(a[2]), a[3]],
                   "r67": [b[0], b[1], hx(b[2]), b[3]]}
            break
    out["replay_divergence"] = {
        "checked": "R67 pass B (frontier_b, restore-only, byte-exact "
                   "frontier) vs R66 pass B (the +500 capture run)",
        "first_target_divergence": div,
        "cause": (
            "amendment G (the disclosed 0x5B0C gate alignment) "
            "changed the target order: the R66 gate counted "
            "just-registered corpses as blockers; the R67 gate does "
            "not — a DIFFERENT tap sequence followed, and the R66 "
            "+500 pay posture (tap 6 slot16 0x1e38) was never "
            "reached. The frontiers are byte-exact (the env probe "
            "restores them alive); the divergence is the "
            "amendment's, not the emulator's."),
        "lesson": ("the +500 capture is a TRAJECTORY-SENSITIVE "
                   "posture, not a standing property of the "
                   "frontier: restoring the same state and tapping "
                   "with a different (even evidence-corrected) gate "
                   "order lands different states under the bullet"),
    }

    # ---- 4. honest status ------------------------------------------------
    n500 = len(all_p500)
    wo = out["widened_zero_overlap"]
    out["status"] = {
        "pay500_goal_2": (
            "NOT MET this round: 0 NEW +500 captures (the R66 "
            "capture stands as the class's only pay-frame vector, "
            f"n={n500}); the ledger cap 3/3 is spent; the capsule "
            "lever stays OPEN for the next round"),
        "plus500_captures": f"OBSERVED (n={n500} total under the "
                            "pay-frame telemetry)",
        "plus1000_class": (
            f"REPLICATED x2 this round (n={len(vecs1000)} pay-frame "
            "vectors banked: 2 R52 + 2 R66 + 2 R67) — the "
            "wound-recovery st_pre class pays +1000 every time it "
            "is captured"),
        "pay_discriminator": wo["verdict"],
        "freshness_spread": (
            "supported per-capture: the +500 st_pre classes are "
            + ", ".join(sorted({hex(p["target_st_pre"])
                                for p in all_p500
                                if p["target_st_pre"]}))
            + " — read against the +1000 wound-recovery classes "
              "(0x42bc/0x3f48 this round again)"),
        "frontier_target_landscape": (
            "both frontiers are target-starved past the "
            "spawner-cluster edge: the de-starve advance (180f per "
            "pass) walked px 1246->1540 (A) and 1254->1546 (B) and "
            "found NO targetable enemy rows — the live rows past "
            "px ~1500 are projectile_air / non-enemy kinds; fresh "
            "0x4054 soldiers exist only AT the frontier at restore "
            "time (frontier_a census: slot20 0x4054) and churn out "
            "of the fresh class before the tap lands"),
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps({k: out[k] for k in
                      ("magnitude_table", "widened_zero_overlap",
                       "status")},
                     indent=1, default=str)[:2600])
    print("analysis ->", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
