#!/usr/bin/env python3
"""r61_restore_tb_manifest.py — R61 Section 0 (baseline restoration).

The R57 teacher-bootstrap cutoff manifest lived ONLY in untracked scratch
(`scratch/r57/tb_manifest.json`) and was lost with the sandbox recycle.
Its authoritative content is committed (`r57_bootstrap_dataset.npz.json`:
per-episode cutoff_step / row counts / the cap rule / cutoff_proof=true).

This script deterministically reconstructs the scratch manifest FROM THE
COMMITTED RECORD so the R57 manifest tests verify committed data instead
of skipping. Every episode maps as:
  result  = "cutoff"  if cutoff_step is not None else "death"
  passages = 20 for cutoff episodes (the cap; the 20th passage fired on
             the cutoff step, whose own action is excluded from rows) or
            max_passed_pipe_count_in_rows for deaths (< 20)
  n_labels = n_rows (rows are the labels; the cutoff step's own action
             excluded -> n_rows == cutoff_step for cutoff episodes)
The reconstruction asserts every invariant the R57 tests enforce before
writing anything.
"""
import json
import os
import sys

REPO = "/home/z/my-project/ps1ai"
DS_META = os.path.join(REPO, "data", "learn",
                       "r57_bootstrap_dataset.npz.json")
OUT = os.path.join(REPO, "scratch", "r57", "tb_manifest.json")


def main():
    d = json.load(open(DS_META))
    assert d["cutoff_proof"] is True
    assert d["cap_rule"].startswith("no teacher action beyond the first 20")
    eps = []
    for e in d["episodes"]:
        cut = e.get("cutoff_step")
        if cut is not None:
            assert e["n_rows"] == cut, e
            res, passages = "cutoff", 20
        else:
            res, passages = "death", int(e["max_passed_pipe_count_in_rows"])
            assert passages < 20, e
        eps.append({
            "episode_id": e["episode_id"],
            "k": e["k"],
            "result": res,
            "passages": passages,
            "n_labels": int(e["n_rows"]),
            "cutoff_step": cut,
            "npz_sha256": e["npz_sha256"],
            "restored_from": "r57_bootstrap_dataset.npz.json",
        })
    n_cut = sum(1 for x in eps if x["result"] == "cutoff")
    assert n_cut >= 5, n_cut  # the mission required >=5 capped episodes
    m = {
        "cap_pipes": 20,
        "cutoff_proof": True,
        "source": ("restored deterministically from the committed "
                   "r57_bootstrap_dataset.npz.json (scratch original "
                   "lost in the 2026-10-31 sandbox recycle); R61 "
                   "Section 0"),
        "episodes": eps,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(m, f, indent=1)
    print("wrote", OUT, "episodes:", len(eps), "cutoff:", n_cut,
          "deaths:", len(eps) - n_cut)


if __name__ == "__main__":
    sys.exit(main())
