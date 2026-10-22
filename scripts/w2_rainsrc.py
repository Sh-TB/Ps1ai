#!/usr/bin/env python3
"""w2_rainsrc.py — Probe (a): WHERE do the falling-mortar transients
spawn? (Issue #5 focused follow-up, next-experiment part 1)

Prior evidence (2d19f41 report):
  * falling mortars = transient entity slots: HP field is a LIFETIME
    counter (204..254 -> 0), +0x7A word DECREASES as the object falls
  * grenade barrage destroyed the mosque (+800) but the rain continued
  * vulcan vs the visible twin-rotor = zero HP-word deltas (bullet-
    damage proof only)

This probe answers the ORIGIN question mechanically:
  1. boot -> load `arena2` (gate-locked, real play) -> re-freeze pair
  2. scan entity slots 1..39 every 2 frames for ~1400 frames
  3. on a NEW transient (slot idle -> occupied with lifetime-style HP):
     dump ALL u16 words of the record (spawn snapshot) + track it to
     death (hp/w78/w7a series)
  4. aggregate: per word-offset, the ACROSS-SPAWN spread -> a word that
     is near-constant across spawns at a plausible screen range is the
     ORIGIN marker (mosque vs truck vs chopper vs off-screen)
  5. guard: if prog drops (<100, respawn pulled the camera back),
     reload `arena2` and continue (observation stays inside the arena)

EXPLORATION DISCLOSURE: hp_pair freeze active after every load.
"""
from __future__ import annotations

import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import msx_gate_probe as gp                     # noqa: E402

EVID = gp.EVID
TABLE, STRIDE, HP_OFF = gp.TABLE, gp.STRIDE, gp.HP_OFF
A_PROGRESS = gp.A_PROGRESS
NW = 0xB0 // 2                  # u16 words per record dumped at spawn


class SlotTracker:
    """Per-slot generation tracking: idle -> occupied(lifetime) = spawn."""
    def __init__(self, mem):
        self.m = mem
        self.gen = {s: 0 for s in range(SLOTS_N)}
        self.prev_hp = {}
        self.tracking = {}      # slot -> {"t0":frame, "samples":[...]}

    def scan(self, frame):
        events = []
        for s in range(1, SLOTS_N):
            hp = self.m.u16(TABLE + s * STRIDE + HP_OFF)
            prev = self.prev_hp.get(s, 0)
            if prev == 0 and hp > 0:
                self.gen[s] += 1
                self.tracking[s] = {"t0": frame, "gen": self.gen[s],
                                    "spawn_words": self._words(s),
                                    "series": []}
                events.append(("spawn", s, frame, hp))
            elif prev > 0 and hp == 0 and s in self.tracking:
                self.tracking[s]["end"] = frame
                events.append(("death", s, frame, 0))
            self.prev_hp[s] = hp
        return events

    def sample(self, frame):
        out = []
        for s, tr in self.tracking.items():
            if "end" in tr:
                continue
            hp = self.m.u16(TABLE + s * STRIDE + HP_OFF)
            tr["series"].append(
                [frame - tr["t0"], hp,
                 self.m.u16(TABLE + s * STRIDE + 0x78),
                 self.m.u16(TABLE + s * STRIDE + 0x7A),
                 self.m.u16(TABLE + s * STRIDE + 0xA0),
                 self.m.u16(TABLE + s * STRIDE + 0xA4)])
            out.append(s)
        return out

    def _words(self, s):
        base = TABLE + s * STRIDE
        return [self.m.u16(base + 2 * i) for i in range(NW)]


SLOTS_N = 40


def main(total_frames=1400, sample_every=2):
    t0 = time.time()
    p, fw = gp.boot()
    m = p.mem
    try:
        p.load_state("arena2")
        src = "arena2"
    except Exception:                            # noqa: BLE001
        p.load_state("arena")
        src = "arena"
    gp.log(f"loaded `{src}`")
    session = gp.freeze_now(p, "w2_rainsrc")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()

    # initial table (who is already alive: player/truck/chopper/soldiers)
    init = {}
    for s in range(SLOTS_N):
        base = TABLE + s * STRIDE
        init[s] = {"hp": m.u16(base + HP_OFF),
                   "w78": m.u16(base + 0x78),
                   "w7a": m.u16(base + 0x7A),
                   "a0": m.u16(base + 0xA0),
                   "a4": m.u16(base + 0xA4)}
    gp.log("initial slots (nonzero hp): " + json.dumps(
        {str(s): v for s, v in init.items() if v["hp"]}))
    gp.png(p, "w2_rainsrc_start.png")

    tr = SlotTracker(m)
    # prime prev_hp so already-alive slots are not "spawns"
    for s in range(SLOTS_N):
        tr.prev_hp[s] = m.u16(TABLE + s * STRIDE + HP_OFF)

    jsonl_path = os.path.join(EVID, "w2_rainsrc_events.jsonl")
    out = open(jsonl_path, "w")
    reloads = 0
    frame = 0
    RELOAD_EVERY = 400          # bounded windows from the same state;
    while frame < total_frames:  # deaths/respawns cannot poison >400f
        if frame and frame % RELOAD_EVERY == 0:
            p.load_state(src)
            session = gp.freeze_now(p, "w2_rainsrc_re")
            for _ in range(2):
                p.core.run_frame()
                session.gs.tick()
            tr = SlotTracker(m)
            for s in range(SLOTS_N):
                tr.prev_hp[s] = m.u16(TABLE + s * STRIDE + HP_OFF)
            reloads += 1
            gp.log(f"f{frame}: window reload #{reloads}")
        evs = tr.scan(frame)
        for kind, s, fr, hp in evs:
            rec = {"kind": kind, "slot": s, "frame": fr, "hp": hp}
            if kind == "spawn":
                rec["spawn_words"] = tr.tracking[s]["spawn_words"]
            out.write(json.dumps(rec) + "\n")
        alive = tr.sample(frame)
        for s in alive:
            out.write(json.dumps({
                "kind": "track", "slot": s, "frame": frame,
                "rel": frame - tr.tracking[s]["t0"],
                "hp": tr.tracking[s]["series"][-1][1],
                "w78": tr.tracking[s]["series"][-1][2],
                "w7a": tr.tracking[s]["series"][-1][3],
                "a0": tr.tracking[s]["series"][-1][4],
                "a4": tr.tracking[s]["series"][-1][5]}) + "\n")
        p.core.set_buttons(set())
        p.core.run_frame()
        session.gs.tick()
        frame += 1
        if frame % sample_every:
            continue
        if frame % 200 == 0:
            gp.png(p, f"w2_rainsrc_f{frame:05d}.png")
            gp.log(f"f{frame} prog={m.u16(A_PROGRESS)} "
                   f"tracking={len(tr.tracking)}")

    out.close()
    gp.unfreeze(session, "w2_rainsrc")
    gp.png(p, "w2_rainsrc_end.png")
    summary = {"source_state": src, "frames": total_frames,
               "reloads": reloads,
               "spawns": sum(1 for s in tr.tracking.values()
                             if "t0" in s),
               "wall_s": round(time.time() - t0, 1)}
    json.dump(summary, open(os.path.join(EVID, "w2_rainsrc.json"), "w"),
              indent=1)
    gp.log("done:", json.dumps(summary))


if __name__ == "__main__":
    main()
