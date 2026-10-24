#!/usr/bin/env python3
"""truck_plugin_verify.py — matched gameplay trials of the PLUGIN-level
truck kill: the decisions come from ps1play.agent.combat (find_truck +
truck_kill_segments), not from the ad-hoc experiment scripts.

Per rep (fresh process, H5): boot -> load chopper-free engage anchor ->
policy loop: scan_entities -> find_truck -> truck_kill_segments ->
run segments verbatim -> verify hp_a4 300->0 + score.

Usage: python3 scripts/truck_plugin_verify.py --rep 1
"""
import argparse, json, os, sys, time
import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig
from issue4_controller import boot
import ps1play.agent.combat as combat

A_SCORE = 0x0EE318
ENGAGE = "truck_engage"
EVID = os.path.join(labconfig.resolve_path("evidence_dir"), "issue5_truck")


def log(*a):
    print("[pv]", *a, file=sys.stderr, flush=True)


def snap(m):
    return {"px": round(int(m.u32(combat.PLAYER_X)) / 65536.0, 1),
            "score": int(m.u32(A_SCORE)),
            "flags": int(m.u32(0x0EE518)) & 0xFF,
            "sec_state": int(m.u16(combat.SECTION_STATE)),
            "sec_flags": int(m.u16(combat.SECTION_FLAGS))}


def png(p, name, tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(EVID, f"{tag}_{name}.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rep", type=int, default=1)
    args = ap.parse_args()
    tag = f"plugin_rep{args.rep}"
    os.makedirs(os.path.join(EVID, tag), exist_ok=True)
    jf = open(os.path.join(EVID, tag, "trace.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    p.load_state(ENGAGE)
    for _ in range(3):
        p.core.run_frame()
    s0 = snap(m)
    J({"ev": "start", "snap": s0})
    log(f"rep{args.rep} start {s0}")
    png(p, "start", tag)

    phase = None
    done = False
    hp_track = []
    steps = 0
    f0 = p.core.frames_run
    while not done and steps < 80 and p.core.frames_run - f0 < 4800:
        steps += 1
        px = int(m.u32(combat.PLAYER_X)) / 65536.0
        ents = combat.scan_entities(m, px=px)
        truck = combat.find_truck(ents)
        ammo = 10 - hp_track.count("thrown") if False else None
        # ammo from the game's own counter (0x0EDCF4)
        gren = int(m.u8(0x0EDCF4))
        segs, phase, done = combat.truck_kill_segments(
            px, truck, gren, phase)
        hp_track.append(truck["hp_a4"] if truck else 0)
        J({"ev": "step", "step": steps, "px": round(px, 1),
           "gren": gren, "truck_hp_a4": truck["hp_a4"] if truck else None,
           "phase": phase, "segs": segs, "done": done,
           "score": snap(m)["score"]})
        if done:
            break
        if not segs:
            break
        if snap(m)["flags"] != 0xFF:
            J({"ev": "death", "step": steps, "snap": snap(m)})
            break
        for seg in segs:
            p.core.run(seg["frames"], seg["btns"] or set())

    fin = snap(m)
    trk = combat.find_truck(combat.scan_entities(
        m, px=int(m.u32(combat.PLAYER_X)) / 65536.0))
    killed = (trk is None or trk["hp_a4"] <= 0) and \
        any(h and h < 300 for h in hp_track)
    res = {"rep": args.rep, "killed": killed, "hp_track": hp_track,
           "steps": steps, "final": fin,
           "grenades_left": int(m.u8(0x0EDCF4)),
           "wall_s": round(time.time() - t0, 1),
           "frames": p.core.frames_run - f0}
    with open(os.path.join(EVID, tag, "report.json"), "w") as f:
        json.dump(res, f, indent=1)
    jf.close()
    png(p, "end", tag)
    log(f"rep{args.rep} DONE killed={killed} hp_track={hp_track} "
        f"final={json.dumps(fin)}")


if __name__ == "__main__":
    main()
