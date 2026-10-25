#!/usr/bin/env python3
"""chopper_hunt.py — Issue #5 session-3: the chopper kill campaign.

Session-2 conclusion (issuecomment-6391740111 §5): the chopper
(hp_a4 300, h 206-228, drops the 0xB4E4 fallers) is the last live
combatant at the D7 pin; ground UP-lobs and bullets never connect.
Two paths named: (a) a JUMPING lob arc — the only untried
ground-reachable delivery; (b) overlay handler analysis.

Modes:
  reach   boot -> fixed-policy walk (grenades=0) -> on the D7 pin
          signature save `pin_ckpt` + dump the entity-bank RAM
          (0x8009C0E8..0x800C9A98) for static analysis + census.
  attack  boot -> load `pin_ckpt` -> run ONE arm:
            C   no-input control (600f) — chopper/faller cadence only
            J1  hop + UP+A lob at apex (timed apex frames)
            J2  hop + flat A lob at apex (arc at head height)
            J3  hop + UP+Y air fire burst
            G   standing UP+A ground lob (negative control, session-2
                says never connects — re-confirms at this anchor)
  dump    boot -> load `pin_ckpt` -> full-RAM bank dump only.

READ-ONLY instrumentation: no memory writes, deaths are real,
grenades are the game's own counter.  Evidence JSONL + report with
sha256 land in evidence/issue5_chopper_hunt/.
"""
import argparse
import hashlib
import json
import os
import sys
import time
import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _REPO)

from ps1play import labconfig
from issue4_controller import boot
import ps1play.agent.combat as combat

TABLE, STRIDE = combat.TABLE, combat.STRIDE
PLAYER_X = 0x0CA2E0
A_SCORE = 0x0EE318
GRENADES = 0x0EDCF4
PLAYER_HP = 0x0CA2F6
CKPT = "pin_ckpt"
EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_chopper_hunt")
DEAD_ST = (0x4BE4, 0x5CC8)


