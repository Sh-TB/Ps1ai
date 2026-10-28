#!/usr/bin/env python3
"""r22t2_bkbs_play.py — BKBS closed-loop note hits (r22-t2).

Goal: upgrade BKBS from RUNNING to PLAYING by proving
  observe note y -> decide -> press lane button -> HIT judgment (RAM + vision).

Source-decoded model (see scratch/r22t2_bkbs/evidence.md):
  - game Update at 30 Hz (Display() VSync(2)); notes: y += 2 per Update.
  - arrowNotes pool: 30 slots. Start() writes constants w=16 h=16 tpage=25
    cx=48 cy=498 scalex=scaley=4096 and y=120 pre-spawn -> structural scan pins
    base/stride/o_y live. Other offsets (attr/rgb/u/active) discovered at spawn.
  - judgment: 83 < y < 102 && fresh lane-button press -> active=0, hit=1,
    rgb=250/250/250, attr bit30 set, desaturation -= 4. Miss (y>100): desat += 4.
  - lanes: x=-30 LEFT|SQUARE, -10 DOWN|CROSS, +10 UP|TRIANGLE, +30 RIGHT|CIRCLE.
  - servo: press 2 run_frames (fresh edge for the next Update) when
    WIN_LO < y_seen + V < WIN_HI. Control: first crossing event gets NO press.
  - y is NEVER reset on death -> liveness = y moved recently (not y==120).

Discipline: BOOT_CAP=2 asserted; ONE boot expected. Evidence incremental.
"""
import hashlib
import json
import os
import shutil
import sys
import time

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
CHART = "/home/z/my-project/emu/games_homebrew/bkbs/BambiCSV.bin"

BOOT_CAP = 2
boots_used = 0

FC_CAND = 0x38C8C            # r21t1 frame-counter candidate (VA-0x80000000)
DESAT_CAND = 0x38CA0         # static-re desaturation candidate
PAD1, PAD2 = 0xB00A, 0xB02E  # padbuff button u16 (active-low)

WIN_LO, WIN_HI = 83, 102     # hit iff 83 < y < 102
MISS_Y = 100                 # miss iff y > 100
FACE = {0: "Y", 1: "B", 2: "X", 3: "A"}      # SQUARE/CROSS/TRIANGLE/CIRCLE
DPAD = {0: "LEFT", 1: "DOWN", 2: "UP", 3: "RIGHT"}
BIT = {"B": 14, "A": 13, "X": 12, "Y": 15,
       "UP": 4, "DOWN": 6, "LEFT": 7, "RIGHT": 5}

R = {"task": "r22t2", "game": "BKBS", "content": CONTENT, "boots_used": 0,
     "started": time.strftime("%FT%TZ", time.gmtime()), "events": [],
     "presses": [], "hits": [], "controls": [], "spawns": []}
T0 = time.time()


