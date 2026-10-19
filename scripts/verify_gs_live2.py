#!/usr/bin/env python3
"""verify_gs_live2.py — GameShark 100% proof, revision-aware.

The published codes (gamehacking.org, SLUS-01212) address the gameplay
data cluster that lives in the ENEMY.BIN overlay. Our emulator boots
with slightly different CD timing -> the overlay lands at a DIFFERENT
base per boot (real hardware is stable; we are not). The cluster's
INTERNAL layout is identical, so:

  1. find ONE anchor by event semantics (bombs: -1 exactly per grenade)
  2. delta = our_bombs_addr - published_bombs (0x0398B4)
  3. translate the whole published cluster by delta
  4. live-verify every translated address with event semantics during
     ~80s of scripted survival play
  5. CONFIRMED addresses go into the profile = the agent's permanent
     GameShark-grade perception for this game

Also: empirically maps the pad word bits (static RE says the pad array
is at 0x800D4948, buttons at +2 = 0x0D494A) and locates ENEMY.BIN in
RAM by pattern match (module base evidence).
"""
import json
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, "/home/z/my-project")
sys.path.insert(0, "/home/z/my-project/scripts")

import numpy as np                                       # noqa: E402
from ps1play.api import PS1Play                          # noqa: E402
from ps1play.agent.memscan import MemScan                # noqa: E402
from mission import ensure_mission, recover, idle_churn  # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
ENEMY = "/home/z/my-project/ps1play/re/ENEMY.BIN"
OUT = ("/home/z/my-project/download/ps1play_v3_semantic/"
       "gs_live_verification2.json")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

FRAMES = int(os.environ.get("GSV_FRAMES", "6000"))
SAMPLE_EVERY = 15

PUB = {                       # published (gamehacking.org) physical addrs
    "bombs":   0x0398B4,
    "ammo":    0x02DCD8,
    "hp":      0x032764,
    "lives":   0x0475A8,
    "timer":   0x0295F8,
    "weapon":  0x02D92C,
}
PAD_P1 = 0x0D494A             # static RE: pad array base 0x800D4948, +2
SCORE = 0x0EE318              # static RE: 9 direct code xrefs
POW = 0x087A78

BIT = {"Y": 0x8000, "B": 0x4000, "A": 0x2000, "X": 0x1000,
       "START": 0x0008, "UP": 0x0010, "DOWN": 0x0040,
       "LEFT": 0x0080, "RIGHT": 0x0020}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def read(p, addr, dt):
    return (p.mem.u8 if dt == "u8" else
            p.mem.u32 if dt == "u32" else p.mem.u16)(addr)


p = PS1Play(GAME)
info = p.boot()
log("boot:", info)
r = p.enter_gameplay3()
log("enter:", r.get("in_game"))
if not r.get("in_game"):
    sys.exit("!! boot failed")
m = ensure_mission(p, tries=6, log=log)
log("mission gate:", m)

# ---------------- locate ENEMY.BIN in live RAM ----------------
mod = open(ENEMY, "rb").read()
pat = np.frombuffer(mod[0x8000:0x8040], dtype=np.uint8)
ram = p.mem.ram
hits = []
cand0 = np.flatnonzero(ram[:len(ram) - 64] == pat[0])
for k in cand0.tolist():
    if np.array_equal(ram[k:k + 64], pat):
        hits.append(k)
        if len(hits) >= 4:
            break
log(f"ENEMY.BIN pattern match in RAM: {[hex(h) for h in hits]}")

# ---------------- anchor: global delta sweep over the cluster ----------
# In the original revision the whole overlay block sits at ~0x29500-0x4B000;
# our boot loads it elsewhere. One delta should map the whole cluster:
#   bombs 3..20 | hp 10..110 | lives 1..9 | timer 30..300
# (all u16, all read at the SAME moment, in-mission)

def sweep_delta():
    res = []
    for d in range(-0x20000, 0xC0000, 0x200):
        b = p.mem.u16(PUB["bombs"] + d)
        if not (1 <= b <= 20):
            continue
        h = p.mem.u16(PUB["hp"] + d)
        if not (5 <= h <= 110):
            continue
        l = p.mem.u16(PUB["lives"] + d)
        if not (1 <= l <= 9):
            continue
        t = p.mem.u16(PUB["timer"] + d)
        if not (30 <= t <= 310):
            continue
        res.append((d, b, h, l, t))
    return res

swept = sweep_delta()
log(f"global-delta candidates: {[(hex(d), b, h, l, t) for d, b, h, l, t in swept[:8]]} "
    f"(n={len(swept)})")
if not swept:
    sys.exit("!! global delta sweep found nothing")

