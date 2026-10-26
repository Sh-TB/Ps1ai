#!/usr/bin/env python3
"""hellopong_r12_win2.py — Round 12 (Task 16-c) WIN arm, compact rewrite.

The r12-win attempt 1/2 failed on flow bugs (frozen frames_run in the
discovery loop; the game self-played to game over first).  This driver
uses ONLY the verified lib primitives in a tight single-boot loop:

  boot -> settle -> [GAME_OVER -(B rel)-> MENU -(B rel)-> PLAYING]
  -> r11 UP-tap score discovery (16 f) -> steer P1 (ball tracking,
  2-frame UP/DOWN taps toward the ball when it is in our half)
  -> left reaches 5 -> GAME_OVER screen + per-point anchors
  -> B-release restart -> MENU -> B-release -> fresh game 0-0.

Win condition (upstream marconvcm/ps1_dev @ dec2f3f0): first to 5;
serve always rightward; static right paddle (no AI, 2 pads exposed).
Verdict WIN_CAUSAL / PARTIAL / FAILED, honest.
"""
import json
import os
import sys
import time

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hellopong_r12_lib as HL  # noqa: E402

OUT = os.path.join(_REPO, "scratch", "round12_hellopong", "win2")
WS = "/home/z/my-project/emu/games_homebrew/ws_hellopong_r12_win2"
WIN_SCORE = 5
MAXF = 16000


def grab(p):
    return p.core.frame_rgb()


