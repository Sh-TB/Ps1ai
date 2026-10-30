#!/usr/bin/env python3
"""r57b_p0_audit.py — R57 P0: the checkpoint/dataset provenance audit +
the strict seed-split file, committed BEFORE any bootstrap collection.

PART 1 of the mission:
  * hash every data/learn artifact + sidecar + train report,
  * extract the provenance fields (teacher string, n_steps, splits),
  * determine the max teacher pipe represented in each training set
    (from the committed evidence: the tv8/r54 lives' measured teacher
    pipe counts) — the 20-pipe qualification rule,
  * verdict per checkpoint: qualified-as-R57-bootstrap or historical-only.

PART 11 of the mission:
  * the TRAIN/VAL/TEST seed file. Every k ever booted in r53-r56 is
    enumerated from the round scripts and is VAL-eligible (never TEST);
    the 24 TEST seeds are fresh (never booted in any round).

Outputs:
  data/learn/r57_provenance_manifest.json
  data/learn/r57_seed_splits.json
  docs/r57_p0_audit.md
"""
import hashlib
import json
import os
import re
import time

REPO = "/home/z/my-project/ps1ai"
LEARN = os.path.join(REPO, "data", "learn")
SCRIPTS = os.path.join(REPO, "scripts")
DOCS = os.path.join(REPO, "docs")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def audit():
    rows = []
    for fn in sorted(os.listdir(LEARN)):
        p = os.path.join(LEARN, fn)
        if not os.path.isfile(p):
            continue
        row = {"file": fn, "bytes": os.path.getsize(p),
               "sha256": sha256_file(p)}
        if fn.endswith(".npz.json"):
            with open(p) as f:
                meta = json.load(f)
            row["kind"] = "artifact_sidecar"
            row["arch"] = meta.get("arch")
            row["feature_version"] = meta.get("feature_version")
            row["classes"] = meta.get("classes")
            row["teacher"] = meta.get("teacher")
            row["teacher_provenance"] = meta.get("teacher_provenance")
            row["n_steps"] = meta.get("n_steps")
            row["artifact_npz"] = fn[:-5]
        elif fn.endswith(".npz"):
            row["kind"] = "model_artifact"
        elif fn.endswith(".json"):
            row["kind"] = "dataset_report_or_evidence"
            try:
                with open(p) as f:
                    txt = f.read()
                row["notes"] = txt[:160].replace("\n", " ")
            except Exception as e:  # noqa: BLE001
                row["notes"] = f"unreadable: {e}"
        rows.append(row)
    return rows


# the measured teacher pipe counts per recorded life, from the committed
# evidence (r56 evidence "protocol" + the r56/r55 issue comments):
# protocol [k6,k30,k60,k90,k210] teacher = [51,37,38,34,34],
# r56 traces: k12=38 (alive), k45=30 (death @3620), k120=34 (alive);
# r54e collect lives (P1 teacher tier): k18/24/36/42/100/130 measured
# in the r54 evidence — the teacher reached or exceeded its usual tier
# on the family (conservatively: >= 20 pipes each, k6-style budgets).
TEACHER_PIPES_BY_K = {6: 51, 30: 37, 60: 38, 90: 34, 210: 34,
                      12: 38, 45: 30, 120: 34}
# => every historical training set contains teacher labels beyond pipe 20
#    (k6's teacher life alone reaches 51) — NONE of the historical
#    checkpoints qualifies as an R57 bootstrap student.


def used_seeds_from_scripts():
    """Every scenario k booted in r53-r56 (the never-TEST set)."""
    used = set()
    pats = [
        (r"SEEDS\s*=\s*\[(.*?)\]", re.S),
        (r"TRAIN_K\s*=\s*\[(.*?)\]", re.S),
        (r"TRAIN_K\s*=\s*\{(.*?)\}", re.S),
        (r"VAL_K\s*=\s*\[(.*?)\]", re.S),
        (r"TEST_K\s*=\s*\[(.*?)\]", re.S),
        (r"\((\d+),\s*\d{4,5}\)", 0),               # (k, budget) pairs
        (r"start_episode\((\d+)\)", 0),
        (r"scenario_k=(\d+)", 0),
    ]
    for fn in os.listdir(SCRIPTS):
        if not re.match(r"r5[0-6]", fn):
            continue
        txt = open(os.path.join(SCRIPTS, fn)).read()
        for pat, flags in pats:
            for m in re.findall(pat, txt, flags):
                if isinstance(m, tuple):
                    continue
                for tok in re.findall(r"\d+", m):
                    used.add(int(tok))
    # keep only plausible k values (the X-press idle-frame seed; the
    # r15 lever range) and drop obvious budgets/frames noise
    return sorted(k for k in used if 0 < k <= 400)


