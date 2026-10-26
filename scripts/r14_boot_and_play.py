#!/usr/bin/env python3
"""r14_boot_and_play.py — THE REAL GAMEPLAY RUN for psxBreakout.

One boot of breakout_cont.cue (stage-1 spin-flag loader at extent 24).
Phases:
  A. boot -> detect stage-1 spin (code@0x80180000, FLAG==0)
  B. harness stages cs50x.exe[0x800:] (77824 B) to 0x80010000, sets
     FLAG=1 -> stage-1 jumps to the game's own pc0 (unmodified)
  C. game-live verify: map-anchored sensors (ballX/ballY/playerX/
     lives/level/motion/bricksCounter/gameWon), pad driver, screen
  D. input causality: LEFT/RIGHT move playerX; CROSS launches
  E. REAL PLAY: closed-loop servo — predict the ball's landing x every
     frame, steer the paddle (LEFT/RIGHT, CIRCLE=speed3) to intercept,
     relaunch after every level transition, play through all 3 levels
     to the gameWon=1 pulse. Captures EVERY frame for the GIF.
Evidence -> scratch/round14_breakout/play/. No RAM writes except the
documented payload staging + flag (the boot workaround).
"""
import ctypes
import json
import os
import shutil
import sys
import time

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                          # noqa: E402
from PIL import Image                                       # noqa: E402
from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                             # noqa: E402

EMU = "/home/z/my-project/emu/games_homebrew"
CUE = os.path.join(EMU, "patched", "breakout_cont.cue")
WS = os.path.join(EMU, "ws_r14_play_fresh")
OUT = os.path.join(REPO, "scratch", "round14_breakout", "play")
FRAMES = os.path.join(OUT, "frames")
GAME = open(os.path.join(EMU, "cs50x.exe"), "rb").read()
BODY = GAME[0x800:]

A = {"motion": 0x80023030, "ballX": 0x80023004, "ballY": 0x8002300C,
     "playerX": 0x80023038, "lives": 0x800187C0, "level": 0x8002303C,
     "bricksCounter": 0x80023028, "gameWon": 0x80023034,
     "velX": 0x800187BC, "velY": 0x800187B8, "pause": 0x80023020}
FLAG = 0x80180400
STAGE1 = 0x80180000
GAME_PC = 0x80010000
PLAYER_Y = 210
BALL_RAD = 8
FRAMING = 16
PLAYER_SIZE = 50


def S(p, names=None):
    s = bytes(p.mem.snapshot())
    out = {}
    for k in (names or A.keys()):
        a = A[k] - 0x80000000
        out[k] = int(np.frombuffer(s[a:a + 4], "<u4")[0])
    return out


def jrn(ev):
    with open(os.path.join(OUT, "events.jsonl"), "a") as f:
        ev = {"t": round(time.time(), 3), **ev}
        f.write(json.dumps(ev, default=str) + "\n")
    print("[play]", json.dumps(ev, default=str)[:180], flush=True)


def save_png(arr, name):
    Image.fromarray(arr).save(os.path.join(FRAMES, name))


def predict(bx, by, vx, vy):
    """Simulate the game's own ballMotion to the paddle band."""
    for _ in range(2000):
        if vy > 0 and 202 <= by <= 212:
            return bx
        if by - BALL_RAD < FRAMING:
            vy = 2
        if bx + BALL_RAD > 320 - FRAMING:
            vx = -1
        elif bx - BALL_RAD < FRAMING:
            vx = 1
        bx += vx
        by += vy
    return bx