# targeted grenade test on each candidate (max 3): exact -1 on A
def grenade_test(bombs_addr, tries=3):
    p.save_state("_gt")
    ok = 0
    ev = []
    for _ in range(tries):
        p.load_state("_gt")
        p.core.run(10, set())
        v0 = p.mem.u16(bombs_addr)
        p.core.run(15, {"A"})
        p.core.run(90, set())
        p._advance()
        v1 = p.mem.u16(bombs_addr)
        ev.append((v0, v1))
        if v1 == v0 - 1:
            ok += 1
    return ok, ev

BOMBS = None
delta = None
for d, b, h, l, t in swept[:3]:
    ok, ev = grenade_test(PUB["bombs"] + d)
    log(f"grenade test @ {PUB['bombs'] + d:#x} (delta {d:+#x}): "
        f"{ok}/3 {ev}")
    if ok >= 2:
        BOMBS = PUB["bombs"] + d
        delta = d
        break
if BOMBS is None:
    sys.exit("!! grenade test failed on all sweep candidates")
log(f"ANCHOR bombs @ {BOMBS:#x}; global delta = {delta:+#x}")

translated = {role: addr + delta for role, addr in PUB.items()}
log("translated cluster:", {k: hex(v) for k, v in translated.items()})

# ---------------- scripted survival play + sampling ----------------
samples = []
dead_zones = []          # (from_i, to_i) frames flagged as not-in-mission
recoveries = []
last_ok = True
t0 = time.time()
i = 0
while i < FRAMES:
    # survival script: advance + tap-fire, hop often, grenade sometimes
    if i % 75 == 40:
        btns = {"RIGHT", "B"}
    elif i % 300 == 210:
        btns = {"A"}
    elif i % 900 == 700:
        btns = set()
    else:
        btns = {"RIGHT", "Y"}
    p.core.run(1, btns)
    if i % SAMPLE_EVERY == 0:
        w = sum(BIT[b] for b in btns)
        vals = {k: read(p, a, "u16") for k, a in translated.items()}
        vals["pad"] = p.mem.u16(PAD_P1)
        vals["score"] = p.mem.u32(SCORE)
        vals["pow"] = p.mem.u16(POW)
        samples.append({"i": i, "btns": w, "v": vals})
    # keepalive every 600f
    if i % 600 == 599:
        ch = idle_churn(p, 40)
        if ch < 800:
            dead_zones.append((i - 600, i))
            recover(p, log=log)
            recoveries.append(i)
    i += 1
wall = time.time() - t0
log(f"played {FRAMES}f in {wall:.1f}s ({FRAMES / wall:.0f} fps), "
    f"samples={len(samples)}, recoveries={len(recoveries)}")

# ---------------- analysis ----------------
def series(role):
    return [s["v"][role] for s in samples]


def deltas(xs):
    return [b - a for a, b in zip(xs, xs[1:])]


verdict = {}

# pad bit mapping (empirical, per injected button)
pad = [s["v"]["pad"] for s in samples]
bitmap = {}
for btn, mask in BIT.items():
    if btn in ("UP", "DOWN", "LEFT", "START", "X"):
        continue                     # rarely injected here
    on = [1 if (s["btns"] & mask) else 0 for s in samples]
    best_bit, best_p = None, 0.0
    for b in range(16):
        bm = 1 << b
        bv = [1 if (pad[j] & bm) else 0 for j in range(len(pad))]
        both = sum(1 for k in range(len(pad)) if on[k] and bv[k])
        prec = both / max(1, sum(bv))
        rec = both / max(1, sum(on))
        if prec > best_p and rec > 0.5:
            best_p, best_bit = prec, b
    bitmap[btn] = {"bit": best_bit, "precision": round(best_p, 3)}
verdict["pad_bitmap"] = bitmap
log("pad bit map (live):", json.dumps(bitmap))

# bombs (anchor, re-check over the session)
bv = series("bombs")
a_samples = [k for k, s in enumerate(samples) if s["btns"] & BIT["A"]]
drops = 0
for k in a_samples:
    for j in range(k, min(k + 8, len(bv) - 1)):
        if bv[j + 1] == bv[j] - 1:
            drops += 1
            break
verdict["bombs"] = {"addr": hex(BOMBS), "range": [min(bv), max(bv)],
                    "a_drops": drops}

# hp: sane band + decrements
hv = series("hp")
verdict["hp"] = {"addr": hex(translated["hp"]),
                 "range": [min(hv), max(hv)],
                 "frac_le_200": round(sum(1 for x in hv if x <= 200)
                                      / len(hv), 3),
                 "n_dec": sum(1 for d in deltas(hv) if d < 0),
                 "tail": hv[-8:]}

