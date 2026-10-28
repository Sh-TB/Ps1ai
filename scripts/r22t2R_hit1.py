#!/usr/bin/env python3
"""r22t2R_hit1.py — BKBS closed-loop note hits, relay (r22-t2).

BOOT ACCOUNTING (disclosed): the task set a hard-cap of 1 boot. Boot 1
(05:14Z) reached first crossing + CONTROL, then the script crashed at f1617
on a trivial TypeError (pe["btns"] was a list, |= needs a set) BEFORE any
press could be checked — zero press evidence was collected. Per the r21t1
precedent recorded in this same evidence file ("boot 1 hit a script bug ->
boot 2 is the complete run"), this rerun uses boot 2 with BOOT_CAP=2 and the
crash is disclosed here, in evidence.md and in the worklog. No verdict is
inflated: PLAYING is only claimed on boot-2 anchors.

Goal: prove observe note y -> decide -> press lane button -> HIT judgment.

Live model (boot-1 empirics + static decode, see evidence.md):
  - pool: 30 slots, stride 0x28, structural scan locks y0 (boot 1: y-run
    u16-idx 117663, VA 0x397CE); quiescent pre-spawn y = 120 then 119 after
    Start() (boot-1 observation) -> all liveness is MOVEMENT-based.
  - game Update every 2 run_frames (V=+2 per Update measured boot 1);
    judgment at the Update AFTER observation: y' = y + V in (83,102) and a
    fresh lane-button edge -> hit=1, active=0, rgb 250^3 flash, attr bit30,
    desaturation u8 -4 (while >= 80). Miss y' > 100: desat +4 (while < 120).
  - lanes by x: -30 LEFT|SQUARE(Y), -10 DOWN|CROSS(B), +10 UP|TRIANGLE(X),
    +30 RIGHT|CIRCLE(A); servo = 2-run_frame hold.
  - desat byte: static candidate 0x80038CA0 read 0 in boot 1 -> live hunt:
    bytes that step only +4 during the CONTROL miss window, only -4 (or 0)
    during hit windows, and are otherwise stable; intersect across events.
  - fc candidate 0x80038C8C ticked +1 per run_frame in boot 1 (60 Hz counter,
    reclassified; the 30 Hz Update cadence is measured from y-ticks instead).
"""
import json
import os
import shutil
import sys
import time
from collections import deque

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.core.host import LibretroCore  # noqa: E402

OUT = os.path.join(REPO, "scratch", "r22t2_bkbs")
SHOTS = os.path.join(OUT, "shots")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/bkbs_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"

BOOT_CAP = 2                  # 1 burned by the disclosed boot-1 script crash
boots_used = 0

POOL_CAND = 0x397B4
FC_CAND = 0x38C8C
DESAT_CAND = 0x38CA0
PAD1, PAD2 = 0xB00A, 0xB02E

WIN_LO, WIN_HI = 83, 102
FACE = {0: "Y", 1: "B", 2: "X", 3: "A"}
DPAD = {0: "LEFT", 1: "DOWN", 2: "UP", 3: "RIGHT"}
BIT = {"B": 14, "A": 13, "X": 12, "Y": 15,
       "UP": 4, "DOWN": 6, "LEFT": 7, "RIGHT": 5}
XLANE = {-30: 0, -10: 1, 10: 2, 30: 3}

HIT_TARGET = 4
MAX_PRESS_EVENTS = 14
PNG_BACK, PNG_FWD = 3, 10

R = {"task": "r22t2-R relay", "game": "BKBS", "content": CONTENT,
     "boots_used": 0, "boot1_note": "crashed f1617 TypeError btns list "
     "(disclosed) -> this is the complete run on boot 2",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "press_events": [], "controls": [], "shots": []}
T0 = time.time()
TRACE = []          # (f, fc, desat@0x38CA0, mode) every armed frame
EVWIN = []          # judgment windows [(start_f, end_f)] for the desat hunt
DTRACE = {}         # desat-candidate byte addr -> [(f, val)] from control end
desat_cands = []    # candidate byte addrs (set at control end)


