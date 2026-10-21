#!/usr/bin/env python3
"""mission.py — 'do we actually CONTROL the game right now?' gate.

THE definition of being in the mission is input responsiveness: holding
RIGHT scrolls the whole world (huge RAM churn) while an idle window of
the same length churns far less. Continue/pause/menu screens ignore the
pad: input window ≈ idle window. A stab-probe (hp-band decayers) is NOT
a reliable gate — UI counters decay on menus too (false positives).

Gate loop (max tries):
  1. measure idle churn (60f) and input churn (60f holding RIGHT+Y)
  2. responsive?  -> IN (return hp-probe candidates too)
  3. else recover like a human: START (continue / unpause) x2,
     then move right to re-engage, retry
"""
import numpy as np

from ps1play.agent.memscan import MemScan


def _changed(p, frames, buttons):
    s0 = p.mem.snapshot()
    p.core.run(frames, buttons)
    n = int(np.count_nonzero(s0 != p.mem.snapshot()))
    p._advance()
    return n


def png(p, name, out_dir="/tmp/gate"):
    try:
        os.makedirs(out_dir, exist_ok=True)
        from PIL import Image
        rgb = p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).resize((320, 240)).save(
                os.path.join(out_dir, name))
    except Exception:
        pass


import os                                              # noqa: E402


def _run(p, frames, buttons, tick=None):
    """Run `frames`, ticking the GameShark engine after EVERY frame when
    a tick callable is supplied (hardware-GS cadence). With tick=None
    the behavior is exactly p.core.run() — legit callers are unaffected.
    This closes the 'freeze silently stops inside shared helpers' gap
    (issue #5 continuation §2): every frame-running path used by a
    cheat-assisted run must keep the per-frame GS cadence alive."""
    if tick is None:
        p.core.run(frames, buttons)
        return
    p.core.set_buttons(set(buttons))
    for _ in range(frames):
        p.core.run_frame()
        tick()


def responsive(p, reps=1, tick=None):
    """THE definitive in-control test, three independent signals:

    1. PAD MIRROR (static RE: 0x0D4948 tracks injected D-pad bits during
       gameplay, frozen on menus) — hold RIGHT: bit 0x20 must appear and
       clear on release.
    2. WORLD CHURN while holding RIGHT+Y — a real mission churns
       thousands of bytes when we run.
    3. SELF-PLAY GUARD (attract demo): release the pad — a REAL mission
       mirrors 0 when we press nothing; the ATTRACT DEMO keeps lighting
       bits up because it feeds its own scripted inputs (v15 lesson:
       the demo also churns 200k+, so churn alone cannot reject it).

    alive = pad toggles AND world churns AND nobody else presses keys."""
    _run(p, 6, set(), tick)
    self_play = False
    for _ in range(3):
        _run(p, 10, set(), tick)
        if p.mem.u16(0x0D4948) != 0:
            self_play = True
    w0 = p.mem.u16(0x0D4948)
    _run(p, 8, {"RIGHT"}, tick)
    w1 = p.mem.u16(0x0D4948)
    _run(p, 6, set(), tick)
    w2 = p.mem.u16(0x0D4948)
    p._advance()
    pad_ok = (w1 & 0x20) and not (w2 & 0x20) and not (w0 & 0x20)
    s0 = p.mem.snapshot()
    _run(p, 60, {"RIGHT", "Y"}, tick)
    churn = int(np.count_nonzero(s0 != p.mem.snapshot()))
    p._advance()
    return bool(pad_ok and churn > 900 and not self_play), \
        (int(w1), churn)


def recover(p, log=print, tick=None):
    """Human recovery from continue/pause screens — MINIMAL:
    ONE START (continue/unpause) + brief settle. The gate's own
    run-window provides movement; blind warmup just gets the player
    killed again (mission 1 opening is lethal to idlers).
    tick: optional per-frame GS tick so freezes survive recovery."""
    _run(p, 15, {"START"}, tick)
    _run(p, 90, set(), tick)
    p._advance()
    log("[gate] recovery: single START + settle")


def alive_probe(p, tick=None):
    """HP-band decayers (for calibration, NOT as the gate)."""
    p.save_state("_em")
    _run(p, 300, set(), tick)
    p._advance()
    scan = MemScan(p.mem)
    scan.reset()
    scan.between("u16", 90, 215)
    _run(p, 360, set(), tick)
    p._advance()
    scan.dec("u16")
    idx = np.flatnonzero(scan.masks["u16"])
    cands = [int(i) * 2 for i in idx if int(i) * 2 < 0x1FC000]
    p.load_state("_em")
    return cands


def ensure_mission(p, tries=6, log=print, want_hp_cands=True, tick=None):
    """Guarantee real input control; recover from any dead screen.
    tick: optional per-frame GS tick threaded into responsive/recover
    so an active freeze keeps its hardware cadence inside the gate."""
    evidence = []
    for k in range(tries):
        ok, (i1, r) = responsive(p, tick=tick)
        png(p, f"gate_{k}_{'in' if ok else 'out'}.png")
        evidence.append({"try": k, "idle": i1, "run": r, "in": ok})
        log(f"[gate] try{k}: idle={i1} run={r} -> "
            f"{'IN MISSION' if ok else 'dead screen'}")
        if ok:
            hp_cands = (alive_probe(p, tick=tick)
                        if want_hp_cands else [])
            return {"in_mission": True, "idle": i1, "run": r,
                    "hp_cands": len(hp_cands), "hp_cand_addrs":
                        [hex(a) for a in hp_cands[:8]], "evidence": evidence}
        recover(p, log=log, tick=tick)
    return {"in_mission": False, "evidence": evidence}


def idle_churn(p, frames=40):
    s0 = p.mem.snapshot()
    p.core.run(frames, set())
    n = int(np.count_nonzero(s0 != p.mem.snapshot()))
    p._advance()
    return n