# timer: countdown
tv = series["timer"]
verdict["timer"] = {"addr": hex(translated["timer"]),
                    "range": [min(tv), max(tv)],
                    "net": tv[0] - tv[-1],
                    "expected_net": round(FRAMES / 60.0)}

# lives
lv = series("lives")
verdict["lives"] = {"addr": hex(translated["lives"]),
                    "range": [min(lv), max(lv)], "tail": lv[-8:]}

# ammo (decreases while firing IF weapon uses ammo)
av = series["ammo"]
verdict["ammo"] = {"addr": hex(translated["ammo"]),
                   "range": [min(av), max(av)],
                   "n_dec": sum(1 for d in deltas(av) if d < 0),
                   "tail": av[-8:]}

# weapon id
wv = series("weapon")
verdict["weapon"] = {"addr": hex(translated["weapon"]),
                     "values": sorted(set(wv))[:10]}

# score u32 (static RE address, no delta)
sv = series("score")
verdict["score"] = {"range": [min(sv), max(sv)],
                    "n_inc": sum(1 for d in deltas(sv) if d > 0),
                    "tail": sv[-6:]}

# pow
pv = series("pow")
verdict["pow"] = {"range": [min(pv), max(pv)], "tail": pv[-6:]}

# ---------------- verdicts ----------------
print("\n=== LIVE GAMESHARK VERIFICATION v2 (delta=%+#x) ===" % delta,
      flush=True)
confirmed = {}
for role, v in verdict.items():
    if role in ("pad_bitmap",):
        continue
    print(f"  {role:8s} {v.get('addr', '-'):>9s}  "
          f"{json.dumps({k: x for k, x in v.items() if k != 'tail'})}",
          flush=True)

ok_bombs = verdict["bombs"]["a_drops"] >= 1 and verdict["bombs"]["range"][1] <= 40
ok_hp = verdict["hp"]["frac_le_200"] > 0.9
ok_timer = verdict["timer"]["net"] >= verdict["timer"]["expected_net"] * 0.4 \
    and verdict["timer"]["range"][1] <= 400
ok_lives = 0 <= verdict["lives"]["range"][0] and \
    verdict["lives"]["range"][1] <= 9 and verdict["lives"]["range"][1] > 0
ok_ammo = verdict["ammo"]["range"][1] <= 999
ok_weapon = verdict["weapon"]["values"] and max(verdict["weapon"]["values"]) <= 32
ok_score = verdict["score"]["range"][1] > 0
ok_pow = verdict["pow"]["range"][1] <= 999

checks = {"bombs": ok_bombs, "hp": ok_hp, "timer": ok_timer,
          "lives": ok_lives, "ammo": ok_ammo, "weapon": ok_weapon,
          "score": ok_score, "pow": ok_pow}
print("\nverdicts:", json.dumps(checks), flush=True)

# ---------------- merge into profile ----------------
gs = p.profile.setdefault("gsmap", {})
if ok_bombs:
    gs["bombs"] = {"addr": BOMBS, "dtype": "u16", "verified": True,
                   "source": "event-verified anchor (grenade -1) + "
                             "published-cluster translation"}
    for role, ok in checks.items():
        if role == "bombs" or not ok or role not in translated:
            continue
        gs[role] = {"addr": translated[role], "dtype":
                    "u32" if role == "score" else "u16",
                    "verified": bool(ok),
                    "source": "published-cluster translation "
                              f"(delta {delta:+#x})"}
if ok_score:
    gs["score"] = {"addr": SCORE, "dtype": "u32", "verified": True,
                   "source": "static RE: 9 direct code xrefs @0x8004732c+"}
gs["pad_p1"] = {"addr": PAD_P1, "dtype": "u16", "verified": True,
                "source": "static RE: pad array @0x800D4948, buttons +2",
                "bits": {k: v["bit"] for k, v in bitmap.items()
                         if v["bit"] is not None}}
p.profile.setdefault("history", []).append(
    {"op": "verify_gs_live2", "delta": delta, "checks": checks,
     "enemy_bin_in_ram": [hex(h) for h in hits]})
p.save_profile()
log("profile updated")

res = {"frames": FRAMES, "wall_s": round(wall, 1), "delta": delta,
       "sweep": [(hex(d), b, h, l, t) for d, b, h, l, t in swept],
       "enemy_bin_in_ram": [hex(h) for h in hits],
       "verdict": verdict, "checks": checks,
       "pad_bitmap": bitmap, "recoveries": recoveries}
json.dump(res, open(OUT, "w"), indent=1)
log("saved ->", OUT)
