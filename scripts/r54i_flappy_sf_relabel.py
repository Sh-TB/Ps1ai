#!/usr/bin/env python3
"""r54i_flappy_sf_relabel.py — SAME-SENSOR relabeling (the flappy
breakthrough).

Diagnosis (r54 dagger traces): the full-res teacher's labels carry a
SENSOR MISMATCH vs the small-frame features the student consumes
(bird_y differs by up to 4-8px at the /4 scale) — in a game with a
~25px margin that noise alone kills the closed-loop student at the
first pipe. The small-frame teacher (FlappyTeacherAgent pathway) acts
on EXACTLY the features the student sees, so its (features, own-
history) -> action mapping is a DETERMINISTIC function — learnable to
saturation by BC, and its closed-loop ceiling is measured at 51/38/38/
34/34 pipes (r54g).

This script REPLAYS the small-frame teacher over every recorded frame
(no emulator; the frames are frozen in the datasets) and writes
relabeled episode copies into ds_flappy_sf / ds_flappy_sf_dagger:
  actions        <- the sf teacher's action (the BC target)
  teacher_actions<- the sf teacher's action (DAgger target = same)
  labels/frames  <- unchanged
Provenance: the relabel note records the sf-teacher law name.
"""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.dataset import EpisodeRecord           # noqa: E402
from ps1play.learn.teacher import FlappyTeacher           # noqa: E402
from ps1play.learn import visual_only as VO               # noqa: E402

OUT = os.path.join(REPO, "scratch", "r54")


def sf_relabel_episode(root, eid, dst_root, use_observer=False,
                       gc_bias=0.0):
    meta, npz = EpisodeRecord.load(root, eid)
    frames = npz["frames"]                  # (T,60,80,3) uint8
    n = meta["n_steps"]
    teacher = FlappyTeacher()
    teacher.reset_history()
    observer = VO.FlappyObserver() if use_observer else None
    prev = None
    sf_actions = []
    for i in range(n):
        cur = frames[i]
        if use_observer:
            by_o, vy_o = observer.step(cur, sf_actions[-1]
                                       if sf_actions else None)
            gc, _dx, _g0, _g1, _rb = VO._flappy_gap_raw(cur)
            gc_eff = (gc + gc_bias) if (gc is not None and gc >= 0) \
                else None
            act = teacher.act(by_o if by_o is not None else None,
                              vy_o, gc_eff)
        else:
            f = VO.features_flappy(cur, prev)
            by = f[0] if f[0] >= 0 else None
            gc = f[2] if f[2] >= 0 else None
            gc_eff = (gc + gc_bias) if (gc is not None and gc >= 0) \
                else None
            act = teacher.act(by, f[1], gc_eff)
        sf_actions.append(act)
        prev = cur
    rec = EpisodeRecord(
        game=meta["game"], mode=meta["mode"], episode_id=meta["episode_id"],
        scenario=meta["scenario"], field_table=meta["field_table"],
        frame_shape=meta["frame_shape"],
        note=(meta.get("note", "") +
              (" | sf-relabel+observer: flappy_teacher_v2_r15play "
               "driven by the FlappyObserver bird state (same-sensor "
               "labels, physics-integrated between trusted frames)"
               if use_observer else
               " | sf-relabel: flappy_teacher_v2_r15play on the SAME "
               "small-frame feature pathway (same-sensor labels)")))
    rec.frames = list(frames)
    rec.actions = sf_actions
    rec.teacher_actions = list(sf_actions)   # DAgger target = sf law
    rec.step_labels = json.loads(str(npz["labels_json"]))
    rec.events = meta.get("events", [])
    rec.outcome = dict(meta.get("outcome", {}))
    rec.outcome["label_source"] = (
        "flappy_teacher_sf_same_sensor_observer" if use_observer
        else "flappy_teacher_sf_same_sensor")
    meta_path = rec.freeze(dst_root)
    return meta_path, n, sf_actions.count("FLAP")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--observer", action="store_true")
    ap.add_argument("--gc-bias", type=float, default=0.0,
                    help="aim the gap target N px LOWER (compensates "
                         "the learned policy's flap-timing jitter)")
    ap.add_argument("--dst-suffix", default="")
    a = ap.parse_args()
    jobs = [
        (os.path.join(OUT, "ds_flappy_v2"),
         os.path.join(OUT, f"ds_flappy_sf{a.dst_suffix}")),
        (os.path.join(OUT, "ds_flappy_dagger_p4"),
         os.path.join(OUT, f"ds_flappy_sf_dagger{a.dst_suffix}")),
    ]
    for root, dst in jobs:
        os.makedirs(dst, exist_ok=True)
        eids = sorted(f[3:-5] for f in os.listdir(root)
                      if f.startswith("ep_") and f.endswith(".json"))
        tot_flap = 0
        for eid in eids:
            mp, n, nflap = sf_relabel_episode(root, eid, dst,
                                              use_observer=a.observer,
                                              gc_bias=a.gc_bias)
            tot_flap += nflap
            print(f"{dst.split('/')[-1]}/{eid} n={n} flaps={nflap}",
                  flush=True)
        print(f"-> {dst}: {len(eids)} episodes, {tot_flap} flap labels")


if __name__ == "__main__":
    main()