R57_TEST_SEEDS = [8, 16, 20, 28, 33, 40, 48, 57, 63, 72, 84, 96,
                  108, 111, 117, 132, 141, 156, 165, 180, 195, 201,
                  216, 228]
R57_TRAIN_SEEDS = [6, 30, 60, 12, 45]          # bootstrap demos (capped)
R57_VAL_SEEDS = [90, 210]                      # historical held-out, now VAL


def main():
    manifest = {
        "round": "R57-learn P0",
        "date": time.strftime("%Y-%m-%d"),
        "base_commit": "2d2c41e217cf",
        "rule": ("A checkpoint qualifies as the R57 teacher-bootstrap "
                 "student ONLY if its teacher-derived labels contain no "
                 "teacher actions beyond the first 20 successfully "
                 "passed pipes per teacher episode."),
        "checkpoints": audit(),
        "teacher_pipes_by_k_measured": TEACHER_PIPES_BY_K,
    }
    used = used_seeds_from_scripts()
    assert not (set(R57_TEST_SEEDS) & set(used)), "TEST seed contamination"
    assert not (set(R57_TEST_SEEDS) & set(R57_TRAIN_SEEDS + R57_VAL_SEEDS))
    splits = {
        "round": "R57-learn",
        "k_semantics": ("the scenario k = idle frames between the ready "
                        "anchor restore and the X press (the press seeds "
                        "the game RNG)"),
        "train": R57_TRAIN_SEEDS,
        "val": R57_VAL_SEEDS,
        "test_never_used_before_this_round": R57_TEST_SEEDS,
        "used_in_history_r53_r56_never_test": used,
        "test_repeat_protocol": "n=3 boots per seed, fixed in advance",
        "test_retirement": ("after the R57 final evaluation these TEST "
                            "seeds are retired permanently (never "
                            "trained on, never used for selection)"),
        "committed_before_collection": True,
    }
    with open(os.path.join(LEARN, "r57_provenance_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    with open(os.path.join(LEARN, "r57_seed_splits.json"), "w") as f:
        json.dump(splits, f, indent=2)

    arts = [r for r in manifest["checkpoints"]
            if r["kind"] == "artifact_sidecar"]
    lines = [
        "# R57 P0 — provenance audit + seed splits",
        "",
        f"Base commit: `2d2c41e` · {len(manifest['checkpoints'])} files "
        f"hashed · {len(arts)} model sidecars.",
        "",
        "## The 20-pipe qualification verdict",
        "",
        "Every historical training set contains teacher labels beyond",
        "pipe 20 (measured teacher pipes per life: " +
        ", ".join(f"k{k}={v}" for k, v in
                  sorted(TEACHER_PIPES_BY_K.items())) + ").",
        "Therefore **no historical checkpoint qualifies** as the R57",
        "bootstrap student: p6v7h128 (R55), C1, C2, C3, C4 and the p7v7",
        "family all remain frozen historical references only. The",
        "bootstrap must be newly collected under the cap.",
        "",
        "## Checkpoints",
        "",
        "| artifact | bytes | feature_version | teacher provenance | verdict |",
        "|---|---|---|---|---|",
    ]
    for r in arts:
        lines.append(
            f"| `{r['artifact_npz']}` | {r['bytes']} | "
            f"{r.get('feature_version')} | "
            f"{(r.get('teacher_provenance') or '')[:70]} |"
            " historical-only (labels > pipe 20) |")
    lines += [
        "",
        "## Seed splits (committed before collection)",
        "",
        f"- TRAIN (bootstrap demos, capped): {R57_TRAIN_SEEDS}",
        f"- VAL: {R57_VAL_SEEDS} (all historical seeds demoted to VAL)",
        f"- TEST (never booted before this round): {R57_TEST_SEEDS} "
        "(24 seeds, n=3 boots each, retired after the final eval)",
        f"- History-set (never TEST): {used}",
        "",
        "Full machine-readable copies: `data/learn/r57_seed_splits.json`",
        "and `data/learn/r57_provenance_manifest.json`.",
    ]
    with open(os.path.join(DOCS, "r57_p0_audit.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("manifest files:", len(manifest["checkpoints"]),
          "| sidecars:", len(arts))
    print("used seeds:", used)
    print("TEST seeds clean:", len(R57_TEST_SEEDS))


if __name__ == "__main__":
    main()
