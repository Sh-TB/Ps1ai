#!/usr/bin/env python3
"""verify_gsmap.py v2 — continues the interrupted task.

The published GameShark seeds turned out to be for a DIFFERENT revision
(hp/lives read constant 0xFF) -> we now FIND the real counters ourselves
with the classic cheat-finder workflow, READ-ONLY, made deterministic by
savestate replay:

  restore base -> trigger (throw grenade / take a stab / kill / die)
               -> narrow dec/inc
  restore base -> control (no event) -> narrow unchanged
  intersect across 2 reps  =>  exactly the event-caused counters.

Phases: entry -> player-x -> event scans (bombs/score/hp/lives/timer)
        -> player-y -> observation play with live telemetry -> persist.
"""
import json
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, "/home/z/my-project")
import numpy as np

from ps1play.api import PS1Play
from ps1play.agent.memscan import MemScan, DT

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
OUT = "/home/z/my-project/ps1-test/emu/states/verify_report.json"
EVID = "/home/z/my-project/download/ps1play_v2"

report = {"started": time.strftime("%Y-%m-%d %H:%M:%S")}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def read_spec(p, spec):
    a, dt = spec["addr"], spec.get("dtype", "u16")
    return {"u8": p.mem.u8, "u16": p.mem.u16, "u32": p.mem.u32}[dt](a)


def png(p, name):
    try:
        from PIL import Image
        rgb = p.core.frame_rgb()
        if rgb is not None:
            os.makedirs(EVID, exist_ok=True)
            Image.fromarray(rgb).resize((320, 240)).save(
                os.path.join(EVID, name))
    except Exception as e:                                  # noqa: BLE001
        log("png fail:", e)


def addr_set(scan, name):
    sz = DT[name][0]
    return {int(i) * sz for i in np.flatnonzero(scan.masks[name])}


def narrowed(p, base, trigger, control, reps=2, dec=True,
             dtypes=("u16", "u32")):
    """Savestate-deterministic differential scan (the classic cheat
    finder, made exact). Returns {dtype: set(addrs)}."""
    surv = {dt: None for dt in dtypes}
    for _ in range(reps):
        p.load_state(base)
        scan = MemScan(p.mem)
        scan.reset()
        trigger()
        for dt in dtypes:
            (scan.dec if dec else scan.inc)(dt)
        for dt in dtypes:
            s = addr_set(scan, dt)
            surv[dt] = s if surv[dt] is None else (surv[dt] & s)
        p.load_state(base)
        scan = MemScan(p.mem)
        scan.reset()
        control()
        for dt in dtypes:
            scan.unchanged(dt)
        for dt in dtypes:
            surv[dt] &= addr_set(scan, dt)
        p._advance()
    return surv


def live_vals(p, addrs, dt):
    read = {"u8": p.mem.u8, "u16": p.mem.u16, "u32": p.mem.u32}[dt]
    return [{"addr": a, "dtype": dt, "val": read(a)} for a in sorted(addrs)]


# ================================================== phase 1: entry
p = PS1Play(GAME, verbose=False)
info = p.boot()
log("boot:", info)
report["boot"] = info
r = p.enter_gameplay3()
report["enter"] = {k: v for k, v in r.items() if k != "proof"}
log("enter_gameplay3:", report["enter"])
if not r.get("in_game"):
    r = p.enter_gameplay3()
    report["enter_retry"] = {k: v for k, v in r.items() if k != "proof"}
    if not r.get("in_game"):
        json.dump(report, open(OUT, "w"), indent=1)
        sys.exit("!! could not enter gameplay")
png(p, "verify_00_gameplay.png")

p.save_state("scan_base")
log("scan_base saved, t =", p.t)

# ================================================== phase 2: player X
scan = MemScan(p.mem)
scan.reset()
p.core.run(35, {"RIGHT", "Y"})
scan.inc("u16"); scan.inc("u32")
p.core.run(35, {"RIGHT", "Y"})
scan.inc("u16"); scan.inc("u32")
p.core.run(30, set())
scan.unchanged("u16"); scan.unchanged("u32")
p._advance()
right = {"u16": addr_set(scan, "u16"), "u32": addr_set(scan, "u32")}
log("after RIGHT narrow: u16", len(right["u16"]), "u32", len(right["u32"]))

p.load_state("scan_base")
scan = MemScan(p.mem)
scan.reset()
p.core.run(35, {"LEFT", "Y"})
scan.dec("u16"); scan.dec("u32")
p.core.run(35, {"LEFT", "Y"})
scan.dec("u16"); scan.dec("u32")
p.core.run(30, set())
scan.unchanged("u16"); scan.unchanged("u32")
p._advance()
left = {"u16": addr_set(scan, "u16"), "u32": addr_set(scan, "u32")}
log("after LEFT narrow: u16", len(left["u16"]), "u32", len(left["u32"]))

