#!/usr/bin/env python3
r"""r19t2_m2_enter.py — Round 19 T2 (finish): reach LIVE Mission 2 gameplay.

Recovered state (r19t2 predecessor, verified from scratch/r19t2_msx/):
  - main menu = ARCADE MISSION / COMBAT SCHOOL / ART GALLERY / OPTION (VLM x6)
    -> NO mission-select entry reachable by pure input (COMBAT SCHOOL gated).
  - pure-input ladder reaches M1 live: px 116.152, php 116, score 0.
  - static capstone on SLUS_012.12: pause label sets @VA 0x80082d18 =
    [PAUSE] / [RETRY,EXIT,CONTINUE] / [RETRY,"MISSION SELECT",EXIT] /
    [MISSION 6..1] / [RETRY,EXIT,CONTINUE] / [EXIT];
    menu objects @0x800D4A48, pause cursor u8 @0x800D4A71 (mod-4),
    MISSION n submenu cursor u8 @0x800D4A70, label ptr u32 @0x800D4A68,
    mode word s16 @0x800D4210 (labels drawn when >= 2),
    mission index s16 @0x800DAB3C.
T9 disc map: CD table rows VA 0x800841C4 (\ST01...) / 0x800841D4 (\ST02...),
same dest 0x800FA6B0 -> row swap = Mission 2 stage data (untested hypothesis).
M2 spawn prior (r17 msel4 docstring, from ST02 disc data): px ~76.4 php 120.

ONE process, ONE boot, escalating experiments (every poke is a labeled RAM
patch; reach-ladder itself is pure button input):
  ladder -> M1 live -> PAUSE
  EXP-A: poke pause mode word -> pause MENU -> MISSION SELECT -> MISSION 2
  EXP-B: swap CD-table rows 0/1 in RAM -> replay M1 ladder -> stage = ST02?
  EXP-C: poke mission index 0xDAB3C=1 at SOLDIER SELECT -> confirm
Verdicts honest: PLAYING only with live px/php != M1 signature + PNG.
Evidence: scratch/r19t2_msx/ (report r19t2_m2_enter_report.json)
"""
from __future__ import annotations

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

CUR_LO, CUR_HI = 0x957D8, 0x957F8      # r17-pinned menu cursor struct
A_MODE = 0xD4210                        # s16 pause/menu mode word
A_ITEMS = 0xD4A48                       # 4 u32 menu object ptrs
A_LABEL = 0xD4A68                       # u32 label string ptr
A_MSEL = 0xD4A70                        # u8 MISSION n submenu cursor
A_CURSOR = 0xD4A71                      # u8 pause/main-menu cursor (mod 4)
A_MVAR = 0xDAB3C                        # s16 mission index
ROW0, ROW1 = 0x841C4, 0x841D4           # CD table rows \ST01 / \ST02 (16B each)
PLAYER_X = 0x0CA2E0
PLAYER_HP = 0x0CA2F6
A_SCORE = 0x0EE318
FLAGS = 0x0EE518
MISSION_STR = {0x800100c4: "MISSION 1", 0x800100b8: "MISSION 2",
               0x800100ac: "MISSION 3", 0x800100a0: "MISSION 4",
               0x80010094: "MISSION 5", 0x80010088: "MISSION 6"}
T0 = time.time()
WALL_BUDGET = 300.0                     # leave margin under 6-min cap


def log(*a):
    print("[r19t2-m2]", *a, file=sys.stderr, flush=True)


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
        return {"ptr": hex(va), "str": None}
    raw = bytes(p.mem.ram[off:off + 24]).split(b"\x00")[0]
    try:
        s = raw.decode("ascii", "replace")
    except Exception:
        s = None
    return {"ptr": hex(va), "str": s or None,
            "named": MISSION_STR.get(va)}


def cursor_words(p):
    return [int(p.mem.u32(a)) for a in range(CUR_LO, CUR_HI + 1, 4)]


def dump(p):
    m = p.mem
    d = {"mode": int(np.int16(m.u16(A_MODE))),
         "items": [hex(m.u32(A_ITEMS + 4 * i)) for i in range(4)],
         "label": label_str(p), "msel_cursor": int(m.u8(A_MSEL)),
         "menu_cursor": int(m.u8(A_CURSOR)), "mission_var": int(m.u16(A_MVAR)),
         "words": words(p)}
    log("dump:", json.dumps(d))
    return d


def ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def poke(p, off, data):
    """RAM_PATCH: write bytes into live PS1 RAM via the numpy view."""
    p.mem.ram[off:off + len(data)] = np.frombuffer(bytes(data), dtype=np.uint8)


