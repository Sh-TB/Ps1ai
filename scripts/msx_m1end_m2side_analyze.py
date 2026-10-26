#!/usr/bin/env python3
"""msx_m1end_m2side_analyze.py — Issue #5 session-11 (round 8): the
diff-of-diffs over the M1-end vs M2-side RAM trackers recorded by
msx_m1end_m2side_diff.py (windows A-E, npz per-byte tracks).

Track format (per byte over the 2 MiB RAM image):
  val0    value at restore (frame 0)
  first_f first frame the byte changed (-1 = never)
  last_f  last change frame
  count   number of observed changes
  final   value at window end

Candidate families:
  SPAWN-EXCLUSIVE  changed in A (M2 live, spawn window f30-60) and in
                   NO other window (B/C/E M1-end ladders, D M1 live) —
                   bytes only the M2 spawn-in path writes.
  WORLD-EXCLUSIVE  changed in A after f60 (M2 world activity), never
                   elsewhere.
  LADDER-EXCLUSIVE changed in B/C/E (the M1-end ladder that never
                   spawns M2) but never in A/D — the re-arm machinery.
  DISCRIMINATOR    A.changed & A.final!=val0 & zero changes elsewhere —
                   stable M2-ness values after the spawn-in.

Known globals (from combat.py / e2e_policy_trial.py) are annotated with
signed distance.  Output: candidates JSON + readable MD in the round-8
scratch dir.  Read-only over the npz tracks; no emulator involvement.
"""
import json
import os
import sys

import numpy as np

SCRATCH = "/home/z/my-project/ps1ai/scratch/issue6_round8_msx"
OUT_JSON = os.path.join(SCRATCH, "candidates_r8.json")
OUT_MD = os.path.join(SCRATCH, "candidates_r8.md")

KNOWN = {
    "PLAYER_X": 0x0CA2E0,
    "PLAYER_HP": 0x0CA2F6,
    "GRENADES": 0x0EDCF4,
    "SECTION_PROGRESS": 0x0EB5D4,
    "SECTION_STATE": 0x0EB5F4,
    "SECTION_FLAGS": 0x0EB5F6,
    "A_SCORE": 0x0EE318,
    "FLAGS_WORD": 0x0EE518,
}

# window specs: (npz path, label, spawn_hi_frame or None)
WINDOWS = {
    "A": (os.path.join(SCRATCH, "diff2_074813_trkA.npz"),
          "m2_live (restore m2_train, ride +505.6px)", 60),
    "B": (os.path.join(SCRATCH, "diff2_074813_trkB.npz"),
          "m1end_quiet (ladder, no spawn)", None),
    "C": (os.path.join(SCRATCH, "diff2_074813_trkC.npz"),
          "m1end_accept (2 START taps, endzone trap, no spawn)", None),
    "D": (os.path.join(SCRATCH, "diff2_074813_trkD.npz"),
          "m1_live (M1 world from issue5_m1_start)", None),
    "E": (os.path.join(SCRATCH, "diff3_075410_trkE.npz"),
          "m1end_long (7200f quiet watch -> attract world)", None),
}


def load(key):
    z = np.load(WINDOWS[key][0])
    return {k: z[k] for k in ("val0", "first_f", "last_f", "count", "final")}


def changed(t):
    return t["count"] > 0


def untouched(*ts):
    acc = np.zeros_like(ts[0]["count"], dtype=bool)
    for t in ts:
        acc |= changed(t)
    return ~acc


def u16_at(val0, final, off):
    return (int(val0[off]) | (int(val0[off + 1]) << 8),
            int(final[off]) | (int(final[off + 1]) << 8))


def u32_at(val0, final, off):
    a = b = 0
    for i in range(4):
        a |= int(val0[off + i]) << (8 * i)
        b |= int(final[off + i]) << (8 * i)
    return a, b


def near_known(off):
    best, bd = None, 1 << 60
    for name, addr in KNOWN.items():
        d = off - addr
        if abs(d) < abs(bd):
            best, bd = name, d
    return best, bd


def word_groups(mask, min_bytes=2):
    """Group candidate byte offsets into aligned u32 words with >=
    min_bytes candidate bytes."""
    idx = np.flatnonzero(mask)
    words = {}
    for i in idx:
        w = int(i) & ~3
        words.setdefault(w, []).append(int(i))
    return {w: v for w, v in words.items() if len(v) >= min_bytes}