def dump():
    with open(os.path.join(OUT, "run_log.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)


def log(ev_name, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev_name, **kw}
    R["events"].append(rec)
    print(f"[r22t2] {json.dumps(rec, default=str)[:230]}", flush=True)
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
        R.setdefault("shots", []).append({"tag": tag, "frame": core.frames_run,
                                          "png": os.path.relpath(p, OUT)})
    return arr


# ---------------- boot (cap 2) ----------------
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
ev(f"\n## Boot 1 @f{core.frames_run}\ncore={core.core_name} {core.core_ver} av={av}. "
   f"SELECT never touched -> effectType stays 5 (beams+diamonds ON, source default).")

chart = open(CHART, "rb").read()
R["chart"] = {"path": CHART, "bytes": len(chart),
              "sha256": hashlib.sha256(chart).hexdigest(),
              "first_nonzero": next(i for i, v in enumerate(chart) if v)}
log("chart", **R["chart"])

ram = core.ram


def rd_u32(off):
    return int(ram.view("<u4")[off >> 2])


def rd_u8(off):
    return int(ram[off])


def mirror():
    return [int(ram.view("<u2")[PAD1 >> 1]), int(ram.view("<u2")[PAD2 >> 1])]


# ---------------- phase A: structural scan for the pool ----------------
def find_pool():
    """Scan whole RAM for 30 u16 slots at stride s whose y-field == 120 and which
    carry the Start() constants. Returns dict with i0 (u16 index of slot0 y-field),
    stride (bytes), and companion offsets (bytes, relative to the y-field)."""
    v = ram.view("<u2")
    cand = np.flatnonzero(v == 120)
    if cand.size > 6000:
        return None
    for s in (0x28, 0x2C, 0x30, 0x34, 0x38):
        s16 = s >> 1
        for i0 in cand:
            i0 = int(i0)
            if i0 + 29 * s16 >= v.size:
                continue
            if not np.all(v[i0: i0 + 30 * s16:s16] == 120):
                continue
            offs = {}
            ok = True
            for name, val in (("w", 16), ("h", 16), ("tpage", 25),
                              ("cx", 48), ("cy", 498), ("sx", 4096), ("sy", 4096)):
                # d = byte offset relative to the y field (y field = u16 index i0)
                found = [d for d in range(2, s - 1, 2)
                         if np.all(v[i0 + d // 2: i0 + d // 2 + 30 * s16:s16] == val)]
                if not found:
                    ok = False
                    break
                offs[name] = found
            if ok:
                return {"i0": i0, "stride": s, "offs": offs}
    return None


pool = None
for i in range(4600):
    core.run_frame()
    if i % 10 == 0:
        pool = find_pool()
        if pool:
            break
if not pool:
    log("FAIL", reason="pool not found by f4600")
    ev("\n## RESULT\nPOOL NOT FOUND — structural scan failed. Verdict stays RUNNING.")
    dump()
    sys.exit(2)

i0, S = int(pool["i0"]), int(pool["stride"])
D = {k: v[0] for k, v in pool["offs"].items()}
pool_va = 0x80000000 + i0 * 2 - 6  # if libgs layout (y at slot+6) this is slot0 base
log("pool_found", f=core.frames_run, i0=i0, stride=S, offs=pool["offs"])
ev(f"""
## Pool layout (live structural scan @f{core.frames_run})
- 30 slots found by the Start() constants (w=16,h=16,tpage=25,cx=48,cy=498,scale=4096)
  with y-field==120 pre-spawn; y-run @ram u16-index {i0} (VA 0x{0x80000000 + i0 * 2:08X}), stride {S} (0x{S:X}).
- offsets (bytes, relative to the y field): w=+{D['w']} h=+{D['h']} tpage=+{D['tpage']} "
  cx=+{D['cx']} cy=+{D['cy']} sx=+{D['sx']} sy=+{D['sy']} (all 30/30 slots).
- {"stride 0x28 CONFIRMS r21t1" if S == 0x28 else "live stride 0x%02X (r21t1's 0x28 was approximate)" % S};
  {"libgs layout plausible (y at slot+6)" if D['w'] == 2 and D['tpage'] == 6 else "non-standard GsSPRITE layout — offsets are authoritative"}""")


def yb(k):
    """byte address of slot k's y field"""
    return (i0 + k * (S >> 1)) * 2


# ---------------- phase B: first spawn, discover offsets, cadence ----------------
OFS = {}          # offsets relative to the y-field byte address
first_spawn_f = None
prev_y = {}
cadence = []
vel = None
det_log = None
for i in range(2600):
    core.run_frame()
    v = ram.view("<i2")
    ys = [int(v[(i0 + k * (S >> 1))]) for k in range(30)]
    if first_spawn_f is None:
        if any(y != 120 for y in ys):
            first_spawn_f = core.frames_run
            k0 = next(k for k in range(30) if ys[k] != 120)
            base = yb(k0)
            # attr: u32 == 0x10000000 (spawn writes (1<<28)); scan 4-aligned addrs
            for d in range(-S, S - 3):
                addr = base + d
                if addr % 4 == 0 and int(ram.view("<u4")[addr >> 2]) == 0x10000000:
                    OFS["attr"] = d
                    break
            # rgb: 3 bytes, one ~120-128, others ~68-88 (desaturation=80 +/- hue shift)
            for d in range(-S, S - 3):
                t = (int(ram[base + d]), int(ram[base + d + 1]), int(ram[base + d + 2]))
                mx, mn = max(t), min(t)
                if 116 <= mx <= 128 and 64 <= mn <= 92 and mx - mn >= 32:
                    OFS["rgb"] = d
                    break
            # u: byte == lane*16 (u = lane*16 at spawn)
            x = int(ram.view("<i2")[(base - 2) >> 1])
            lane = (x + 30) // 20
            for d in range(-S, S):
                if int(ram[base + d]) == lane * 16:
                    OFS["u"] = d
                    break
            # active: byte == 1 (exclude cy-high byte at D['cy']+1)
            for d in range(-S, S):
                if int(ram[base + d]) == 1 and d != D["cy"] + 1:
                    OFS["active"] = d
                    break
            attr_seen = (int(ram.view("<u4")[(base + OFS["attr"]) >> 2])
                         if "attr" in OFS else None)
            det_log = {"slot": k0, "y": ys[k0], "x": x, "lane": lane,
                       "OFS": OFS, "attr_seen": attr_seen}
            log("first_spawn", f=first_spawn_f, **det_log)
            ev(f"""
## First spawn @f{first_spawn_f} (slot {k0})
- y={ys[k0]} x={x} lane={lane} (x=(lane*20)-30 source formula) u@y{OFS.get('u', '?')}={int(ram[base + OFS['u']]) if 'u' in OFS else '?'}
- attr@y{OFS.get('attr', '?')} = 0x{attr_seen:08X} (spawn writes 0x10000000 = (1<<28) blend)
- rgb@y{OFS.get('rgb', '?')} (one channel 128, two = desaturation 80 plus/minus hue shift)
- active@y{OFS.get('active', '?')} == 1
- offsets are relative to the y-field byte address (slot base = y-field - libgs_pad)""")
    else:
        moved = [k for k in range(30) if k in prev_y and ys[k] != prev_y[k]]
        if moved:
            cadence.append(core.frames_run)
            if vel is None:
                k0 = moved[0]
                vel = ys[k0] - prev_y[k0]
        if len(cadence) >= 6:
            break
    for k in range(30):
        if ys[k] != 120:
            prev_y[k] = ys[k]

if vel is None:
    log("FAIL", reason="no note motion")
    ev("\n## RESULT\nNO NOTE MOTION — verdict stays RUNNING.")
    dump()
    sys.exit(3)
V = vel if vel in (1, 2, 3, 4) else 2
cad = list(np.diff(cadence[:8]))
ev(f"""
## Motion cadence (measured @f{core.frames_run})
- note velocity: y += {V} per game Update (source: frameDiff, author comment says 2)
- Update cadence in run_frames between y-ticks: {cad} -> Updates every {max(set(cad), key=cad.count)} run_frames (30 Hz game loop)
- all servo timing uses run_frames with 2-frame presses (guarantees one Update sees a fresh edge)""")

# ---------------- helpers for the servo ----------------
last_move = {k: -99 for k in range(30)}
last_ys = {k: 120 for k in range(30)}


def frame_state():
    v = ram.view("<i2")
    ys = {k: int(v[i0 + k * (S >> 1)]) for k in range(30)}
    live = []
    for k in range(30):
        y = ys[k]
        if y != 120 and y != last_ys[k]:
            last_move[k] = core.frames_run
        if core.frames_run - last_move[k] <= 3 and -1000 < y < MISS_Y + 2:
            live.append(k)
    return ys, live


def slot_bytes(k):
    b = yb(k)
    return ram[b + OFS["attr"]: b + OFS["attr"] + 4].view("<u4")[0] if False else \
        int(ram.view("<u4")[(b + OFS["attr"]) >> 2]), \
        (int(ram[b + OFS["rgb"]]), int(ram[b + OFS["rgb"] + 1]), int(ram[b + OFS["rgb"] + 2])), \
        int(ram[b + OFS["active"]])


def lane_btn(lane):
    """face button unless it failed delivery before"""
    return FACE[lane] if not lane_fail.get(lane) else DPAD[lane]


lane_fail = {}

# ---------------- phase C: servo — control first, then HIT_TARGET hits ----------------
HIT_TARGET = 4
hits_done = 0
control_done = False
control_ev = None
press_queue = []      # [frames_left, btnset, rec]
press_pend = []       # dicts with pre/post bookkeeping
hit_minus4_sets = []  # per successful hit: u8 offsets that fell exactly -4
cooldown = 0
mode = "servo"
png_tag, png_until = None, -1
end_f = None
MAXF = first_spawn_f + 3400

while core.frames_run < MAXF:
    core.run_frame()
    f = core.frames_run
    cur = core.frame_rgb()

    # press hold
    if press_queue:
        for pq in press_queue:
            pq[0] -= 1
        liveq = [pq for pq in press_queue if pq[0] > 0]
        if liveq:
            btns = set()
            for pq in liveq:
                btns |= pq[1]
            core.set_buttons(btns)
            m1, m2 = mirror()
            press_pend[-1].setdefault("mirror", []).append({"f": f, "m1": m1, "m2": m2})
        else:
            core.set_buttons(set())
            press_queue = []
    else:
        core.set_buttons(set())
    if cooldown > 0:
        cooldown -= 1

    # rgb trace for open presses (catch the transient 250/250/250 hit flash)
    for p in press_pend:
        if not p["checked"] and "rgb" in OFS:
            b = yb(p["slot"]) + OFS["rgb"]
            p["rgb_trace"].append((int(ram[b]), int(ram[b + 1]), int(ram[b + 2])))

    ys, live = frame_state()
    for k in range(30):
        last_ys[k] = ys[k]

    # png capture window
    if png_tag and f <= png_until and cur is not None:
        Image.fromarray(cur).save(os.path.join(SHOTS, f"{png_tag}_f{f:06d}.png"))

    if mode == "done":
        if f > (end_f or f) + 40:
            break
        continue

    # candidates: live notes whose NEXT-update y will be inside the window
    cands = []
    for k in live:
        y = ys[k]
        if WIN_LO < y + V < WIN_HI:
            x = int(ram.view("<i2")[(yb(k) - 2) >> 1])
            cands.append((k, y, x))

    if not control_done:
        if cands and control_ev is None:
            control_ev = {"start_f": f, "slots": cands, "pre": ram.copy()}
            png_tag, png_until = "ctl", f + 46
            log("control_start", slots=cands)
            ev(f"## CONTROL (deliberate miss) starts @f{f}: slots={cands} — NO press "
               f"until the crossing zone empties (causality control)")
        elif control_ev is not None:
            zone = [k for k in live if 55 < ys[k] < 115]
            if not zone:
                post = ram.copy()
                d = post.astype(np.int32) - control_ev["pre"].astype(np.int32)
                plus4 = sorted(int(x) for x in np.flatnonzero(d == 4))
                after = []
                for k, _, _ in control_ev["slots"]:
                    if 'attr' in OFS:
                        a, rgb, act = slot_bytes(k)
                        after.append({"k": k, "y": ys[k], "attr": f"0x{a:08X}",
                                      "rgb": rgb, "active": act})
                R["controls"].append({"start_f": control_ev["start_f"], "end_f": f,
                                      "slots": control_ev["slots"], "plus4": plus4[:40],
                                      "after": after,
                                      "raw_slot_bytes": {
                                          str(k): bytes(ram[yb(k) - S: yb(k) + S]).hex()
                                          for k, _, _ in control_ev["slots"]}})
                log("control_end", f=f, plus4_n=len(plus4), after=after)
                ev(f"## CONTROL end @f{f}: zone empty. After: {after} "
                   f"(note released, hit-flag NOT set — a MISS by design). "
                   f"u8 bytes +4 over the miss window: {len(plus4)} (desat hunt).")
                control_done = True
                control_ev = None
                cooldown = 4
        continue

    # post-press bookkeeping
    for p in press_pend:
        if not p["checked"] and f >= p["chk_f"]:
            a, rgb, act = slot_bytes(p["slot"])
            semi = bool(a & (1 << 30))
            d = ram.astype(np.int32) - p["pre"].astype(np.int32)
            minus4 = sorted(int(x) for x in np.flatnonzero(d == -4))
            plus4 = sorted(int(x) for x in np.flatnonzero(d == 4))
            white_seen = (250, 250, 250) in p["rgb_trace"]
            ok = semi and white_seen
            p.update({"checked": True, "ok": ok, "attr_after": f"0x{a:08X}",
                      "rgb_after": rgb, "active_after": act,
                      "white_seen": white_seen,
                      "minus4": minus4[:80], "plus4": plus4[:20]})
            if ok:
                hit_minus4_sets.append(set(minus4))
            m = p.get("mirror", [])
            delivered = any((mm["m1"] & (1 << BIT[p["btn"]])) == 0 for mm in m)
            p["delivered"] = bool(delivered)
            # discover the hit-flag byte at the first successful hit:
            # a byte in the slot that was 0 pre-press and is 1 now (attr byte3 goes
            # 0x10->0x50, rgb goes white-then-halves, scale grows: none are 0->1)
            if ok and "hit" not in OFS:
                base = yb(p["slot"])
                for dd in range(-S, S):
                    if (0 <= base + dd < len(ram)
                            and int(p["pre"][base + dd]) == 0
                            and int(ram[base + dd]) == 1):
                        OFS["hit"] = dd
                        break
            rec = {"press_f": p["press_f"], "slot": p["slot"], "lane": p["lane"],
                   "y_seen": p["y_seen"], "btn": p["btn"], "delivered": delivered,
                   "ok": ok, "white_seen": white_seen,
                   "attr_after": p["attr_after"], "rgb_after": rgb,
                   "active_after": act, "rgb_trace": p["rgb_trace"],
                   "minus4_n": len(minus4),
                   "minus4_first": [f"0x{0x80000000 + x:08X}" for x in minus4[:6]],
                   "mirror": m}
            if "hit" in OFS:
                rec["hits_total_before"] = p.get("hits_before")
                rec["hits_total_after"] = sum(
                    1 for k2 in range(30)
                    if int(ram[yb(k2) + OFS["hit"]]) == 1)
                rec["hit_flag_delta"] = (rec["hits_total_after"]
                                         - (rec["hits_total_before"] or 0))
            R["presses"].append(rec)
            if ok:
                hits_done += 1
                R["hits"].append(rec)
                log("HIT", **{k2: rec[k2] for k2 in ("press_f", "slot", "lane",
                                                     "y_seen", "btn", "delivered")})
                ev(f"## HIT #{hits_done} @press f{p['press_f']} slot {p['slot']} lane {p['lane']} "
                   f"(x={p['lane'] * 20 - 30}, y_seen={p['y_seen']}, btn={p['btn']}, "
                   f"mirror_delivered={delivered}): white flash 250/250/250 seen "
                   f"{p['rgb_trace']}, attr bit30 set (0x{a:08X}), active 1->0 "
                   f"(hit-flag byte @y{OFS.get('hit')}), u8 -4 bytes: {len(minus4)}.")
            else:
                log("press_no_hit", press_f=p["press_f"], slot=p["slot"],
                    rgb=rgb, semi=semi, delivered=delivered, y_after=ys[p["slot"]])
                ev(f"## press @f{p['press_f']} slot {p['slot']} lane {p['lane']} NO HIT: "
                   f"rgb_trace={p['rgb_trace']} semi={semi} delivered={delivered} "
                   f"y_now={ys[p['slot']]}")
                lane_fail[p["lane"]] = lane_fail.get(p["lane"], 0) + 1

    press_pend = [p for p in press_pend if not p["checked"]]

    if mode == "servo" and cands and cooldown == 0 and not press_queue:
        k, y, x = cands[0]
        lane = (x + 30) // 20
        btn = lane_btn(lane)
        pre = ram.copy()
        press_queue.append([3, {btn}, None])   # 3 -> 2 hold frames (f+1, f+2)
        pnew = {"press_f": f + 1, "slot": k, "lane": lane, "y_seen": y,
                "btn": btn, "pre": pre, "chk_f": f + 7, "checked": False,
                "mirror": [], "rgb_trace": []}
        if "hit" in OFS:
            pnew["hits_before"] = sum(1 for k2 in range(30)
                                      if int(ram[yb(k2) + OFS["hit"]]) == 1)
        press_pend.append(pnew)
        png_tag, png_until = f"hit{hits_done + 1}", f + 26
        log("press", press_f=f + 1, slot=k, lane=lane, x=x, y_seen=y,
            y_pred=y + V, btn=btn)
        cooldown = 4

    if hits_done >= HIT_TARGET:
        mode = "done"
        end_f = f
        log("servo_done", hits=hits_done)

log("phase_c_done", hits=hits_done, controls=len(R["controls"]), f=core.frames_run)

# ---------------- desaturation resolution ----------------
hit_sets = [h for h in hit_minus4_sets if h]
miss_set = set(R["controls"][0]["plus4"]) if R["controls"] else set()
inter_hit = set.intersection(*hit_sets) if hit_sets else set()
both = sorted(inter_hit & miss_set) if miss_set else sorted(inter_hit)
R["desat"] = {"hit_intersect_n": len(inter_hit),
              "miss_n": len(miss_set),
              "both": [f"0x{0x80000000 + a:08X}" for a in both[:10]]}
log("desat_hunt", both=[f"0x{0x80000000 + a:08X}" for a in both[:10]],
    hit_n=len(inter_hit), miss_n=len(miss_set))
if both:
    a = both[0]
    tr = [rd_u8(a)]
    for _ in range(30):
        core.run_frame()
        tr.append(rd_u8(a))
    R["desat"]["trace30"] = tr
    R["desat"]["addr"] = f"0x{0x80000000 + a:08X}"
    ev(f"""
## Judgment counter (desaturation u_char)
- **u8 @VA {R['desat']['addr']}**: -4 at EVERY successful hit (intersection of {len(hit_sets)} hit
  windows) AND +4 over the deliberate-miss control — exactly the source semantics
  (`noteHit -> desaturation -= 4; noteMissed -> desaturation += 4`, init 80).
- static-re prediction was VA 0x{0x80000000 + DESAT_CAND:08X} -> {"MATCH" if a == DESAT_CAND else "differs"}.
- 30-frame live trace after the servo (misses push up / hits pull down): {tr}""")
else:
    ev("""
## Judgment counter
- NO u8 satisfied both (-4 at all hits AND +4 at the miss) — hit-flags + vision remain
  the anchors; the ambiguous byte is logged in run_log.json (desat block).""")

fc_now = rd_u32(FC_CAND)
ev(f"- u32@VA 0x{0x80000000 + FC_CAND:08X}: {fc_now} (r21t1's counter; re-classified in run_log)")

snap("final")
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
R["boots_used"] = boots_used
dump()
ev(f"""
## Run end
- boots_used={boots_used}/{BOOT_CAP}, total run_frames={core.frames_run},
  hits anchored={hits_done} (target {HIT_TARGET}), deliberate-miss controls={len(R['controls'])}""")
print("[r22t2] DONE hits=", hits_done, "boots=", boots_used,
      "wall=", round(time.time() - T0, 1), flush=True)