def log(*a):
    print("[ch]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def snap(m):
    return {"px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "flags": int(m.u32(0x0EE518)) & 0xFF,
            "gren": int(m.u8(GRENADES)),
            "hp": int(m.u16(PLAYER_HP)),
            "sec_state": int(m.u16(combat.SECTION_STATE)),
            "sec_flags": int(m.u16(combat.SECTION_FLAGS)),
            "sec_prog": int(m.u16(combat.SECTION_PROGRESS))}


def raw_slots(m):
    tv = m.ram[TABLE:TABLE + 24 * STRIDE].view("<u2").astype(
        np.int32).reshape(24, STRIDE // 2)
    out = []
    for s in range(1, 24):
        st = int(tv[s, 0])
        xw = ((int(tv[s, 61]) << 16) | int(tv[s, 60])) / 65536.0
        h = int(tv[s, 63])
        hp8E = int(tv[s, 71])
        hpA4 = int(tv[s, 82])
        if not st and not xw:
            continue
        out.append({"s": s, "st": st, "x": round(xw, 1), "h": h,
                    "hp8E": hp8E, "hpA4": hpA4})
    return out


CHOPPER_ST = (0xAA94, 0xABDC)   # session-2 confirmed alternating states


def chopper(m, px):
    """The chopper: its two alternating state words, else airborne with
    real HP >= 200 and h > 190 (fallers are h <= ~185, hpA4 30)."""
    best = None
    for sl in raw_slots(m):
        hit = (sl["st"] in CHOPPER_ST) or \
              (sl["hpA4"] >= 200 and sl["h"] > 190)
        if hit and sl["st"] not in DEAD_ST and abs(sl["x"] - px) < 500:
            d = abs(sl["x"] - px)
            if best is None or d < best[0]:
                best = (d, sl)
    return best[1] if best else None


def alive(m):
    s = snap(m)
    return s["flags"] == 0xFF and s["px"] != 0.0 and s["hp"] > 0


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_to_pin(p, m, J, max_chunks=140):
    """Fixed-policy walk to the D7 pin; returns final snap."""
    pol = combat.CombatPolicy()
    last_px, last_segs = None, None
    f0 = p.core.frames_run
    for c in range(max_chunks):
        px = px_of(m)
        s = snap(m)
        if not alive(m):
            J({"ev": "death_walk", "chunk": c, **s})
            log(f"DIED walking c{c} px={s['px']}")
            return s
        advanced = 0.0 if last_px is None else px - last_px
        intent = any("RIGHT" in (x.get("btns") or set())
                     for x in (last_segs or []))
        pol.observe(px, advanced, intent)
        pol.observe_section(combat.scan_section(m))
        scan = combat.scan_entities(m, px=px)
        segs = pol.decide(60, px, scan, grenades=0,
                          hp=int(m.u16(PLAYER_HP)))
        last_px, last_segs = px, segs
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
        pinned = px >= 1155.0     # the D7 clamp freezes px at 1164.0
        if c % 5 == 0 or pinned:
            J({"ev": "walk", "chunk": c, "mode": pol.mode,
               "chopper": chopper(m, px), "slots": raw_slots(m), **s})
        if pinned:
            # quiesce briefly so the anchor is not mid-swing, then save
            # BEFORE the clamp_clear escalation burns the grenades.
            p.core.run(10, set())
            s2 = snap(m)
            if alive(m) and s2["px"] >= 1150.0:
                p.save_state(CKPT)
                J({"ev": "PIN_ARRIVAL_SAVED", "chunk": c,
                   "slots": raw_slots(m), **s2})
                log(f"PIN anchor saved c{c} px={s2['px']:.0f} "
                    f"gren={s2['gren']} score={s2['score']}")
                return s2
            J({"ev": "pin_transit", "chunk": c, **s})
    return snap(m)


def do_reach(p, m, J, tag):
    s = walk_to_pin(p, m, J)
    if not alive(m):
        log("reach failed (death on the walk)")
        return 1
    # the anchor was already saved inside walk_to_pin on pin arrival;
    # here only the bank dump + confirmation census happen.
    dump_path = os.path.join(EVID, f"bank_{tag}.bin")
    lo, hi = 0x8009C0E8 - 0x80000000, 0x800C9B00 - 0x80000000
    with open(dump_path, "wb") as f:
        f.write(m.ram[lo:hi].tobytes())
    slots = raw_slots(m)
    rep = {"ev": "SAVED", "ckpt": CKPT, "snap": s,
           "slots": slots, "chopper": chopper(m, px_of(m)),
           "bank_dump": {"path": dump_path,
                         "lo": "0x8009C0E8", "hi": "0x800C9B00",
                         "sha256": sha_file(dump_path),
                         "bytes": os.path.getsize(dump_path)},
           "frames_total": p.core.frames_run}
    J(rep)
    log("REACH done: px=%s gren=%s score=%s sec=(0x%X,0x%X)"
        % (s["px"], s["gren"], s["score"],
           s["sec_state"], s["sec_flags"]))
    return 0


def face_dir(sl, px):
    return "RIGHT" if sl["x"] >= px else "LEFT"


def do_attack(p, m, J, arm, cycles=80):
    s0 = snap(m)
    ch0 = chopper(m, px_of(m))
    J({"ev": "arm_start", "arm": arm, "snap": s0, "chopper": ch0})
    log(f"arm {arm}: chopper={ch0} px={s0['px']} gren={s0['gren']}")
    results = []
    hp0 = s0["score"]
    gren0 = s0["gren"]
    connects = 0
    last_hop = -999
    for k in range(cycles):
        if not alive(m):
            J({"ev": "death_arm", "cycle": k, **snap(m),
               "results": results})
            log(f"DIED arm {arm} c{k}")
            break
        px = px_of(m)
        ch = chopper(m, px)
        if arm == "C":
            p.core.run(60, set())
        elif arm == "G":
            if ch is not None and (k % 8) < 8 and int(m.u8(GRENADES)) > 0:
                d = face_dir(ch, px)
                p.core.run(6, {"UP", "A", d})
                p.core.run(30, set())
                J({"ev": "throw", "arm": arm, "k": k, "kind": "up_lob",
                   "dx": round(ch["x"] - px, 1), "ch": ch,
                   **snap(m)})
            else:
                p.core.run(30, set())
        elif arm in ("J1", "J2", "J3"):
            if ch is not None and int(m.u8(GRENADES)) > 0 and \
                    k - last_hop >= 4:
                last_hop = k
                d = face_dir(ch, px)
                dx = ch["x"] - px
                p.core.run(3, {"B"})                    # hop
                p.core.run(8, set())                    # rise to apex
                if arm == "J1":
                    p.core.run(8, {"UP", "A", d})       # apex UP-lob
                elif arm == "J2":
                    p.core.run(8, {"A", d})             # apex flat lob
                else:
                    p.core.run(16, {"UP", "Y", d})      # apex air fire
                p.core.run(24, set())                   # land+settle
                sn = snap(m)
                con = sn["score"] > hp0
                hp0 = sn["score"]
                results.append({"k": k, "dx": round(dx, 1),
                                "ch_h": ch["h"], "ch_hp": ch["hpA4"],
                                "score": sn["score"], "connect": con})
                J({"ev": "throw", "arm": arm, "k": k, "kind": arm,
                   "dx": round(dx, 1), "ch": ch, "connect": con,
                   **sn})
                if con:
                    connects += 1
            else:
                p.core.run(20, set())
        # every cycle: census + hp_a4 tracking of the chopper slot
        if k % 4 == 0:
            chn = chopper(m, px_of(m))
            J({"ev": "census", "arm": arm, "k": k, "chopper": chn,
               **snap(m)})
            if chn is not None and ch0 is not None and \
                    chn["hpA4"] < ch0["hpA4"]:
                J({"ev": "CHOPPER_HP_DROP", "arm": arm, "k": k,
                   "from": ch0["hpA4"], "to": chn["hpA4"], **snap(m)})
                ch0 = chn
    fin = snap(m)
    chf = chopper(m, px_of(m))
    rep = {"arm": arm, "start": s0, "final": fin,
           "chopper_start": ch0, "chopper_final": chf,
           "score_delta": fin["score"] - s0["score"],
           "gren_used": gren0 - fin["gren"],
           "connects": connects, "alive": bool(alive(m)),
           "cycles": k + 1 if "k" in dir() else 0,
           "sec_final": {"state": fin["sec_state"],
                         "flags": fin["sec_flags"],
                         "prog": fin["sec_prog"]}}
    J({"ev": "arm_done", **rep})
    log(f"arm {arm} done: dScore={rep['score_delta']} "
        f"connects={connects} gren_used={rep['gren_used']} "
        f"alive={rep['alive']} "
        f"sec=(0x{fin['sec_state']:X},0x{fin['sec_flags']:X})")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True,
                    choices=["reach", "attack", "dump"])
    ap.add_argument("--arm", default="C",
                    choices=["C", "G", "J1", "J2", "J3"])
    ap.add_argument("--cycles", type=int, default=80)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    tag = time.strftime("%H%M%S")
    jf = open(os.path.join(EVID, f"{args.mode}_{args.arm}_{tag}.jsonl"),
              "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    if args.mode in ("attack", "dump"):
        try:
            p.load_state(CKPT)
        except Exception as e:
            log(f"no {CKPT}: {e} — run --mode reach first")
            return 1
    if args.mode == "reach":
        rc = do_reach(p, m, J, tag)
    elif args.mode == "dump":
        dump_path = os.path.join(EVID, f"bank_{tag}.bin")
        lo = 0x8009C0E8 - 0x80000000
        hi = 0x800C9B00 - 0x80000000
        with open(dump_path, "wb") as f:
            f.write(m.ram[lo:hi].tobytes())
        rep = {"bank_dump": {"path": dump_path, "lo": "0x8009C0E8",
                             "hi": "0x800C9B00",
                             "sha256": sha_file(dump_path),
                             "bytes": os.path.getsize(dump_path)},
               "snap": snap(m), "slots": raw_slots(m)}
        J(rep)
        log("bank dumped", rep["bank_dump"]["sha256"][:16])
        rc = 0
    else:
        rep = do_attack(p, m, J, args.arm, args.cycles)
        with open(os.path.join(
                EVID, f"report_{args.arm}_{tag}.json"), "w") as f:
            json.dump(rep, f, indent=1, default=str)
        rc = 0
    J({"ev": "done", "wall_s": round(time.time() - t0, 1),
       "frames": p.core.frames_run})
    jf.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