def main():
    T = {k: load(k) for k in WINDOWS}
    log = lambda *a: print("[anl]", *a, file=sys.stderr, flush=True)

    untouched_others = untouched(T["B"], T["C"], T["D"], T["E"])

    spawn_win = (T["A"]["count"] > 0) & (T["A"]["first_f"] >= 30) \
        & (T["A"]["first_f"] <= WINDOWS["A"][2])
    world_win = (T["A"]["count"] > 0) & (T["A"]["first_f"] > WINDOWS["A"][2])

    spawn_excl = spawn_win & untouched_others
    world_excl = world_win & untouched_others
    a_any = changed(T["A"])
    ladder_any = changed(T["B"]) | changed(T["C"]) | changed(T["E"])
    ladder_excl = ladder_any & ~a_any & ~changed(T["D"])
    discriminator = a_any & (T["A"]["final"] != T["A"]["val0"]) \
        & untouched_others

    log(f"spawn_excl bytes: {int(spawn_excl.sum())}")
    log(f"world_excl bytes: {int(world_excl.sum())}")
    log(f"ladder_excl bytes: {int(ladder_excl.sum())}")
    log(f"discriminator bytes: {int(discriminator.sum())}")

    fams = {"spawn_exclusive": spawn_excl, "world_exclusive": world_excl,
            "ladder_exclusive": ladder_excl, "discriminator": discriminator}

    out = {"windows": {k: {"label": WINDOWS[k][1],
                           "changed_bytes": int(changed(T[k]).sum())}
                       for k in WINDOWS},
           "families": {}}

    for fam, mask in fams.items():
        words = word_groups(mask)
        rows = []
        for w in sorted(words):
            nb = words[w]
            v0_32, f_32 = u32_at(T["A"]["val0"], T["A"]["final"], w)
            v0_16, f_16 = u16_at(T["A"]["val0"], T["A"]["final"], w)
            name, dist = near_known(w)
            firsts = [int(T["A"]["first_f"][o]) for o in nb]
            u8s = [(int(T["A"]["val0"][o]), int(T["A"]["final"][o]))
                   for o in nb]
            rows.append({
                "word": f"0x{w:06X}", "nbytes": len(nb),
                "val0_u32": v0_32, "final_u32": f_32,
                "val0_u16": v0_16, "final_u16": f_16,
                "u8": u8s,
                "first_f": min(firsts) if firsts else None,
                "near": name, "dist": dist,
            })
        # rank: near known globals first, then early spawn frames
        rows.sort(key=lambda r: (abs(r["dist"]), r["first_f"] or 10**9))
        out["families"][fam] = {"n_bytes": int(mask.sum()),
                                "n_words": len(rows), "top": rows[:40]}
        log(f"{fam}: {int(mask.sum())} bytes in {len(rows)} words")

    # small-value hunt: u16 transitions 0..0x3f -> 0..0x3f, val0 != final,
    # in spawn_exclusive + discriminator families (mission-index shape)
    small = []
    for fam in ("spawn_exclusive", "discriminator"):
        words2 = word_groups(fams[fam], min_bytes=1)
        for w in sorted(words2):
            for o in words2[w]:
                v0, f1 = u16_at(T["A"]["val0"], T["A"]["final"], o & ~1)
                if v0 != f1 and v0 <= 0x3F and f1 <= 0x3F:
                    name, dist = near_known(o & ~1)
                    small.append({"addr": f"0x{o:06X}",
                                  "u16": f"{v0}->{f1}",
                                  "first_f": int(T["A"]["first_f"][o]),
                                  "near": name, "dist": dist, "fam": fam})
    small.sort(key=lambda r: (abs(r["dist"]), r["first_f"]))
    out["small_value_transitions"] = small
    log(f"small-value u16 transitions: {len(small)}")

    # stable-value table for the top discriminators (u16 view)
    disc = out["families"]["discriminator"]["top"]
    for r in disc[:20]:
        w = int(r["word"], 16)
        r["val0_u16"], r["final_u16"] = u16_at(T["A"]["val0"],
                                               T["A"]["final"], w)

    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=1)

    with open(OUT_MD, "w") as f:
        f.write("# M1-end vs M2-side diff-of-diffs (round 8)\n\n")
        for k, v in out["windows"].items():
            f.write(f"- window {k}: {v['label']} — "
                    f"{v['changed_bytes']} bytes changed\n")
        for fam, d in out["families"].items():
            f.write(f"\n## {fam}: {d['n_bytes']} bytes, "
                    f"{d['n_words']} aligned words\n\n")
            f.write("| word | nbytes | val0->final (u32) | first_f | "
                    "near | dist |\n|---|---|---|---|---|---|\n")
            for r in d["top"][:25]:
                f.write(f"| {r['word']} | {r['nbytes']} | "
                        f"{r['val0_u32']:08x}->{r['final_u32']:08x} | "
                        f"{r['first_f']} | {r['near']} | {r['dist']:+d} |\n")
    log(f"wrote {OUT_JSON} and {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
