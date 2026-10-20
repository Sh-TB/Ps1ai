#!/usr/bin/env python3
"""issue5_probe.py — Priority Refinement §2+§3: one bounded live session
answering the highest-value questions with the smallest probes.

P1  ENEMY.BIN code head @0x800A7800 in live RAM (mapping TESTED/FAILED)
    + data-head + MISSION.BIN residency patterns.
P2  player pointer [0x800C9A98] -> P; struct dump; x/y candidate fields
    via RIGHT-move / JUMP diff; published lives/hp GS reads.
P3  death/continue handling observation if a death occurs in-window.

All results appended to evidence/issue5_probe/probe.jsonl (metadata,
addresses and values only). Legal inputs only; no cheats.
"""
import json
import os
import sys
import time

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

from ps1play import labconfig                                # noqa: E402
from mission import ensure_mission                           # noqa: E402
from issue4_real_start import boot_to_demo, owns_pad         # noqa: E402
from run_mission1_legit import recover_v2                    # noqa: E402
from ps1play.telemetry import TelemetryAdapter               # noqa: E402

EV = "/home/z/my-project/work/msx_recomp/evidence/issue5_probe"
ENEMY = os.path.join(_REPO, "ps1play", "re", "ENEMY.BIN")
MISSION = os.path.join(_REPO, "ps1play", "re", "MISSION.BIN")

ADDR_PLAYER_PTR = 0xC9A98          # physical (KUSEG offset) — this
                                   # codebase reads physical offsets
ADDR_LIVES_GS = 0x475A8
ADDR_HP_GS = 0x32764

LOG = []


def log(ev, **kw):
    rec = {"t": time.strftime("%FT%TZ", time.gmtime()), "event": ev, **kw}
    LOG.append(rec)
    print(f"[probe] {json.dumps(rec, default=str)[:400]}", flush=True)


def save():
    os.makedirs(EV, exist_ok=True)
    with open(os.path.join(EV, "probe.jsonl"), "w") as f:
        for r in LOG:
            f.write(json.dumps(r, default=str) + "\n")


def pattern_hits(ram, pat, limit=6):
    hits = []
    cand = np.flatnonzero(ram[:len(ram) - 64] == pat[0])
    for k in cand.tolist():
        if np.array_equal(ram[k:k + len(pat)], pat):
            hits.append(int(k))
            if len(hits) >= limit:
                break
    return hits


def struct_dump(mem, base, n=0x180):
    return bytes(mem.ram[base:base + n])


def field_diffs(a, b):
    """u16 field deltas between two struct dumps."""
    out = {}
    for off in range(0, min(len(a), len(b)) - 1, 2):
        va = a[off] | (a[off + 1] << 8)
        vb = b[off] | (b[off + 1] << 8)
        if va != vb:
            out[f"+{off:#05x}"] = [va, vb]
    return out


