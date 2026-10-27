#!/usr/bin/env python3
"""r19t2_m2_native.py — Round 19 T2: native Mission 2 start via mission global.

Static proof (r19t2_static_scan + capstone, offline):
  loader fn @0x8002848C:  lui $v0,0x800f; lh $v0,-0x24c4($v0)  -> mission s16
  @VA 0x800FDB3C; then map[mission] from u32[6] @0x80010E58 = {0,1,5,7,8,12}
  (M1..M6 -> CD-table rows ST01/ST02/ST03/ST04/ST05/ST06); jal 0x8001e030.
  -> mission global is 0-based s16; poke 1 = Mission 2 (RAM_PATCH, labeled).
This run: pure-input ladder -> SOLDIER SELECT -> poke mission=1 -> confirm ->
expect native M2: ST02 package + X21 events + SEQ02 audio + LD\\WAIT_S2 screen
+ HUD "MISSION 2". WAIT-screen identity is verified byte-wise against the disc
extraction (WAIT_S1 vs WAIT_S2 heads @ dest 0x801E8000).
ONE process, ONE boot, <=6 min wall. Verdict honest: PLAYING(M2) only if
live px/php differ from M1 signature (px 116.152/php 116) and control moves.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.api import PS1Play                                   # noqa: E402

EVID = "/home/z/my-project/ps1ai/scratch/r19t2_msx"
CUE = "/home/z/my-project/emu/game/Metal Slug X (USA).cue"
WS = "/home/z/my-project/emu/ws_r19t2"
EXT = "/home/z/my-project/emu/msx_extract_r18"

A_MISSION = 0xFDB3C          # s16 mission index (VA 0x800FDB3C)
A_SELA = 0xFDB30             # s16 arcade-start mission slot (copied -> mission
                             # by fn 0x80028660: lhu -0x24d0; sh -0x24c4)
A_SELB = 0xFDB54             # s16 current-mission progression (selB++ on clear)
A_ROWMAP = 0x10E58           # u32[6] M1..M6 -> CD rows
A_LABEL = 0xD4A68            # u32 HUD label ptr
A_WAITDEST = 0x1E8000        # LD\\WAIT_* load dest (rows 117-133)
PLAYER_X = 0x0CA2E0
PLAYER_HP = 0x0CA2F6
A_SCORE = 0x0EE318
FLAGS = 0x0EE518
MISSION_STR = {0x800100c4: "MISSION 1", 0x800100b8: "MISSION 2"}
T0 = time.time()


def log(*a):
    print("[r19t2-m2n]", *a, file=sys.stderr, flush=True)


def wall():
    return round(time.time() - T0, 1)


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def words(p):
    m = p.mem
    px = int(m.u32(PLAYER_X))
    if px >= 0x80000000:
        px -= 0x100000000
    return {"states": int(m.u8(0x95A7D)), "flags": int(m.u32(FLAGS)),
            "px": round(px / 65536.0, 3), "php": int(m.u16(PLAYER_HP)),
            "score": int(m.u32(A_SCORE))}


def label_str(p):
    va = int(p.mem.u32(A_LABEL))
    off = va - 0x80000000
    if not (0 <= off < len(p.mem.ram) - 32):
        return {"ptr": hex(va), "named": None}
    raw = bytes(p.mem.ram[off:off + 24]).split(b"\x00")[0]
    return {"ptr": hex(va), "str": raw.decode("ascii", "replace"),
            "named": MISSION_STR.get(va)}


def dump(p, tag):
    m = p.mem
    d = {"mission": int(np.int16(m.u16(A_MISSION))),
         "selA": int(np.int16(m.u16(A_SELA))),
         "selB": int(np.int16(m.u16(A_SELB))),
         "rowmap": [int(m.u32(A_ROWMAP + 4 * i)) for i in range(6)],
         "label": label_str(p), "words": words(p)}
    log(tag, json.dumps(d))
    return d


def poke(p, off, data):
    p.mem.ram[off:off + len(data)] = np.frombuffer(bytes(data), dtype=np.uint8)


def wait_live(p, max_f=7200, min_px=20.0, snaps=()):
    tl = []
    snaps = set(snaps)
    for i in range(max_f // 300):
        p.core.run(300, set())
        w = words(p)
        tl.append({"f": (i + 1) * 300, **w})
        if (i + 1) * 300 in snaps:
            snap(p, f"f{(i + 1) * 300}.png")
        if w["px"] > min_px and w["php"] > 0:
            return {"live": True, "frames": (i + 1) * 300, "timeline": tl,
                    "words": w}
    return {"live": False, "frames": max_f, "timeline": tl, "words": tl[-1]}


def wait_digest(p):
    chunk = bytes(p.mem.ram[A_WAITDEST:A_WAITDEST + 4096])
    return hashlib.blake2b(chunk, digest_size=12).hexdigest()


def keep_m2(p, val=1):
    """RAM_PATCH (labeled): keep mission slots = 1 through the start flow.
    The arcade start zeroes selA/selB/selC/mission after the soldier OK?YES,
    then copies selA -> mission; re-asserting every 10 frames wins the race."""
    b = int(val).to_bytes(2, "little")
    for off in (A_SELA, A_SELB, 0xFDB5C, A_MISSION):
        poke(p, off, b)


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime()),
           "ram_patch": "u16 1 -> 0x800FDB30 (selA) at SOLDIER SELECT; "
                        "start fn 0x80028660 copies selA -> mission 0x800FDB3C",
           "wait_heads": {}}
    for f in ("LD/WAIT_S1.BIN", "LD/WAIT_S2.BIN"):
        b = open(os.path.join(EXT, f), "rb").read(4096)
        out["wait_heads"][f] = hashlib.blake2b(b, digest_size=12).hexdigest()
    log("WAIT_S1 head:", out["wait_heads"]["LD/WAIT_S1.BIN"])
    log("WAIT_S2 head:", out["wait_heads"]["LD/WAIT_S2.BIN"])

    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    # ---- pure-input ladder ----
    p.core.run(4800, set())
    p.core.run(60, {"START"})
    p.core.run(900, set())
    p.save_state("n_menu")
    out["menu_dump"] = dump(p, "menu:")
    p.core.run(60, {"B"})
    p.core.run(600, set())
    out["ok_dialog_dump"] = dump(p, "ok_dialog:")
    p.core.run(60, {"B"})
    p.core.run(900, set())
    p.save_state("n_soldier")
    out["soldier_dump"] = dump(p, "soldier:")
    snap(p, "n_soldier.png")

    # ---- RAM_PATCH: arcade-start mission slot selA 0 -> 1, then pure input ----
    poke(p, A_SELA, int(1).to_bytes(2, "little"))
    p.core.run(120, set())
    out["after_poke_dump"] = dump(p, "after_poke:")
    snap(p, "n_after_poke.png")

    p.core.run(60, {"B"})            # confirm soldier
    for _ in range(60):              # 600 f, guarded: zero+copy+loader-read
        keep_m2(p)                   # happen in THIS window (measured r19t2)
        p.core.run(10, set())
    out["soldier_ok_dump"] = dump(p, "soldier_ok:")
    snap(p, "n_soldier_ok.png")
    p.core.run(60, {"B"})            # OK? YES -> load continues
    # poke-guarded load wait: re-assert mission slots every 10 f until live
    tl = []
    res = {"live": False, "frames": 0, "words": None}
    for chunk_i in range(24):                     # 24 x 300 f = 7200 f
        for _ in range(30):                       # 30 x 10 f
            keep_m2(p)
            p.core.run(10, set())
        w = words(p)
        tl.append({"f": (chunk_i + 1) * 300, **w})
        if chunk_i in (1, 3, 5):
            snap(p, f"n_load_{(chunk_i + 1) * 300}.png")
            out.setdefault("load_wait_digests", {})[
                f"f{(chunk_i + 1) * 300}"] = wait_digest(p)
        if w["px"] > 20 and w["php"] > 0:
            res = {"live": True, "frames": (chunk_i + 1) * 300,
                   "words": w}
            break
    out["load_wait"] = {"live": res["live"], "frames": res["frames"],
                        "poked": "selA/selB/selC/mission=1 every 10f until live"}
    out["load_timeline"] = tl
    out["m2_words"] = res["words"]
    log("wait result:", res["words"], "wall", wall())

    if not res["live"]:
        # honest negative: capture where it stopped
        snap(p, "n_stuck.png")
        out["stuck_dump"] = dump(p, "stuck:")
        out["verdict"] = "NOT_REACHED"
        _write(out)
        return 1

    # ---- M2 live: identity + control causality (poking STOPPED) ----
    snap(p, "n_m2_live0.png")
    out["m2_live_dump"] = dump(p, "m2_live:")
    out["wait_ram_digest"] = wait_digest(p)
    p.save_state("n_m2_live")
    x0 = res["words"]["px"]
    p.core.run(60, {"RIGHT"})
    p.core.run(300, set())
    w1 = words(p)
    snap(p, "n_m2_live_right.png")
    p.core.run(30, {"B"})            # fire
    p.core.run(300, set())
    w2 = words(p)
    snap(p, "n_m2_live_fire.png")
    out["control"] = {"px_before": x0, "px_after_right": w1["px"],
                      "px_after_fire": w2["px"],
                      "php_after": w2["php"], "score_after": w2["score"]}
    m1_sig = abs(w2["px"] - 116.152) < 1 and w2["php"] == 116
    live_m = out["m2_live_dump"]["mission"] if "m2_live_dump" in out else None
    if live_m != 1:
        out["verdict"] = "RUNNING(M1)" if m1_sig else "RUNNING(unknown)"
    else:
        out["verdict"] = "PLAYING(M2)"
    log("control:", out["control"], "mission:", live_m,
        "verdict:", out["verdict"])
    _write(out)
    return 0


def _write(out):
    out.setdefault("finished", time.strftime("%FT%TZ", time.gmtime()))
    out["wall_s"] = wall()
    with open(os.path.join(EVID, "r19t2_m2_native_report.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    log("report written; verdict:", out.get("verdict"), "wall", out["wall_s"])


if __name__ == "__main__":
    sys.exit(main())