def main():
    os.makedirs(FRAMES, exist_ok=True)
    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(os.path.join(REPO, "third_party", "openbios",
                                 "openbios.bin"),
                    os.path.join(WS, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(CUE, workspace=WS, var_overrides=fw["override_vars"])
    p.boot()
    t0 = time.time()

    # ---- A: wait for the stage-1 spin ----
    spin_f = None
    for _ in range(400):
        p.wait(6)
        s = bytes(p.mem.snapshot())
        if s[0x180000:0x180008] != b"\x00" * 8 and \
                int(np.frombuffer(s[0x180400:0x180404], "<u4")[0]) == 0:
            spin_f = p.core.frames_run
            break
    if spin_f is None:
        jrn({"ev": "FAIL", "phase": "spin_wait"})
        return 1
    jrn({"ev": "stage1_spinning", "frame": spin_f})

    # ---- B: stage the payload + flag ----
    base = p.mem.ram.ctypes.data
    ctypes.memmove(base + 0x10000, BODY, len(BODY))
    snapchk = bytes(p.mem.snapshot())[0x10000:0x10020]
    assert snapchk == BODY[:32], "payload staging mismatch"
    flag = np.asarray([1, 0, 0, 0], dtype=np.uint8)
    p.mem.ram[0x180400:0x180404] = flag
    jrn({"ev": "payload_staged", "bytes": len(BODY),
         "flag_set": True, "frame": p.core.frames_run})

    # ---- C: game live ----
    live_f = None
    for _ in range(600):
        p.wait(6)
        st = S(p, ("motion", "lives", "level"))
        fr = p.core.frame_rgb()
        if fr is not None and float(fr.mean()) > 8 and st["lives"] == 3 \
                and st["level"] == 0:
            live_f = p.core.frames_run
            break
    if live_f is None:
        jrn({"ev": "FAIL", "phase": "game_live"})
        return 1
    save_png(p.core.frame_rgb(), "game_first_screen.png")
    jrn({"ev": "game_live", "frame": live_f,
         "sensors": S(p)})

    # ---- D: input causality ----
    s0 = S(p, ("playerX",))
    p.core.run(30, {"RIGHT"})
    s1 = S(p, ("playerX",))
    p.core.run(30, {"LEFT"})
    s2 = S(p, ("playerX",))
    causality = {"right_dx": s1["playerX"] - s0["playerX"],
                 "left_dx": s2["playerX"] - s1["playerX"]}
    jrn({"ev": "move_causality", **causality})
    # launch
    p.core.run(3, {"B"})
    p.core.run(4, set())
    p.wait(10)
    launched = S(p, ("motion",))["motion"] == 1
    jrn({"ev": "launch_causality", "motion_after_cross": launched})
    save_png(p.core.frame_rgb(), "game_after_launch.png")

    # ---- E: REAL PLAY ----
    st = {"gameWon": 0, "level": 0, "lives": 3}
    stats = {"frames": 0, "catches": 0, "misses": 0, "launches": 1,
             "level_flips": [], "win_pulse": None, "win_frame": None,
             "max_level_seen": 0}
    prev_vy = None
    prev_lives = 3
    prev_level = 0
    catch_states = 0
    idx = 0
    win_seen = False
    buttons = set()
    t_start = time.time()
    while stats["frames"] < 12000:
        p.core.run(1, buttons)
        idx += 1
        stats["frames"] += 1
        st = S(p)
        fr = p.core.frame_rgb()
        save_png(fr, f"f{idx:06d}.png")
        # win pulse
        if st["gameWon"] == 1 and not win_seen:
            win_seen = True
            stats["win_pulse"] = st
            stats["win_frame"] = idx
            save_png(fr, "WIN_FRAME.png")
            jrn({"ev": "WIN_PULSE", "i": idx, "state": st})
        if win_seen and st["level"] == 0 and st["lives"] == 3 and \
                stats["frames"] - (stats["win_frame"] or 0) > 30:
            break
        # level flip
        if st["level"] != prev_level:
            stats["level_flips"].append(
                {"i": idx, "from": prev_level, "to": st["level"],
                 "bricks": st["bricksCounter"]})
            jrn({"ev": "level_flip", "i": idx, "to": st["level"],
                 "bricks": st["bricksCounter"]})
            prev_level = st["level"]
            save_png(fr, f"level{st['level']}_i{idx:06d}.png")
        stats["max_level_seen"] = max(stats["max_level_seen"],
                                      st["level"])
        # lives (misses)
        if st["lives"] < prev_lives:
            stats["misses"] += prev_lives - st["lives"]
            jrn({"ev": "MISS", "i": idx, "lives": st["lives"]})
            save_png(fr, f"miss_i{idx:06d}.png")
        prev_lives = st["lives"]
        # catch detection: vy flipped + -> - while in the band
        if prev_vy is not None and prev_vy > 0 and st["velY"] < 0:
            stats["catches"] += 1
            catch_states += 1
        prev_vy = st["velY"]
        # ---- servo ----
        if st["pause"]:
            buttons = set()
            continue
        if st["motion"] == 0:
            # ball on paddle: center, then relaunch
            err = (st["playerX"] + PLAYER_SIZE // 2) - 160
            if abs(err) > 8:
                buttons = {"RIGHT" if err < 0 else "LEFT"}
                if abs(err) > 60:
                    buttons.add("A")
            else:
                buttons = {"B"}
            continue
        # ball in flight: predict + steer
        bx, by = st["ballX"], st["ballY"]
        vx = -1 if st["velX"] < 0 else 1
        vy = -2 if st["velY"] < 0 else 2
        target = predict(bx, by, vx, vy)
        err = (st["playerX"] + PLAYER_SIZE // 2) - target
        if abs(err) <= 3:
            buttons = set()
        else:
            buttons = {"RIGHT" if err < 0 else "LEFT"}
            if abs(err) > 40:
                buttons.add("A")

    wall = round(time.time() - t_start, 1)
    save_png(p.core.frame_rgb(), "final_screen.png")
    rep = {"verdict": "WON_BY_PLAYING" if win_seen else "INCOMPLETE",
           "wall_s": wall, "stats": stats,
           "causality": causality, "launch_causality": launched,
           "spin_frame": spin_f, "live_frame": live_f,
           "frames_total": idx}
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    jrn({"ev": "DONE", **rep})
    print(json.dumps(rep, indent=1))
    return 0 if win_seen else 2


if __name__ == "__main__":
    sys.exit(main())