def main():
    tel_notes = []
    p = boot_to_demo()
    owned = False
    for _ in range(6):
        p.core.run(12, {"START"})
        p.core.run(150, set())
        if owns_pad(p, frames=30)["owns"]:
            owned = True
            break
    if not owned:
        sys.exit("ownership failed")
    g = ensure_mission(p, log=lambda *a: None, want_hp_cands=False)
    log("mission_gate", **{k: g.get(k) for k in
                           ("in_mission", "tries")})
    if not g.get("in_mission"):
        sys.exit("not in mission")
    tel = TelemetryAdapter(p)
    mem = p.mem

    # ---------------- P1: overlay mapping in live RAM --------------
    enemy = open(ENEMY, "rb").read()
    mission = open(MISSION, "rb").read()
    ram = mem.ram

    def scan32(file_off, src, limit=4):
        pat = np.frombuffer(src[file_off:file_off + 32], np.uint8)
        return pattern_hits(ram, pat, limit)

    # multi-anchor delta map: is the overlay contiguous / chunked /
    # relocated? delta = ram_hit - file_off per anchor.
    deltas = {}
    for off in range(0x1000, 0x1C000, 0x1000):
        hits = scan32(off, enemy)
        deltas[f"{off:#x}"] = ([f"0x{h - 0x80000000 + off:X}"
                                if False else
                                [f"phys {h:#x} delta {h - off:#x}"
                                 for h in hits]])
    log("P1_enemy_anchor_deltas", deltas=deltas)
    head_code_hit = scan32(0xD180, enemy)
    log("P1_enemy_code_head", hits=head_code_hit)
    if head_code_hit:
        base = head_code_hit[0]
        live = bytes(ram[base:base + 0x400])
        disc = enemy[0xD180:0xD180 + 0x400]
        log("P1_code_window_verbatim", equal=live == disc)
        # live j/jal targets vs disc targets from the same window
        lw = np.frombuffer(live, dtype="<u4")
        dw = np.frombuffer(disc, dtype="<u4")
        lt = sorted({int(0x80000000 | ((w & 0x3FFFFFF) << 2))
                     for w in lw if (w >> 26) in (2, 3)})
        dt = sorted({int(0x80000000 | ((w & 0x3FFFFFF) << 2))
                     for w in dw if (w >> 26) in (2, 3)})
        log("P1_live_vs_disc_targets", live=[hex(x) for x in lt[:10]],
            disc=[hex(x) for x in dt[:10]], identical=lt == dt)
    log("P1_enemy_data_head", hits=scan32(0x8000, enemy))
    log("P1_mission_code", hits=scan32(0x3000, mission))
    log("P1_mission_head", hits=scan32(0x0, mission))

    # ---------------- P2: player struct discovery ------------------
    ptr = mem.u32(ADDR_PLAYER_PTR)
    log("P2_player_ptr", value=f"0x{ptr:08X}",
        sane=bool(0x80080000 <= ptr < 0x80200000))
    results = {"ptr": f"0x{ptr:08X}"}
    if 0x80080000 <= ptr < 0x80200000:
        base_phys = ptr - 0x80000000
        base = struct_dump(mem, base_phys)
        tel0 = tel.snapshot(buttons=[], frame=p.core.frames_run)
        p.core.run(40, {"RIGHT"})
        moved = struct_dump(mem, base_phys)
        tel1 = tel.snapshot(buttons=["RIGHT"], frame=p.core.frames_run)
        d_right = field_diffs(base, moved)
        log("P2_right_move_diff", changed_fields=len(d_right),
            top=dict(list(sorted(d_right.items(),
                    key=lambda kv: abs(kv[1][1] - kv[1][0]),
                    reverse=True))[:14]))
        p.core.run(20, set())
        base2 = struct_dump(mem, base_phys)
        p.core.run(30, {"X"})            # jump (X = jump button)
        jumped = struct_dump(mem, base_phys)
        d_jump = field_diffs(base2, jumped)
        log("P2_jump_diff", changed_fields=len(d_jump),
            top=dict(list(sorted(d_jump.items(),
                    key=lambda kv: abs(kv[1][1] - kv[1][0]),
                    reverse=True))[:14]))
        results["right_diff"] = d_right
        results["jump_diff"] = d_jump
        # published GS lives/hp at the same moments
        log("P2_gs_reads",
            lives_u8=mem.u8(ADDR_LIVES_GS),
            lives_u16=mem.u16(ADDR_LIVES_GS),
            hp_u16=mem.u16(ADDR_HP_GS),
            score=tel1["score"], grenades=tel1["grenades"],
            camera_fx=tel1["camera_fx"])

    # ---------------- P3: bounded attrition window -----------------
    # stand still up to 1200 frames; enemies usually punish that.
    tel_prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
    death = None
    for i in range(6):
        p.core.run(200, set())
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        evs = tel.events(tel_prev, cur)
        tel_prev = cur
        ptr_now = mem.u32(ADDR_PLAYER_PTR)
        log("P3_window", i=i, frame=cur["frame"], score=cur["score"],
            camera_fx=cur["camera_fx"], ptr=f"0x{ptr_now:08X}",
            lives_u8=mem.u8(ADDR_LIVES_GS), hp_u16=mem.u16(ADDR_HP_GS),
            events=[e["type"] for e in evs])
        if any(e["type"] == "death_candidate" for e in evs):
            death = i
            # struct snapshot right after death: hp/lives fields?
            ptr_now = mem.u32(ADDR_PLAYER_PTR)
            if 0x80080000 <= ptr_now < 0x80200000:
                dead = struct_dump(mem, ptr_now - 0x80000000)
                log("P3_death_struct",
                    hp_u16=mem.u16(ADDR_HP_GS),
                    lives_u8=mem.u8(ADDR_LIVES_GS),
                    lives_u16=mem.u16(ADDR_LIVES_GS))
            break
    if death is not None:
        ok = recover_v2(p, log=lambda *a: None)
        log("P3_recover_v2_after_death", ok=bool(ok),
            lives_u8=mem.u8(ADDR_LIVES_GS),
            lives_u16=mem.u16(ADDR_LIVES_GS),
            score=tel.snapshot(buttons=[],
                               frame=p.core.frames_run)["score"])
        g2 = ensure_mission(p, tries=4, log=lambda *a: None,
                            want_hp_cands=False)
        log("P3_recheck_gate", in_mission=bool(g2.get("in_mission")))
    else:
        log("P3_no_death_in_window")

    save()
    (json.dumps(tel_notes))
    print("probe done")


if __name__ == "__main__":
    main()