x_cands = []
for dt in ("u16", "u32"):
    both = sorted(right[dt] & left[dt])
    log(f"x candidates {dt}: {len(both)}", [hex(a) for a in both[:12]])
    for a in both[:8]:
        ver = p.disc.verify_series(p.states, "scan_base", a, dt,
                                   "RIGHT", frames=90, step=15)
        if ver:
            x_cands.append(ver)
x_cands.sort(key=lambda v: -v["quality"])
for v in x_cands[:4]:
    log(f"  x verify {hex(v['addr'])} {v['dtype']} q={v['quality']} "
        f"m_act={v['m_act']} m_idle={v['m_idle']} mono={v['mono_frac']}")
report["x_candidates"] = [
    {k: v[k] for k in ("addr", "dtype", "quality", "m_act", "m_idle",
                       "mono_frac")} for v in x_cands[:8]]

# ================================================== phase 3: events
# bombs: circle throws a grenade -> dec; idle control -> unchanged
bombs_sets = narrowed(
    p, "scan_base",
    trigger=lambda: (p.core.run(15, {"A"}), p.core.run(45, set())),
    control=lambda: p.core.run(60, set()), reps=2, dec=True)
bcands = live_vals(p, bombs_sets["u16"], "u16") + \
    live_vals(p, bombs_sets["u32"], "u32")
bombs_c = [c for c in bcands if 0 <= c["val"] <= 99]
log("bombs candidates:", [(hex(c['addr']), c['val']) for c in bombs_c[:8]])
report["bombs_candidates"] = bombs_c[:8]

# score: shooting kills -> inc; idle control (no kills) -> unchanged
score_sets = narrowed(
    p, "scan_base",
    trigger=lambda: p.core.run(120, {"RIGHT", "Y"}),
    control=lambda: p.core.run(120, set()), reps=2, dec=False)
scands = live_vals(p, score_sets["u32"], "u32")
score_c = [c for c in scands if c["val"] <= 300000]
log("score candidates:", [(hex(c['addr']), c['val']) for c in score_c[:8]])
report["score_candidates"] = score_c[:8]

# hp: stand still -> melee stab -> dec; hop control -> unchanged
hp_sets = narrowed(
    p, "scan_base",
    trigger=lambda: p.core.run(240, set()),
    control=lambda: p.core.run(60, {"B"}), reps=2, dec=True,
    dtypes=("u16",))
hcands = live_vals(p, hp_sets["u16"], "u16")
hp_c = [c for c in hcands if 1 <= c["val"] <= 200]
log("hp candidates:", [(hex(c['addr']), c['val']) for c in hp_c[:8]])
report["hp_candidates"] = hp_c[:8]

# timer: 1 Hz countdown over 300f (=5 ticks +-1), two passes
def _timer_pass():
    p.load_state("scan_base")
    scan = MemScan(p.mem)
    scan.reset()
    p.core.run(300, set())
    scan.dec_by("u16", 5, tol=1)
    p._advance()
    return addr_set(scan, "u16")

ts = _timer_pass() & _timer_pass()
tcands = [c for c in live_vals(p, ts, "u16") if 0 < c["val"] <= 300]
log("timer candidates:", [(hex(c['addr']), c['val']) for c in tcands[:8]])
report["timer_candidates"] = tcands[:8]

# lives: stand in fire -> death -> dec; short play control -> unchanged
lives_sets = narrowed(
    p, "scan_base",
    trigger=lambda: p.core.run(900, set()),
    control=lambda: p.core.run(300, {"RIGHT", "Y"}), reps=2, dec=True,
    dtypes=("u16",))
lcands = live_vals(p, lives_sets["u16"], "u16")
lives_c = [c for c in lcands if 0 <= c["val"] <= 9]
log("lives candidates:", [(hex(c['addr']), c['val']) for c in lives_c[:8]])
report["lives_candidates"] = lives_c[:8]
png(p, "verify_01_after_scans.png")

# ================================================== phase 4: player Y
p.load_state("scan_base")
scan = MemScan(p.mem)
scan.reset()
p.core.run(40, set())
scan.unchanged("u16"); scan.unchanged("u32")
p.core.run(16, {"B"})
scan.changed("u16"); scan.changed("u32")
p.core.run(30, {"B"})
scan.changed("u16"); scan.changed("u32")
p.core.run(40, set())
scan.changed("u16"); scan.changed("u32")
p.core.run(40, set())
scan.unchanged("u16"); scan.unchanged("u32")
p._advance()
yc = (addr_set(scan, "u16") | addr_set(scan, "u32"))
log("y candidates after jump pattern:", len(yc))
report["y_narrow_count"] = len(yc)

x_addr = x_cands[0]["addr"] if x_cands else None