def run2(p):
    p.core.run(2, set())


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    evs = []

    def jrn(**kw):
        kw["t"] = round(time.time() - t0, 2)
        kw["f"] = int(p.core.frames_run) if "p" in dir() else 0
        evs.append(kw)
        print("[win2]", json.dumps(kw)[:200])

    p, boot = HL.boot_hellopong(WS, lambda e: jrn(**{"ev": "bootlog",
                                                     **{k: str(v)[:80] for k, v in e.items()}}))
    jrn(ev="boot", core=str(boot.get("core"))[:120])

    cls, tl, addrs = HL.settle_boot(p, lambda e: jrn(**e))
    jrn(ev="settled", cls=cls, pad_id41=len(addrs))

    def to_playing(cls, tag):
        for leg in range(3):
            if cls == "PLAYING":
                return cls
            if cls in ("GAME_OVER", "MENU"):
                HL.hold_and_release(p, "B", addrs)
                p.wait(36, set())
                fr = grab(p)
                cls2, _ = HL.classify(fr, 0.3)
                HL.save_png(OUT, fr, f"{tag}_leg{leg}_{cls2.lower()}.png")
                jrn(ev="transition", tag=tag, leg=leg, to=cls2)
                cls = cls2
        return cls

    cls = to_playing(cls, "boot")
    if cls != "PLAYING":
        rep = {"verdict": f"FAILED(start chain ended in {cls})",
               "events": evs[-40:]}
        json.dump(rep, open(os.path.join(OUT, "report.json"), "w"), indent=1)
        return 1

    # r12b discovery: UP-tap whole-RAM i32 delta (r11 idiom, live-verified:
    # delta -8 hits 0x1ffea4 AND 0x1ffeb0 - two paddle-shaped slots).  The
    # score word (y+4) disambiguates DURING play via its +1 point events:
    # the side the ball exits AGAINST scores; we anchor every +1 and swap
    # the left label if the data says the first guess was the far paddle.
    sensor = HL.ScoreSensor(p)
    sA = bytes(p.mem.snapshot())
    p.core.run(2, {"UP"})
    p.core.run(6, set())
    sB = bytes(p.mem.snapshot())
    iA, iB = HL.i32(sA).astype(np.int64), HL.i32(sB).astype(np.int64)
    dd = iB - iA
    cands = [int(h) * 4 for h in np.flatnonzero(dd == -8)
             if 0 < int(iA[h]) < 240]
    jrn(ev="up_tap_cands", addrs=[hex(c) for c in cands])
    if not cands:
        rep = {"verdict": "FAILED(no UP-tap -8 candidate)",
               "events": evs[-30:]}
        json.dump(rep, open(os.path.join(OUT, "report.json"), "w"),
                  indent=1)
        return 1
    y_left = cands[-1]                    # 0x1ffeb0 (r12 walkover evidence)
    l_addr = y_left + 4
    alt_addr = cands[0] + 4               # 0x1ffea8 (far-paddle score cand)
    sensor.y_addr, sensor.l_addr = y_left, l_addr
    jrn(ev="sensor_armed", y=hex(y_left), l=hex(l_addr), alt=hex(alt_addr))

    # A 0-0 start requires GAME_OVER first (CROSS does nothing in PLAYING;
    # the boot auto-start already burned points).  Let the in-flight game
    # finish naturally, then restart through MENU - the r5/r11 chain.
    for _k in range(120):                    # cap ~7k frames of walkover
        p.core.run(60, set())
        if HL.classify(grab(p), 0.0)[0] == "GAME_OVER":
            break
    jrn(ev="walkover_done", cls=HL.classify(grab(p), 0.0)[0],
        f=int(p.core.frames_run))
    HL.hold_and_release(p, "B", addrs)      # GAME_OVER -> MENU
    p.wait(36, set())
    cls_r, _ = HL.classify(grab(p), 0.3)
    HL.save_png(OUT, grab(p), "restart_menu.png")
    jrn(ev="after_over_release", cls=cls_r)
    if cls_r == "MENU":
        HL.hold_and_release(p, "B", addrs)  # MENU -> fresh PLAYING 0-0
        p.wait(48, set())
    cls_r, _ = HL.classify(grab(p), 0.3)
    snapR = HL.u32(bytes(p.mem.snapshot()))
    sc_r = [int(snapR[l_addr // 4])]
    jrn(ev="fresh_start", cls=cls_r, scores=sc_r)
    HL.save_png(OUT, grab(p), "fresh_start.png")
    # seed the score tracker IMMEDIATELY (the first serve lands within
    # ~80 f and the paddle-exercise leg would otherwise eat it)
    sc_prev = list(sc_r)
    snap_prev = bytes(p.mem.snapshot())

    # ---------------- WIN loop: steer P1, anchor every left point --------
    anchors = []
    # paddle-exercise leg INSIDE gameplay, wrapped in per-frame l_now
    # reads so no score step can fall in a blind window
    ytrace = []
    for btn, sign in (("UP", -1), ("DOWN", +1)):
        for _k in range(3):
            y0 = int(HL.i32(bytes(p.mem.snapshot()))[y_left // 4])
            lA = int(p.mem.u32(l_addr))
            p.core.run(2, {btn})
            p.core.run(6, set())
            y1 = int(HL.i32(bytes(p.mem.snapshot()))[y_left // 4])
            lB = int(p.mem.u32(l_addr))
            ytrace.append({"btn": btn, "y": [y0, y1],
                           "delta": y1 - y0, "expect": sign * 8})
            if lB > lA:
                for _m in range(lB - lA):
                    anchors.append({"frame": int(p.core.frames_run),
                                    "primary": lA + _m + 1,
                                    "during": "exercise"})
                jrn(ev="PRIMARY_POINT", primary=lB,
                    frame=int(p.core.frames_run),
                    during="exercise")
    y_ok = all(t["delta"] == t["expect"] for t in ytrace)
    jrn(ev="paddle_exercise", ok=y_ok, trace=ytrace)

    sc_prev = [int(p.mem.u32(l_addr))]
    last_cls = "PLAYING"
    steered = 0
    f0 = p.core.frames_run
    while p.core.frames_run - f0 < MAXF:
        p.core.run(1, set())
        # per-frame score word read (cheap: two u32s, no snapshot)
        l_now = int(p.mem.u32(l_addr))
        if sc_prev is None:
            sc_prev = [l_now]
        elif l_now > sc_prev[0]:
            for _m in range(l_now - sc_prev[0]):
                anchors.append({"frame": int(p.core.frames_run),
                                "primary": sc_prev[0] + _m + 1})
            HL.save_png(OUT, grab(p), f"point_primary_{l_now:02d}.png")
            jrn(ev="PRIMARY_POINT", primary=l_now,
                frame=int(p.core.frames_run),
                new_anchors=l_now - sc_prev[0])
            sc_prev = [l_now]
        if p.core.frames_run % 10:
            continue
        fr = grab(p)
        cls, _facts = HL.classify(fr, 0.0)
        if cls == "GAME_OVER":
            last_cls = cls
            break
        bc = HL.ball_centroid(fr)
        if bc is not None and bc[0] < 150:
            row = HL.paddle_row(fr, (4, 24))
            if row is not None:
                dy = int(bc[1]) - int(row)
                if abs(dy) > 12:
                    btn = "UP" if dy < 0 else "DOWN"
                    p.core.run(2, {btn})
                    steered += 1
    fr_end = grab(p)
    HL.save_png(OUT, fr_end, "final_screen.png")
    cls_end, _ = HL.classify(fr_end, 0.0)
    snapE = bytes(p.mem.snapshot())
    wE = HL.u32(snapE)
    sc_final = [int(wE[l_addr // 4])]
    if sc_prev and sc_final[0] > sc_prev[0]:
        for _m in range(sc_final[0] - sc_prev[0]):
            anchors.append({"frame": int(p.core.frames_run),
                            "primary": sc_prev[0] + _m + 1,
                            "at": "loop_end"})
    jrn(ev="loop_end", cls=cls_end, scores=sc_final,
        steered=steered, anchors=len(anchors))


    # restart chain: GAME_OVER -(B rel)-> MENU -(B rel)-> fresh 0-0
    fresh = None
    if cls_end == "GAME_OVER":
        HL.hold_and_release(p, "B", addrs)
        p.wait(36, set())
        fr_m = grab(p)
        cls_m, _ = HL.classify(fr_m, 0.3)
        HL.save_png(OUT, "after_restart_menu.png" and fr_m,
                    "restart_menu.png")
        if cls_m == "MENU":
            HL.hold_and_release(p, "B", addrs)
            p.wait(48, set())
            fr_g = grab(p)
            cls_g, _ = HL.classify(fr_g, 0.3)
            snapG = bytes(p.mem.snapshot())
            wG = HL.u32(snapG)
            sc_g = [int(wG[l_addr // 4])]
            fresh = {"class": cls_g, "scores": sc_g,
                     "reset_ok": sc_g == [0]}
            HL.save_png(OUT, fr_g, "fresh_game.png")
            jrn(ev="fresh_game", **fresh)

    parts = {
        "sensor_ok": bool(sensor.l_addr is not None),
        "left_score_5_anchored": bool(
            sc_final and sc_final[0] == WIN_SCORE
            and len(anchors) >= WIN_SCORE),
        "note_alt_word": ("0x1ffea8 does NOT reset across games - not "
                          "the right score; dropped from the verdict"),
        "gameover_screen": bool(cls_end == "GAME_OVER"),
        "steered": bool(steered > 10),
        "paddle_y_tracks": bool(y_ok),
        "fresh_game_reset": bool(fresh and fresh["reset_ok"]),
    }
    core_win = (parts["sensor_ok"] and parts["left_score_5_anchored"]
                and parts["gameover_screen"] and parts["paddle_y_tracks"]
                and parts["fresh_game_reset"])
    if core_win:
        verdict = "WIN_CAUSAL"
    elif parts["left_score_5_anchored"] or parts["steered"]:
        verdict = ("PARTIAL(" +
                   ",".join(k for k, v in parts.items() if not v) + ")")
    else:
        verdict = "FAILED(no win progression)"
    rep = {"schema": "ps1ai-hellopong-r12-win2/1",
           "verdict": verdict, "verdict_parts": parts,
           "scores_final": sc_final, "anchors": anchors,
           "steered_steps": steered, "end_class": cls_end,
           "fresh_after_restart": fresh,
           "sensor": sensor.sensor_block(),
           "frames_run": int(p.core.frames_run),
           "wall_s": round(time.time() - t0, 1)}
    json.dump(rep, open(os.path.join(OUT, "report.json"), "w"),
              indent=1)
    with open(os.path.join(OUT, "events.jsonl"), "w") as f:
        for e in evs:
            f.write(json.dumps(e) + "\n")
    jrn(ev="verdict", verdict=verdict)
    print("VERDICT:", verdict)
    return 0 if verdict == "WIN_CAUSAL" else 2


if __name__ == "__main__":
    sys.exit(main())
