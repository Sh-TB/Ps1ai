#!/usr/bin/env python3
"""msx_helicopter_ladder.py — 10-pattern chopper/mortar-rain survival
ladder from ONE pre-encounter checkpoint savestate (Issue #5).

USER DIRECTIVE (this task): web-research the MSX Mission-1 chopper
fight ("when the helicopter drops bombs you must move — standing still
kills you"), make ONE savestate ~1 second before the chopper/rain zone
so the level does not have to be replayed every time, then test 10
DIFFERENT movement patterns from that same savestate.

WEB SOURCES (researched before the run):
  * arcadequartermaster.com MS2 Mission 1: "focus all your fire on the
    red Masknell chopper: the entire squadron collapses with the
    demise of the red leader" -> attacking the SOURCE should quiet
    the rain.
  * Antstream Arcade guide: "R-Shobu - Enemy Chopper: drops bombs on
    the player. Fast and deadly"; Mission 1 boss tips say keep firing.
  * metalslug.fandom "Drifting in Desert": the mosque minarets hide
    launchers -> our instrumented non-tracking mortar 'rain' and the
    chopper are two distinct threat sources in the same zone.
  * Player consensus (r/metalslug): keep moving, learn the wave
    pattern; standing still is what kills you.

CHECKPOINT: player px inside the proven lob window [810, 868] px —
the rain corridor (fallers X 915..1067, twin-rotor chopper hover
~920-970, section clamp 1163) starts immediately ahead. The reach
reuses gif_story_run.phase_b verbatim: boot -> live-play gate ->
hp_pair_freeze EXPLORATION (disclosed in the trace) -> walk. The
checkpoint is saved ONCE; the 10 patterns then run UNFROZEN (no
CheatSession exists in the pattern phase — deaths are real).

PATTERNS (all from the same savestate, 60 fps):
  1 stand_in_corridor  walk to px>=950 then idle   (user control)
  2 walk_right         hold RIGHT                  (web: keep moving)
  3 patrol_tight       RIGHT 30f / LEFT 30f        (move in place)
  4 zigzag_forward     RIGHT 60f / LEFT 25f        (net-forward shuffle)
  5 hop_advance        RIGHT + 14f hop every 90f   (route cadence)
  6 run_to_wall_hold   RIGHT to px>=1150 then idle (wall + still)
  7 wall_upfire        RIGHT to px>=1100 then UP+LEFT+Y (protocol B)
  8 lob_grenades       A lob LEFT cycles at the window (mosque kill)
  9 retreat_left       LEFT to px<=600 then idle   (escape the zone)
  10 prone_in_corridor walk to px>=950 then DOWN   (classic MS prone)

Instrumentation per frame (READ-ONLY): player px, hp pair, flags,
score, grenades, bomb-faller census (slots whose 0x7E height word is
decreasing by 1..20/f with the RainLogger signature; near = |X-px|<80)
and zone entities (880<=X<=1100). Death = hp0==0 -> +60f anim -> the
pattern STOPS there (first-death endpoint, like a human attempt).

Phases:
  reach        boot + disclosed-assist walk + save `chopper_ckpt`
  run          load `chopper_ckpt`, run the requested patterns
  all          reach then every pattern
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np                                      # noqa: E402
from PIL import Image                                   # noqa: E402

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                           # noqa: E402
from ps1play.telemetry import JsonlTrace                # noqa: E402
from ps1play.agent.combat import scan_entities          # noqa: E402
from issue4_controller import boot                      # noqa: E402
import msx_gate_probe as gp                             # noqa: E402
import gif_story_run as story                           # noqa: E402

TABLE, STRIDE, SLOTS = gp.TABLE, gp.STRIDE, 40
PLAYER_X = 0x0CA2E0
A_FLAGS = 0x0EE518
A_SCORE = 0x0EE318
A_PAIR0, A_PAIR1 = 0x0CA2F6, 0x0CA2FE
GRENADES = 0x0EDCF4
CKPT = "chopper_ckpt"
KILL_LO, KILL_HI = 810.0, 868.0          # lob window (gif_story_run)
CORRIDOR_PX = 950.0                      # inside the faller corridor
WALL_PX = 1150.0                         # section clamp is 1163-1164

EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "heli_ladder")
os.makedirs(EVID, exist_ok=True)


def log(*a):
    print("[heli]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def flags_of(m):
    return int(m.u32(A_FLAGS)) & 0xFF


def png(p, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(EVID, name))


def _table_words(m):
    return m.ram[TABLE:TABLE + SLOTS * STRIDE].view("<u2").astype(
        np.int32).reshape(SLOTS, STRIDE // 2)


class FallerCensus:
    """Bomb-faller census with the w2 RainLogger signature: a slot is
    FALLING when its 0x7E height word drops 1..20/f while alive
    (hp != 0) above the ground band (h > 60, prev > 70)."""

    def __init__(self):
        self.prev_h = {}

    def poll(self, m, px):
        tv = _table_words(m)
        fall_total = fall_near = 0
        zone = []
        for s in range(1, SLOTS):
            xw = (int(tv[s, 61]) << 16) | int(tv[s, 60])
            h = int(tv[s, 63])
            hp = int(tv[s, 71])
            ph = self.prev_h.get(s)
            self.prev_h[s] = h
            if not xw:
                continue
            xpx = xw / 65536.0
            if hp and ph is not None and 0 < ph - h <= 20 and \
                    h > 60 and ph > 70:
                fall_total += 1
                if abs(xpx - px) < 80.0:
                    fall_near += 1
            if 880.0 <= xpx <= 1100.0 and hp:
                zone.append({"slot": s, "x": round(xpx, 1), "h": h,
                             "hp": hp})
        return {"fall_total": fall_total, "fall_near": fall_near,
                "zone": zone}


# ------------------------------------------------------------------
# the 10 patterns
# ------------------------------------------------------------------
def _pos_right(st, px, target, cap=600):
    """Shared positioning: hold RIGHT until target px (bounded)."""
    if st.get("pos_done"):
        return None
    if px >= target or st.get("walk_f", 0) >= cap:
        st["pos_done"] = True
        return None
    st["walk_f"] = st.get("walk_f", 0) + 1
    return {"RIGHT"}


def _pos_left(st, px, target, cap=600):
    if st.get("pos_done"):
        return None
    if px <= target or st.get("walk_f", 0) >= cap:
        st["pos_done"] = True
        return None
    st["walk_f"] = st.get("walk_f", 0) + 1
    return {"LEFT"}


PATTERNS = [
    ("01_stand_in_corridor", 1500,
     lambda i, px, st: (_pos_right(st, px, CORRIDOR_PX) or set())),
    ("02_walk_right", 1500, lambda i, px, st: {"RIGHT"}),
    ("03_patrol_tight", 1200,
     lambda i, px, st: {"RIGHT"} if (i // 30) % 2 == 0 else {"LEFT"}),
    ("04_zigzag_forward", 1500,
     lambda i, px, st: {"RIGHT"} if (i % 85) < 60 else {"LEFT"}),
    ("05_hop_advance", 1500,
     lambda i, px, st: ({"RIGHT", "B"} if (i % 90) < 14
                        else {"RIGHT"})),
    ("06_run_to_wall_hold", 1500,
     lambda i, px, st: (_pos_right(st, px, WALL_PX) or set())),
    ("07_wall_upfire", 1800,
     lambda i, px, st: (_pos_right(st, px, 1100.0) or
                        ({"UP", "LEFT", "Y"} if (i % 60) < 40
                         else {"UP", "LEFT"}))),
    ("08_lob_grenades", 1800,
     lambda i, px, st: ({"A"} if (i % 80) < 8 else
                        ({"LEFT"} if (i % 80) < 24 else set()))),
    ("09_retreat_left", 1500,
     lambda i, px, st: (_pos_left(st, px, 600.0) or set())),
    ("10_prone_in_corridor", 1500,
     lambda i, px, st: (_pos_right(st, px, CORRIDOR_PX) or {"DOWN"})),
]


# ------------------------------------------------------------------
def nudge_into_window(p, session, m):
    """After phase_b: position inside [810, 868] (lob window)."""
    for k in range(900):
        x = px_of(m)
        if KILL_LO <= x <= KILL_HI:
            return x
        btns = {"RIGHT"} if x < KILL_LO else {"LEFT"}
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
    return px_of(m)


def phase_reach(p):
    """boot -> disclosed-freeze walk to the window -> save checkpoint.
    Reuses gif_story_run.phase_b verbatim (proven flow, disclosed
    assist, grenade top-up included)."""
    trace = JsonlTrace(os.path.join(EVID, "reach_trace.jsonl"))
    evlog = JsonlTrace(os.path.join(EVID, "reach_highlights.jsonl"))
    cap = {"count": 0}
    t0 = time.time()
    trace.write({"type": "reach_start",
                 "assist": "hp_pair_freeze EXPLORATION (disclosed) "
                           "for REACH ONLY; patterns run UNFROZEN"})
    rb, sess = story.phase_b(p, 0, trace, evlog, EVID, 0, cap, EVID)
    x = nudge_into_window(p, sess, p.mem)
    px = px_of(p.mem)
    gren = int(p.mem.u8(GRENADES))
    hp = int(p.mem.u16(A_PAIR0))
    p.save_state(CKPT)
    gp.unfreeze(sess, "heli_reach")
    png(p, "checkpoint.png")
    rec = {"type": "checkpoint_saved", "state": CKPT,
           "px": round(px, 1), "window_x": round(x, 1),
           "grenades": gren, "hp0": hp,
           "flags_active": flags_of(p.mem) == 0xFF,
           "frame": p.core.frames_run,
           "wall_s": round(time.time() - t0, 1),
           "phase_b_report": rb}
    trace.write(rec)
    trace.close()
    evlog.close()
    log("checkpoint saved:", json.dumps({k: rec[k] for k in
        ("state", "px", "grenades", "hp0", "flags_active")}))
    return rec


def run_pattern(p, idx, name, budget, ctrl):
    """One UNFROZEN pattern attempt from the checkpoint savestate."""
    m = p.mem
    p.load_state(CKPT)
    for _ in range(2):                    # settle (post-load engage)
        p.core.run_frame()
    census = FallerCensus()
    jpath = os.path.join(EVID, f"pattern_{name}.jsonl")
    jf = open(jpath, "w")
    gdir = os.path.join(EVID, "gif", name)
    os.makedirs(gdir, exist_ok=True)
    st = {}
    px0 = px_of(m)
    hp0v = int(m.u16(A_PAIR0))
    score0 = int(m.u32(A_SCORE))
    gren0 = int(m.u8(GRENADES))
    if flags_of(m) != 0xFF:
        jf.close()
        return {"pattern": name, "skipped": True,
                "reason": f"flags={flags_of(m):#x} not active"}
    t0 = time.time()
    last_hp = hp0v
    damage = []                           # (frame, delta, fall_near)
    death = None
    max_px = min_px = px0
    max_fall_total = 0
    fall_hist = []
    f0 = p.core.frames_run
    for i in range(budget):
        px = px_of(m)
        btns = ctrl(i, px, st) or set()
        p.core.set_buttons(btns)
        p.core.run_frame()
        c = census.poll(m, px)
        max_px = max(max_px, px)
        min_px = min(min_px, px)
        max_fall_total = max(max_fall_total, c["fall_total"])
        fall_hist.append(c["fall_total"])
        hp = int(m.u16(A_PAIR0))
        row = {"f": i, "px": round(px, 1), "hp0": hp,
               "hp1": int(m.u16(A_PAIR1)),
               "flags": flags_of(m),
               "score": int(m.u32(A_SCORE)),
               "gren": int(m.u8(GRENADES)),
               "fall_total": c["fall_total"],
               "fall_near": c["fall_near"],
               "n_zone": len(c["zone"]),
               "btns": sorted(btns)}
        if hp < last_hp:
            damage.append({"f": i, "delta": last_hp - hp,
                           "fall_near": c["fall_near"],
                           "px": round(px, 1)})
        last_hp = hp
        jf.write(json.dumps(row) + "\n")
        if i % 12 == 0:
            rgb = p.core.frame_rgb()
            if rgb is not None:
                Image.fromarray(rgb).save(
                    os.path.join(gdir, f"f{i:05d}.jpg"),
                    "JPEG", quality=80)
        if i % 150 == 0:
            png(p, f"pat{name}_f{i:04d}.png")
        if hp == 0 or row["flags"] == 0x1:
            death = {"frame": i, "px": round(px_of(m), 1),
                     "trigger": "hp_zero" if hp == 0
                     else "game_over_screen",
                     "geometry": scan_entities(m, px=px_of(m)),
                     "zone": c["zone"]}
            for k in range(60):           # death animation tail
                p.core.set_buttons(set())
                p.core.run_frame()
                if k in (20, 40):
                    png(p, f"pat{name}_death_{k:02d}.png")
            break
    jf.close()
    n = len(fall_hist)
    third = max(n // 3, 1)
    rep = {"pattern": name, "index": idx,
           "budget": budget,
           "frames_run": i + 1,
           "start_px": round(px0, 1), "end_px": round(px_of(m), 1),
           "max_px": round(max_px, 1), "min_px": round(min_px, 1),
           "hp_start": hp0v, "hp_end": last_hp,
           "died": death is not None,
           "death": death,
           "n_damage_events": len(damage),
           "damage": damage,
           "score_start": score0,
           "score_end": int(m.u32(A_SCORE)),
           "score_delta": int(m.u32(A_SCORE)) - score0,
           "grenades_start": gren0,
           "grenades_end": int(m.u8(GRENADES)),
           "max_fall_total": max_fall_total,
           "fall_rate_first_third": round(
               sum(fall_hist[:third]) / third, 3),
           "fall_rate_last_third": round(
               sum(fall_hist[-third:]) / third, 3),
           "wall_s": round(time.time() - t0, 1),
           "jsonl": jpath}
    png(p, f"pat{name}_end.png")
    with open(os.path.join(EVID, f"report_{name}.json"), "w") as f:
        json.dump(rep, f, indent=1)
    # GIF (5 fps from the 12f stride capture)
    try:
        frames = sorted(os.listdir(gdir))
        if len(frames) >= 4:
            ims = [Image.open(os.path.join(gdir, f)).convert("P",
                   palette=Image.ADAPTIVE) for f in frames]
            ims[0].save(os.path.join(EVID, f"pat_{name}.gif"),
                        save_all=True, append_images=ims[1:],
                        duration=200, loop=0)
            rep["gif"] = f"pat_{name}.gif"
    except Exception as e:                     # noqa: BLE001
        rep["gif_error"] = repr(e)[:120]
    with open(os.path.join(EVID, f"report_{name}.json"), "w") as f:
        json.dump(rep, f, indent=1)
    log(f"pattern {name}: died={rep['died']} "
        f"frames={rep['frames_run']} hp {hp0v}->{last_hp} "
        f"px {round(px0)}->{rep['end_px']} dmg={len(damage)} "
        f"score {score0}->{rep['score_end']}")
    return rep


def phase_run(p, wanted):
    out = []
    for idx, (name, budget, ctrl) in enumerate(PATTERNS):
        if wanted and idx + 1 not in wanted:
            continue
        out.append(run_pattern(p, idx + 1, name, budget, ctrl))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=("reach", "run", "all"),
                    default="all")
    ap.add_argument("--patterns", default="",
                    help="comma list like 1,2,7 for --phase run")
    args = ap.parse_args()
    wanted = [int(x) for x in args.patterns.split(",") if x.strip()]
    p, fwmode = boot()
    report = {"schema": "ps1play-heli-ladder/1",
              "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
              "firmware_mode": fwmode, "checkpoint": CKPT}
    if args.phase in ("reach", "all"):
        report["reach"] = phase_reach(p)
    if args.phase in ("run", "all"):
        report["patterns"] = phase_run(p, wanted)
    with open(os.path.join(
            EVID, f"ladder_report_{args.phase}"
            f"{'_' + args.patterns.replace(',', '-') if wanted else ''}"
            ".json"), "w") as f:
        json.dump(report, f, indent=1)
    log("done:", os.path.join(EVID, "ladder_report"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