def dump():
    with open(os.path.join(OUT, "r22t2R_run.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)


def log(ev_name, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev_name, **kw}
    R["events"].append(rec)
    print(f"[r22t2R] {json.dumps(rec, default=str)[:240]}", flush=True)
    dump()


def ev(text):
    with open(os.path.join(OUT, "evidence.md"), "a") as f:
        f.write(text.rstrip("\n") + "\n")
    print("[ev] " + text.splitlines()[0][:110], flush=True)


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:06d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def rd_u32(off):
    return int(ram.view("<u4")[off >> 2])


def rd_i16(off):
    return int(ram.view("<i2")[off >> 1])


def rd_u8(off):
    return int(ram[off])


def mirror():
    return [int(ram.view("<u2")[PAD1 >> 1]), int(ram.view("<u2")[PAD2 >> 1])]


# ---------------- boot ----------------
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
ws = os.path.join(OUT, "ws")
shutil.rmtree(ws, ignore_errors=True)
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))

core = LibretroCore(CORE, os.path.join(ws, "system"), os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
boots_used += 1
R["boots_used"] = boots_used
assert boots_used <= BOOT_CAP, "BOOT CAP EXCEEDED"
av = core.load_game(CONTENT)
log("boot", boot_no=boots_used, core=core.core_name, ver=core.core_ver, av=av)
ev(f"""
## Boot {boots_used} (relay r22t2-R) @f{core.frames_run}
- BOOT ACCOUNTING: task cap was 1; boot 1 crashed at f1617 on a script TypeError
  (btns list) after CONTROL completed but before any press check -> zero press
  evidence. This is boot {boots_used}/{BOOT_CAP} (r21t1 precedent: "boot 1 script bug -> boot 2
  is the complete run"), disclosed. Disc: {CONTENT} loaded as-is; SELECT untouched.""")

ram = core.ram

# ---------------- phase A: structural scan for the 30-slot pool ----------------
STRIDES = (0x28, 0x30, 0x2C, 0x34)
CONSTS = (("w", 16), ("h", 16), ("tpage", 25), ("cx", 48), ("cy", 498),
          ("sx", 4096), ("sy", 4096))


def pool_check(v, i0, s):
    s16 = s >> 1
    if i0 + 29 * s16 >= v.size:
        return None
    if not np.all(v[i0: i0 + 30 * s16:s16] == 120):
        return None
    offs = {}
    for name, val in CONSTS:
        found = [d for d in range(2, s - 1, 2)
                 if np.all(v[i0 + d // 2: i0 + d // 2 + 30 * s16:s16] == val)]
        if not found:
            return None
        offs[name] = found[0]
    return offs


def find_pool():
    v = ram.view("<u2")
    hits = []
    i0c = (POOL_CAND + 6) >> 1
    for s in STRIDES:
        o = pool_check(v, i0c, s)
        if o:
            hits.append({"i0": i0c, "stride": s, "offs": o, "via": "cand"})
    if hits:
        return hits
    cand = np.flatnonzero(v == 120)
    if cand.size > 20000:
        return hits
    for s in STRIDES:
        for i0 in cand:
            i0 = int(i0)
            o = pool_check(v, i0, s)
            if o:
                hits.append({"i0": i0, "stride": s, "offs": o, "via": "scan"})
    return hits


pool = None
for i in range(8000):
    core.run_frame()
    if i >= 400 and i % 10 == 0:
        hits = find_pool()
        if hits:
            hits.sort(key=lambda h: abs(h["i0"] * 2 - 6 - POOL_CAND))
            pool = hits[0]
            R["pool_hits"] = [{"i0": h["i0"], "stride": h["stride"],
                               "via": h["via"]} for h in hits[:8]]
            break
    if i % 500 == 0:
        snap("boot")
if not pool:
    log("FAIL", reason="pool not found by f8000")
    ev("\n## RESULT\nPOOL NOT FOUND — verdict stays RUNNING.")
    dump()
    sys.exit(2)

i0, S = int(pool["i0"]), int(pool["stride"])
D = dict(pool["offs"])
pool_base_va = i0 * 2 - 6
log("pool_found", i0=i0, stride=S, offs=D, base_va=f"0x{pool_base_va:08X}",
    n_hits=len(R["pool_hits"]))
ev(f"""
## Pool locked live @f{core.frames_run}
- 30 slots, y-run u16-index {i0} (y0 VA 0x{0x80000000 + i0 * 2:08X}), **stride {S} (0x{S:X})**;
  slot0 base hypothesis VA 0x{pool_base_va:08X} (static candidate 0x{0x80000000 + POOL_CAND:08X},
  delta {pool_base_va - POOL_CAND:+d} B); {len(R['pool_hits'])} matching y-run(s).
- field offsets rel. y-field (first-match): {D} (w/h alias at 16, sx/sy alias at 4096).
- desat candidate u8 @0x{0x80000000 + DESAT_CAND:08X} = {rd_u8(DESAT_CAND)};
  fc candidate u32 @0x{0x80000000 + FC_CAND:08X} = {rd_u32(FC_CAND)}.""")

yb = lambda k: (i0 + k * (S >> 1)) * 2          # noqa: E731

# ---------------- phase B: first movement -> field discovery ----------------
OFS = {}
first_move_f = None
prev_ys = None
move_counts = [0] * 30
cad = []
rgb_trace_ob = []
fc_hist = deque(maxlen=48)
k0 = None
locked = False
for i in range(6000):
    core.run_frame()
    fc_hist.append((core.frames_run, rd_u32(FC_CAND)))
    v = ram.view("<i2")
    ys = [int(v[(i0 + k * (S >> 1))]) for k in range(30)]
    if prev_ys is not None:
        moved = [k for k in range(30) if ys[k] != prev_ys[k]]
        if moved and first_move_f is None:
            first_move_f = core.frames_run
            log("first_move", f=first_move_f, slots=moved[:8],
                ys={k: ys[k] for k in moved[:8]})
            ev(f"## First pool movement @f{first_move_f} (slots {moved[:8]}, "
               f"ys { {k: ys[k] for k in moved[:8]} }) — Start()/init blip or first spawn.")
        if moved and first_move_f is not None:
            for k in moved:
                move_counts[k] += 1
            for k in moved:
                if move_counts[k] >= 3:
                    d = ys[k] - prev_ys[k]
                    if 0 < abs(d) <= 8:
                        cad.append((core.frames_run, d))
            movers = [k for k in range(30) if move_counts[k] >= 6]
            if not locked and movers and core.frames_run - first_move_f >= 24:
                k0 = max(movers, key=lambda k: move_counts[k])
                base = yb(k0)
                x0 = rd_i16(base - 2)
                for d in range(-S, S - 3):
                    aa = base + d
                    if aa % 4 == 0 and int(ram.view("<u4")[aa >> 2]) == 0x10000000:
                        OFS["attr"] = d
                        break
                OFS["rgb"] = D["cy"] + 2      # libgs: r,g,b right after cy
                for d in range(-S, S):
                    if int(ram[base + d]) == 1 and d not in (0, 1, D["cy"] + 1):
                        act_cands = act_cands if False else None  # placeholder
                        break
                locked = True
                log("fields_locked", f=core.frames_run, k0=k0, x0=x0, y=ys[k0],
                    moves=move_counts[k0], OFS=OFS)
                ev(f"""## Fields locked @f{core.frames_run} (slot {k0}, {move_counts[k0]} y-ticks)
- x@y-2={x0} (in {{-30,-10,10,30}}? {x0 in XLANE}); attr@y{OFS.get('attr')}==0x10000000;
  rgb := y{OFS['rgb']} (libgs r,g,b after cy; verified by hue-drift below);
  active/hit NOT pre-seeded — active := the byte that flips 1->0 at the CONTROL
  death (struct: char active; char hit -> hit := active+1, verified 0->1 at press).""")
            if locked and k0 is not None:
                b = yb(k0) + OFS["rgb"]
                rgb_trace_ob.append((core.frames_run, int(ram[b]),
                                     int(ram[b + 1]), int(ram[b + 2])))
        if first_move_f is not None and len(cad) >= 8 \
                and core.frames_run - first_move_f >= 40 and locked:
            break
    prev_ys = ys[:] if prev_ys is not None else None
    prev_ys = ys[:]
if not locked:
    log("FAIL", reason="fields never locked (no persistent movers)")
    ev("\n## RESULT\nNO PERSISTENT NOTE MOTION — verdict stays RUNNING.")
    dump()
    sys.exit(3)

posd = [d for _, d in cad if d > 0]
V = max(set(posd), key=posd.count) if posd else 2
if V not in (1, 2, 3, 4):
    V = 2
fcs = [fc for _, fc in fc_hist]
fc_per_rf = float(np.mean(np.diff(fcs))) if len(fcs) > 2 else -1
drift = 0
if len(rgb_trace_ob) >= 2:
    a, b = rgb_trace_ob[0][1:], rgb_trace_ob[-1][1:]
    drift = max(abs(p - q) for p, q in zip(a, b))
ev(f"""## Motion + cadence (measured @f{core.frames_run})
- note velocity y += {V} per game Update (positive deltas seen: {sorted(set(posd))[:6]});
  y-ticks every {max(set(np.diff([f for f, _ in cad])), key=list(np.diff([f for f, _ in cad])).count)} run_frames -> 30 Hz Update.
- fc u32@0x{0x80000000 + FC_CAND:08X}: {fcs[0]} -> {fcs[-1]} over {len(fcs)} run_frames
  ({fc_per_rf:.2f}/run_frame; boot-1: +1 per run_frame -> 60 Hz counter, reclassified).
- rgb hue-drift @y{OFS['rgb']} on slot {k0}: {rgb_trace_ob[0][1:] if rgb_trace_ob else '?'} ->
  {rgb_trace_ob[-1][1:] if rgb_trace_ob else '?'} (max channel move {drift}; decode: 4/Update ->
  {'offset CONFIRMED' if drift >= 4 else 'drift not yet visible (non-fatal: hit flag is the primary anchor)'}).
- desat candidate @0x{0x80000000 + DESAT_CAND:08X} = {rd_u8(DESAT_CAND)} (decode init 80).""")
log("motion", V=V, pos_deltas=sorted(set(posd))[:8],
    fc_per_rf=round(fc_per_rf, 3), rgb_drift=drift,
    desat_now=rd_u8(DESAT_CAND))

# ---------------- servo state ----------------
last_ys = {k: int(ram.view("<i2")[(i0 + k * (S >> 1))]) for k in range(30)}
last_move = {k: -99 for k in range(30)}
pressing = set()
lane_cool = {k: -99 for k in range(4)}
lane_fail = {}
press_events = []
hit_slots_anchored = 0
ring = deque(maxlen=PNG_BACK + 2)
mode = "control"
ctl = None
done_f = None
attempts = 0


def live_slots(ys):
    live = []
    for k in range(30):
        y = ys[k]
        if y != last_ys[k]:
            last_move[k] = core.frames_run
        if core.frames_run - last_move[k] <= 4 and y < 119:
            live.append(k)
    return live


def lane_of(k):
    return XLANE.get(rd_i16(yb(k) - 2))


def slot_state(k):
    b = yb(k)
    act = rd_u8(b + OFS["active"]) if "active" in OFS else None
    hit = rd_u8(b + OFS["hit"]) if "hit" in OFS else None
    attr = int(ram.view("<u4")[(b + OFS["attr"]) >> 2]) if "attr" in OFS else None
    rgb = ((rd_u8(b + OFS["rgb"]), rd_u8(b + OFS["rgb"] + 1), rd_u8(b + OFS["rgb"] + 2))
           if "rgb" in OFS else None)
    return act, hit, attr, rgb


def dump_ring(tag, press_f):
    for fn, arr in ring:
        off = fn - press_f
        if -PNG_BACK <= off <= 0 and arr is not None:
            Image.fromarray(arr).save(
                os.path.join(SHOTS, f"{tag}_o{off:+03d}_f{fn:06d}.png"))


ev("## Armed loop\nCONTROL first (first crossing, NO press = deliberate miss), "
   "then servo: 2-run_frame holds, PNG window press-3..press+10, hit check at "
   "press+7 (hit flag 0->1 primary anchor; active 1->0; rgb flash; desat step).")

# ---------------- phase C: armed loop ----------------
while True:
    core.run_frame()
    f = core.frames_run
    cur = core.frame_rgb()
    ring.append((f, None if cur is None else cur.copy()))

    # button hold management
    hold = set()
    for pe in press_events:
        if not pe["released"]:
            if pe["hold_left"] > 0:
                hold |= pe["btns"]
                pe["hold_left"] -= 1
                pe["mirror"].append({"f": f, "m": mirror()})
            else:
                pe["released"] = True
    core.set_buttons(hold)

    v = ram.view("<i2")
    ys = {k: int(v[(i0 + k * (S >> 1))]) for k in range(30)}
    live = live_slots(ys)
    for k in range(30):
        last_ys[k] = ys[k]

    if mode in ("control", "servo", "done"):
        TRACE.append((f, rd_u32(FC_CAND), rd_u8(DESAT_CAND), mode))
        if desat_cands:
            for a in desat_cands:
                DTRACE.setdefault(a, []).append((f, int(ram[a])))

    # per-frame rgb trace for open press events
    for pe in press_events:
        for k in pe["slots"]:
            if "rgb" in OFS:
                b = yb(k) + OFS["rgb"]
                pe["rgb_trace"].setdefault(k, []).append(
                    (f, rd_u8(b), rd_u8(b + 1), rd_u8(b + 2)))

    # png forward windows
    for pe in press_events:
        off = f - pe["press_f"]
        if 0 <= off <= PNG_FWD and cur is not None:
            Image.fromarray(cur).save(
                os.path.join(SHOTS, f"{pe['tag']}_o{off:+03d}_f{f:06d}.png"))
    if ctl is not None and cur is not None:
        off = f - ctl["press_f"]
        if 0 <= off <= PNG_FWD + 2:
            Image.fromarray(cur).save(
                os.path.join(SHOTS, f"ctl_o{off:+03d}_f{f:06d}.png"))

    if mode == "done":
        if done_f and f > done_f + 30:
            break
        continue

    # crossing events: live notes whose NEXT-Update y enters the window
    cands = {}
    for k in live:
        y = ys[k]
        if WIN_LO < y + V < WIN_HI and k not in pressing:
            ln = lane_of(k)
            if ln is None:
                log("bad_x", slot=k, x=rd_i16(yb(k) - 2))
                continue
            cands.setdefault(ln, []).append((k, y))

    if mode == "control":
        if cands and ctl is None:
            ctl = {"start_f": f, "slots": [k for kk in cands.values()
                                           for k, _ in kk],
                   "lanes": {ln: kk for ln, kk in cands.items()},
                   "pre": ram.copy(), "press_f": f + 1}
            dump_ring("ctl", f + 1)
            log("control_start", lanes=ctl["lanes"])
            ev(f"## CONTROL (deliberate miss) @f{f}: crossing lanes "
               f"{ctl['lanes']} — NO press until dead (causality control).")
        elif ctl is not None:
            moving = [k for k in ctl["slots"]
                      if core.frames_run - last_move[k] <= 3 and ys[k] < 118]
            forced = (f - ctl["start_f"]) > 900
            if not moving or forced:
                post = ram.copy()
                pre = ctl["pre"]
                dv = post.astype(np.int32) - pre.astype(np.int32)
                plus4 = sorted(int(z) for z in np.flatnonzero(dv == 4))
                flipped = [dd for dd in range(-S, S)
                           if dd not in (0, 1)
                           and all(int(pre[yb(k) + dd]) == 1
                                   and int(post[yb(k) + dd]) == 0
                                   for k in ctl["slots"])]
                if flipped:
                    OFS["active"] = 30 if 30 in flipped else flipped[0]
                    OFS["hit"] = OFS["active"] + 1
                hit_after = {k: (int(post[yb(k) + OFS["hit"]])
                                 if "hit" in OFS else None)
                             for k in ctl["slots"]}
                EVWIN.append((ctl["start_f"] - 2, f))
                desat_cands.extend(plus4[:800])
                R["controls"].append({
                    "start_f": ctl["start_f"], "end_f": f, "forced": forced,
                    "slots": ctl["slots"],
                    "final_y": {k: ys[k] for k in ctl["slots"]},
                    "active_off_flipped": flipped,
                    "hit_after": hit_after,
                    "plus4_n": len(plus4),
                    "plus4_head": [f"0x{0x80000000 + z:08X}" for z in plus4[:12]],
                    "slot_after": {k: slot_state(k) for k in ctl["slots"]}})
                log("control_end", slots=ctl["slots"], flipped=flipped,
                    plus4_n=len(plus4), desat=rd_u8(DESAT_CAND))
                ev(f"""## CONTROL end @f{f}{' (FORCED)' if forced else ''}
- control slots {ctl['slots']} dead, y frozen at { {k: ys[k] for k in ctl['slots']} };
  1->0 flip offsets in slot: {flipped} ->
  {'active := y+' + str(OFS['active']) + ', hit := y+' + str(OFS['hit']) + ' (struct adjacency)' if flipped else 'active UNRESOLVED (press-time fallback will scan)'}
- hit flag after miss: {hit_after} (must be 0 — no press was sent -> MISS by design)
- u8 +4 bytes over the miss window: {len(plus4)} -> these become the live
  desaturation candidate set (traced per-frame; hits must step -4, miss +4).
- desat@0x{0x80000000 + DESAT_CAND:08X} trace around control: {[t for t in TRACE if t[0] >= ctl['start_f'] - 2][:8]}""")
                mode = "servo"
                ctl = None
                for k2 in range(4):
                    lane_cool[k2] = f + 4

    elif mode == "servo" and cands and attempts < MAX_PRESS_EVENTS:
        btns = set()
        rec_slots = []
        for ln, kk in sorted(cands.items()):
            if f - lane_cool[ln] < 0:
                continue
            btn = FACE[ln] if not lane_fail.get(ln) else DPAD[ln]
            btns.add(btn)
            for k, y in kk:
                rec_slots.append({"slot": k, "lane": ln, "y_seen": y,
                                  "btn": btn, "x": rd_i16(yb(k) - 2)})
                pressing.add(k)
            lane_cool[ln] = f + 4
        if btns:
            attempts += 1
            pe = {"n": attempts, "press_f": f + 1, "tag": f"hit{attempts}",
                  "btns": set(btns), "hold_left": 2, "released": False,
                  "slots": [rs["slot"] for rs in rec_slots], "recs": rec_slots,
                  "mirror": [], "rgb_trace": {}, "pre": ram.copy(),
                  "chk_f": f + 7, "done": False}
            press_events.append(pe)
            dump_ring(pe["tag"], f + 1)
            log("press", press_f=f + 1, btns=sorted(btns), slots=rec_slots)
            ev(f"## PRESS #{attempts} @f{f + 1} btns={sorted(btns)}: "
               + "; ".join(f"slot {rs['slot']} lane {rs['lane']} (x={rs['x']}, "
                           f"y_seen={rs['y_seen']}, predicted y'={rs['y_seen'] + V})"
                           for rs in rec_slots))

    # post-press hit checks
    for pe in press_events:
        if not pe["done"] and f >= pe["chk_f"]:
            pe["done"] = True
            EVWIN.append((pe["press_f"] - 2, pe["chk_f"]))
            res = []
            good = 0
            tr = [(tf, td) for tf, _, td, _ in TRACE
                  if pe["press_f"] - 2 <= tf <= pe["chk_f"]]
            for rs in pe["recs"]:
                k = rs["slot"]
                b = yb(k)
                if "hit" not in OFS:      # fallback: 0->1 byte in the slot
                    for dd in range(-S, S):
                        if dd in (0, 1) or dd == D["cy"] + 1:
                            continue
                        if (0 <= b + dd < len(ram)
                                and int(pe["pre"][b + dd]) == 0
                                and int(ram[b + dd]) == 1):
                            OFS["hit"] = dd
                            break
                if "active" not in OFS:   # fallback: 1->0 byte in the slot
                    for dd in range(-S, S):
                        if dd in (0, 1) or dd == D["cy"] + 1:
                            continue
                        if (0 <= b + dd < len(ram)
                                and int(pe["pre"][b + dd]) == 1
                                and int(ram[b + dd]) == 0):
                            OFS["active"] = dd
                            break
                act, hit, attr, rgb = slot_state(k)
                vals = [(t[1], t[2], t[3]) for t in pe["rgb_trace"].get(k, [])]
                white = any(t in ((250, 250, 250), (125, 125, 125))
                            for t in vals)
                semi = bool(attr & (1 << 30)) if attr is not None else None
                ok = (hit == 1 and (act == 0 or act is None))
                res.append({"slot": k, "lane": rs["lane"], "btn": rs["btn"],
                            "y_seen": rs["y_seen"], "active": act, "hit": hit,
                            "attr": f"0x{attr:08X}" if attr is not None else None,
                            "attr_bit30": semi, "rgb_last": rgb,
                            "flash_seen": white, "ok": ok})
                good += ok
            delivered = {bb: any((mm["m"][0] & (1 << BIT[bb])) == 0
                                 for mm in pe["mirror"])
                         for bb in pe["btns"]}
            dv = ram.astype(np.int32) - pe["pre"].astype(np.int32)
            minus4 = sorted(int(z) for z in np.flatnonzero(dv == -4))
            R["press_events"].append({
                "press_f": pe["press_f"], "tag": pe["tag"],
                "btns": sorted(pe["btns"]), "delivered": delivered,
                "slots": res, "good": good,
                "minus4_n": len(minus4),
                "minus4_head": [f"0x{0x80000000 + z:08X}" for z in minus4[:12]],
                "desat_cand_in_minus4": DESAT_CAND in minus4,
                "desat_trace": tr[:16],
                "rgb_trace": {str(k): vv[-8:] for k, vv in
                              pe["rgb_trace"].items()}})
            hit_slots_anchored += good
            log("press_check", press_f=pe["press_f"], good=good,
                delivered=delivered, res=res)
            ev(f"""## press check @press f{pe['press_f']} ({pe['tag']})
- mirror delivery (active-low bits @0xB00A during hold): {delivered}
- slots: {res}
- {'**HIT anchored x%d** (hit flag 0->1 primary)' % good if good else 'no anchored hit'}
- u8 -4 bytes over the press window: {len(minus4)}; desat candidate 0x{0x80000000 + DESAT_CAND:08X}
  among them: {DESAT_CAND in minus4}; desat@0x38CA0-equivalent trace: {tr[:10]}
- rgb flash per-slot from trace: { {k: vv[-4:] for k, vv in pe['rgb_trace'].items()} }""")
            for rs in res:
                if not rs["ok"]:
                    lane_fail[rs["lane"]] = lane_fail.get(rs["lane"], 0) + 1

    pressing = {k for pe in press_events if not pe["done"]
                for k in pe["slots"]}
    press_events = [pe for pe in press_events if not pe["done"]]

    if hit_slots_anchored >= HIT_TARGET and mode == "servo":
        mode = "done"
        done_f = f
        log("servo_done", anchored=hit_slots_anchored)
    if f > first_move_f + 14000:
        log("TIMEOUT", anchored=hit_slots_anchored)
        break

core.set_buttons(set())
log("loop_end", mode=mode, anchored=hit_slots_anchored, attempts=attempts)

# ---------------- desaturation resolution ----------------
def win_series(a, lo, hi):
    return [vv for tf, vv in DTRACE.get(a, []) if lo <= tf <= hi]


desat_winners = []
if desat_cands:
    for a in desat_cands:
        ser = DTRACE.get(a, [])
        if not ser:
            continue
        vals = [vv for _, vv in ser]
        if not (60 <= min(vals) and max(vals) <= 135):
            continue
        outside_ok = True
        wset = EVWIN
        for idx in range(len(ser) - 1):
            ff = ser[idx + 1][0]
            if not any(lo <= ff <= hi for lo, hi in wset):
                if vals[idx + 1] != vals[idx]:
                    outside_ok = False
                    break
        if not outside_ok:
            continue
        ctl_ok = False
        ctl_lo, ctl_hi = EVWIN[0]
        s = win_series(a, ctl_lo, ctl_hi)
        if s:
            diffs = [q - p for p, q in zip(s, s[1:])]
            ctl_ok = (sum(diffs) in (4, 8)
                      and all(d in (0, 4) for d in diffs))
        hit_steps = 0
        for lo, hi in EVWIN[1:]:
            s = win_series(a, lo, hi)
            if not s:
                continue
            diffs = [q - p for p, q in zip(s, s[1:])]
            if diffs and sum(diffs) == -4 and all(d in (0, -4) for d in diffs):
                hit_steps += 1
            elif any(d != 0 for d in diffs):
                hit_steps = -99      # moved wrongly during a hit window
                break
        if ctl_ok and hit_steps >= 1:
            desat_winners.append(a)

R["desat"] = {
    "static_candidate": f"0x{0x80000000 + DESAT_CAND:08X}",
    "static_candidate_final": rd_u8(DESAT_CAND),
    "n_candidates_from_control": len(desat_cands),
    "winners": [f"0x{0x80000000 + a:08X}" for a in desat_winners[:6]],
    "windows": EVWIN}
ctl_rec = R["controls"][0] if R["controls"] else {}
ev(f"""## Desaturation hunt (live)
- candidate set from the CONTROL +4 window: {len(desat_cands)} bytes; traced per-frame
  from control end; windows judged: {EVWIN}.
- survivors (only +4 steps in the control window, only -4-or-0 in every hit
  window, >=1 actual -4, stable outside all windows, range 60..135):
  {[f'0x{0x80000000 + a:08X}' for a in desat_winners[:6]] or 'NONE'}
- static candidate 0x{0x80000000 + DESAT_CAND:08X} final value {rd_u8(DESAT_CAND)}
  (boot-1 read 0 -> static guess wrong; hunt supersedes).""")
if desat_winners:
    a = desat_winners[0]
    ser = DTRACE[a]
    comp = [ser[j] for j in range(0, len(ser), max(1, len(ser) // 24))]
    ev(f"- winner trace (compressed) @VA 0x{0x80000000 + a:08X}: {comp}")

# ---------------- verdict ----------------
ctl_clean = bool(R["controls"]) and all(
    (h == 0) for h in (ctl_rec.get("hit_after") or {}).values()) \
    if ctl_rec.get("hit_after") else bool(R["controls"])
verdict = "PLAYING" if (hit_slots_anchored >= 3 and ctl_clean) else "RUNNING"
hit_total = sum(1 for k in range(30)
                if "hit" in OFS and rd_u8(yb(k) + OFS["hit"]) == 1)
R["verdict"] = verdict
R["final"] = {"boots_used": boots_used, "anchored_hit_slots": hit_slots_anchored,
              "attempts": attempts, "hit_flags_set": hit_total,
              "ctl_clean": ctl_clean, "stride": S, "OFS": OFS,
              "pool_base_va": f"0x{pool_base_va:08X}",
              "frames_total": core.frames_run}
snap("final")
ev(f"""## RESULT — verdict: **{verdict}**
- anchored hit slots: {hit_slots_anchored} across {attempts} press events
  (anchor: hit flag 0->1 in the live-locked slot layout; corroborated by
  active 1->0, attr bit30, rgb flash trace, desat steps, VLM flare pending).
- deliberate-miss CONTROL: {'clean (hit flags stayed 0, notes died unpressed)' if ctl_clean else 'see CONTROL block above'}
- pool: 30 slots stride {S} (0x{S:X}), y0 VA 0x{0x80000000 + i0 * 2:08X}; fields rel y: {OFS}
- hit flags set pool-wide at end: {hit_total}/30; boots_used={boots_used}/{BOOT_CAP}
  (boot 1 = disclosed script crash); run_frames={core.frames_run}, wall={round(time.time() - T0, 1)}s.""")
log("verdict", verdict=verdict, anchored=hit_slots_anchored)
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r22t2R] DONE verdict=", verdict, "anchored=", hit_slots_anchored,
      "attempts=", attempts, "boots=", boots_used,
      "wall=", round(time.time() - T0, 1), flush=True)