def wait_live(p, max_f=6000, min_px=20.0):
    tl = []
    for i in range(max_f // 300):
        p.core.run(300, set())
        w = words(p)
        tl.append({"f": (i + 1) * 300, **w})
        if w["px"] > min_px and w["php"] > 0:
            log("live at +", (i + 1) * 300, "f:", w)
            return {"live": True, "frames": (i + 1) * 300, "timeline": tl,
                    "words": w}
    log("no live px within", max_f, "f")
    return {"live": False, "frames": max_f, "timeline": tl, "words": tl[-1]}


def ladder_menu(p):
    """boot->START->main menu; save m_menu; return menu words."""
    p.core.run(4800, set())
    p.core.run(60, {"START"})
    p.core.run(900, set())
    p.save_state("m_menu")
    snap(p, "z_menu.png")
    log("menu:", words(p), "wall", wall())


def ladder_m1(p):
    """menu -> CROSS OK?YES -> soldier -> OK?YES -> M1 live; save m1_live."""
    p.core.run(60, {"B"})
    p.core.run(600, set())
    snap(p, "z_ok_dialog.png")
    p.core.run(60, {"B"})
    p.core.run(900, set())
    p.save_state("m_soldier")
    snap(p, "z_soldier.png")
    p.core.run(60, {"B"})
    p.core.run(600, set())
    snap(p, "z_soldier_ok.png")
    p.core.run(60, {"B"})
    r = wait_live(p, 6000)
    snap(p, "z_m1_live.png")
    p.save_state("m1_live")
    log("M1 live:", r["words"], "wall", wall())
    return r


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime()),
           "cue": CUE, "ws": WS,
           "ram_patch_policy": "all pokes explicitly tagged RAM_PATCH; "
                               "reach ladder is pure button input"}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)
    log("booted wall", wall())

    # ---------- pure-input ladder to M1 live ----------
    ladder_menu(p)
    m1 = ladder_m1(p)
    out["m1_live"] = m1["words"]
    out["m1_signature"] = "px 116.152 / php 116 / score 0 (r17+r19t2 repro)"

    # ---------- PAUSE ----------
    p.core.run(120, set())
    p.core.run(60, {"START"})
    p.core.run(600, set())
    p.save_state("m_pause")
    snap(p, "z_pause.png")
    base_ram = ram(p)
    out["pause_dump"] = dump(p)
    pause_cursor_words = cursor_words(p)

    # ---------- EXP-A: pause mode-word poke -> MISSION SELECT ----------
    expA = {"kind": "RAM_PATCH mode@0xD4210 + pure-input navigation",
            "pause_cursor_words_0x957D8": pause_cursor_words}
    live_mv = None
    for mv in (2, 3, 1, 4, 5):
        if time.time() - T0 > WALL_BUDGET:
            log("wall budget stop before mv", mv)
            break
        p.load_state("m_pause")
        p.core.run(60, set())
        try:
            poke(p, A_MODE, int(mv).to_bytes(2, "little"))
        except Exception as e:
            expA["poke_error"] = str(e)
            log("poke failed:", e)
            break
        p.core.run(240, set())
        c0 = int(p.mem.u8(A_CURSOR))
        p.core.run(30, {"DOWN"})
        p.core.run(120, set())
        c1 = int(p.mem.u8(A_CURSOR))
        live_mv = mv if c1 != c0 else None
        expA[f"probe_mv{mv}"] = {"cursor_before": c0, "cursor_after": c1,
                                 "menu_responds": c1 != c0}
        snap(p, f"a_poke{mv}.png")
        log(f"poke mv={mv}: cursor {c0}->{c1} responds={c1 != c0}")
        if live_mv is not None:
            break
    expA["mode_used"] = live_mv
    out["expA"] = expA

    if live_mv is not None:
        # navigate pause menu: [RETRY, MISSION SELECT, EXIT] -> cursor 1
        for i in range(4):
            c = int(p.mem.u8(A_CURSOR))
            if c == 1:
                break
            p.core.run(30, {"DOWN"})
            p.core.run(90, set())
        p.core.run(120, set())
        snap(p, "a_msel_highlight.png")
        expA["msel_highlight_dump"] = dump(p)
        pre_list = ram(p)
        p.core.run(60, {"B"})
        p.core.run(600, set())
        snap(p, "a_mission_list.png")
        r = ram(p)
        expA["mission_list"] = dump(p)
        expA["mission_list_full_ram_diff"] = int(np.count_nonzero(r != pre_list))
        expA["mission_list_cursor_words_0x957D8"] = cursor_words(p)
        log("MISSION LIST diff:", expA["mission_list_full_ram_diff"], "bytes")
        # DOWN once -> MISSION 2
        p.core.run(30, {"DOWN"})
        p.core.run(240, set())
        snap(p, "a_m2_highlight.png")
        expA["m2_highlight_dump"] = dump(p)
        # CROSS -> (OK? YES) -> wait for M2 spawn
        p.core.run(60, {"B"})
        p.core.run(600, set())
        snap(p, "a_m2_confirm.png")
        expA["m2_confirm_dump"] = dump(p)
        p.core.run(60, {"B"})          # YES (pure-input pattern from menus)
        res = wait_live(p, 7200)
        snap(p, "a_m2_live0.png")
        p.core.run(600, set())
        w2 = words(p)
        snap(p, "a_m2_live1.png")
        expA["wait"] = {"live": res["live"], "frames": res["frames"]}
        expA["m2_words"] = res["words"]
        expA["m2_words_plus600"] = w2
        out["verdict"] = "PLAYING(M2)" if (res["live"] and
                                           (abs(res["words"]["px"] - 116.152) > 1
                                            or res["words"]["php"] != 116)) \
            else ("RUNNING" if res["live"] else "NOT_REACHED")
        if res["live"]:
            p.save_state("m2_live")
            out["finished_verdict"] = out.get("verdict")
            _write(out)
            return 0

    # ---------- EXP-B: CD-table row swap (T9 lever, RAM patch) ----------
    if time.time() - T0 < WALL_BUDGET:
        expB = {"kind": "RAM_PATCH swap CD rows 0/1 @0x841C4/0x841D4"}
        p.load_state("m_menu")
        p.core.run(60, set())
        row0 = bytes(p.mem.ram[ROW0:ROW0 + 16])
        row1 = bytes(p.mem.ram[ROW1:ROW1 + 16])
        expB["row0_before_hex"] = row0.hex()
        expB["row1_before_hex"] = row1.hex()
        pv0 = int.from_bytes(row0[0:4], "little") - 0x80000000
        pv1 = int.from_bytes(row1[0:4], "little") - 0x80000000
        try:
            expB["row0_path"] = bytes(p.mem.ram[pv0:pv0 + 24]).split(b"\x00")[0].decode("ascii", "replace")
            expB["row1_path"] = bytes(p.mem.ram[pv1:pv1 + 24]).split(b"\x00")[0].decode("ascii", "replace")
        except Exception as e:
            expB["path_read_error"] = str(e)
        p.mem.ram[ROW0:ROW0 + 16] = np.frombuffer(row1, dtype=np.uint8)
        p.mem.ram[ROW1:ROW1 + 16] = np.frombuffer(row0, dtype=np.uint8)
        expB["row0_after_hex"] = bytes(p.mem.ram[ROW0:ROW0 + 16]).hex()
        expB["swap_ok"] = bytes(p.mem.ram[ROW0:ROW0 + 16]) == row1
        log("rows swapped:", expB.get("row0_path"), "<->", expB.get("row1_path"))
        r = ladder_m1(p)
        res = wait_live(p, 2400) if not r["live"] else {"live": True,
                                                        "words": r["words"]}
        snap(p, "b_m2_live0.png")
        p.core.run(600, set())
        w2 = words(p)
        snap(p, "b_m2_live1.png")
        expB["wait"] = {"live": res["live"]}
        expB["m2_words"] = res["words"]
        expB["m2_words_plus600"] = w2
        expB["post_dump"] = dump(p)
        out["expB"] = expB
        if res["live"] and (abs(res["words"]["px"] - 116.152) > 1
                            or res["words"]["php"] != 116):
            out["verdict"] = "PLAYING(M2)"
            p.save_state("m2_rowswap")
            _write(out)
            return 0
        out["verdict"] = "RUNNING" if res["live"] else "NOT_REACHED"

    # ---------- EXP-C: mission-index poke (RAM patch) ----------
    if time.time() - T0 < WALL_BUDGET:
        expC = {"kind": "RAM_PATCH u16 0xDAB3C=1 at SOLDIER SELECT"}
        p.load_state("m_soldier")
        p.core.run(60, set())
        poke(p, A_MVAR, int(1).to_bytes(2, "little"))
        p.core.run(120, set())
        expC["mission_var_after_poke"] = int(p.mem.u16(A_MVAR))
        p.core.run(60, {"B"})
        p.core.run(600, set())
        expC["post_confirm_dump"] = dump(p)
        p.core.run(60, {"B"})
        res = wait_live(p, 7200)
        snap(p, "c_m2_live0.png")
        expC["wait"] = {"live": res["live"], "frames": res["frames"]}
        expC["m2_words"] = res["words"]
        out["expC"] = expC
        if res["live"] and (abs(res["words"]["px"] - 116.152) > 1
                            or res["words"]["php"] != 116):
            out["verdict"] = "PLAYING(M2)"
            snap(p, "c_m2_live1.png")
            p.save_state("m2_varpoke")
            _write(out)
            return 0
        out["verdict"] = "RUNNING" if res["live"] else "NOT_REACHED"

    out.setdefault("verdict", "NOT_REACHED")
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    out["wall_s"] = wall()
    _write(out)
    return 0


def _write(out):
    out.setdefault("finished", time.strftime("%FT%TZ", time.gmtime()))
    out["wall_s"] = wall()
    with open(os.path.join(EVID, "r19t2_m2_enter_report.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    log("report written; verdict:", out.get("verdict"))


if __name__ == "__main__":
    sys.exit(main())