def y_verify(addr, dt):
    read = p.mem.u16 if dt == "u16" else p.mem.u32
    p.load_state("scan_base")
    idle = [read(addr)]
    for _ in range(6):
        p.core.run(10, set())
        idle.append(read(addr))
    p._advance()
    p.load_state("scan_base")
    jump = [read(addr)]
    for _ in range(5):
        p.core.run(10, {"B"})
        jump.append(read(addr))
    p.core.run(40, set())
    for _ in range(4):
        p.core.run(10, set())
        jump.append(read(addr))
    p._advance()
    return (max(idle) - min(idle)), (max(jump) - min(jump))


y_results = []
for a in sorted(yc)[:24]:
    if x_addr is not None and abs(a - x_addr) <= 4:
        continue
    dt = "u32" if a % 4 == 0 else "u16"
    i_sw, j_sw = y_verify(a, dt)
    if j_sw >= 3 * max(i_sw, 8) and j_sw >= 48:
        y_results.append({"addr": a, "dtype": dt, "idle_swing": i_sw,
                          "jump_swing": j_sw})
    if len(y_results) >= 5:
        break
y_results.sort(key=lambda r_: -(r_["jump_swing"] - r_["idle_swing"]))
for v in y_results[:5]:
    log(f"  y verify {hex(v['addr'])} {v['dtype']} "
        f"idle={v['idle_swing']} jump={v['jump_swing']}")
report["y_candidates"] = y_results[:5]

# ================================================== phase 5: persist map
gs = p.profile.setdefault("gsmap", {})


def adopt(role, cands, ok_range, note):
    if not cands:
        gs.setdefault(role, {})["verified"] = False
        gs[role]["evidence"] = "no candidate survived narrowing"
        return None
    c = cands[0]
    spec = gs.setdefault(role, {})
    spec.update({"addr": c["addr"], "dtype": c["dtype"],
                 "verified": True, "last_value": c["val"],
                 "evidence": note, "alternatives": cands[1:4]})
    return c


adopt("bombs", bombs_c, (0, 99), "grenade-dec scan, 2 reps savestate")
adopt("score", score_c, None, "kill-inc scan, 2 reps savestate")
adopt("hp", hp_c, (1, 200), "melee-stab-dec scan, 2 reps savestate")
adopt("timer", tcands, None, "1Hz dec_by(5±1) scan, two passes")
adopt("lives", lives_c, (0, 9), "death-dec scan, 2 reps savestate")
gs.setdefault("ammo", {})["verified"] = False
gs["ammo"]["evidence"] = ("pistol is infinite in MSX; needs a weapon "
                          "pickup event to scan — deferred")
gs.setdefault("pad_mirror", {})["verified"] = False
gs["pad_mirror"]["evidence"] = ("0x0D4948 not updated on menus/this "
                                "revision — bit-probe all zero")

if x_cands and x_cands[0]["quality"] >= 5:
    xb = x_cands[0]
    cand = {"addr": xb["addr"], "dtype": xb["dtype"],
            "score": int(xb["quality"]), "dir": "+",
            "verified": "series", "quality": xb["quality"],
            "mono_frac": xb["mono_frac"], "m_act": xb["m_act"],
            "m_idle": xb["m_idle"]}
    p.profile.setdefault("discovered", {})["player_x"] = cand
    report["player_x_final"] = cand
if y_results:
    yb = y_results[0]
    p.profile.setdefault("discovered", {})["player_y"] = {
        "addr": yb["addr"], "dtype": yb["dtype"],
        "score": int(yb["jump_swing"]), "dir": "-",
        "verified": "jump-swing"}
    report["player_y_final"] = yb

# ================================================== phase 6: live play
evc = defaultdict(int)
CH, NC = 60, 40
stall, last_x = 0, None
for i in range(NC):
    obs = p.observer.observe(p.t)
    feat = p.plugin.features(p.mem, obs)
    for e in feat.get("events", ()):
        evc[e] += 1
    watched = feat.get("x")
    if watched is not None and last_x is not None:
        stall = stall + CH if watched == last_x else 0
    last_x = watched
    ctx = {"t": p.t, "chunk": CH, "stall": stall, "feat": feat, "obs": obs}
    done = 0
    for s_ in (p.plugin.policy(ctx) or []):
        k = min(s_["frames"], CH - done)
        if k > 0:
            p.core.run(k, s_["btns"])
            done += k
    if done < CH:
        p.core.run(CH - done)
    p._advance()
    if ctx.get("stall_reset"):
        stall = 0
    if i == 20:
        png(p, "verify_02_play_mid.png")
log("events during live play:", dict(evc))
report["events"] = dict(evc)
report["feat_sample"] = feat
png(p, "verify_03_done.png")

report["finished"] = time.strftime("%H:%M:%S")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(report, open(OUT, "w"), indent=1)
p.save_profile()
log("profile saved:", p.profile_path)
print(json.dumps({k: report.get(k) for k in
                  ("player_x_final", "player_y_final", "events")}, indent=1))
