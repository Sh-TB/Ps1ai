#!/usr/bin/env python3
"""verify_gs_live3.py — FINAL GameShark-grade perception builder.

Chain (all zero tokens):
  boot -> enter -> INPUT-RESPONSIVE gate -> live A-diff (grenade) ->
  bombs anchor -> cluster delta (published layout translated) ->
  100s scripted survival play sampling every address ->
  event-semantic verdicts -> profile merge.

Also maps the true pad word bits empirically (static RE says the pad
array base is 0x800D4948; P1 button word = 0x0D4948).
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
from mission import ensure_mission, recover, idle_churn, responsive  # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
OUT = ("/home/z/my-project/download/ps1play_v3_semantic/"
       "gs_live_verification3.json")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

FRAMES = int(os.environ.get("GSV_FRAMES", "6600"))
SAMPLE_EVERY = 15

PUB = {"bombs": 0x0398B4, "ammo": 0x02DCD8, "hp": 0x032764,
       "lives": 0x0475A8, "timer": 0x0295F8, "weapon": 0x02D92C}
PAD_P1 = 0x0D4948            # empirical: bit0x20=RIGHT tracked here
SCORE = 0x0EE318             # static RE: 9 code xrefs
POW = 0x087A78               # static RE: 4 code xrefs

BIT = {"Y": 0x8000, "B": 0x4000, "A": 0x2000, "X": 0x1000,
       "START": 0x0008, "UP": 0x0010, "DOWN": 0x0040,
       "LEFT": 0x0080, "RIGHT": 0x0020}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


p = PS1Play(GAME)
info = p.boot()
log("boot:", info)
r = p.enter_gameplay3()
log("enter:", r.get("in_game"))
if not r.get("in_game"):
    sys.exit("!! boot failed")
m = ensure_mission(p, tries=6, log=log)
log("mission gate:", {k: v for k, v in m.items()
                      if k not in ("evidence", "hp_cand_addrs")})
if not m.get("in_mission"):
    sys.exit("!! gate failed")

# ---------------- pad bit probes (empirical, per button) ----------------
p.save_state("padbase")
bitmap = {}
for btn in ("RIGHT", "LEFT", "Y", "A", "B", "UP", "DOWN"):
    p.load_state("padbase")
    p.core.run(20, set())
    w_idle = p.mem.u16(PAD_P1)
    p.core.run(30, {btn})
    w_held = p.mem.u16(PAD_P1)                 # read while still held
    p.core.run(10, set())
    p._advance()
    bit = w_held & ~w_idle & 0xFFFF
    bitmap[btn] = bit
    log(f"pad {btn:6s}: idle={w_idle:#06x} held={w_held:#06x} -> bit {bit:#06x}")
p.load_state("padbase")

# ---------------- anchor: live A-diff ----------------
def trial(base, action):
    p.load_state(base)
    p.core.run(8, set())
    s0 = p.mem.snapshot()
    p.core.run(15, action)
    p.core.run(90, set())
    p._advance()
    return s0, p.mem.snapshot()


BOMBS = None
for round_k in range(2):
    p.save_state("dbase")
    i0, i1 = trial("dbase", set())
    a0, a1 = trial("dbase", {"A"})
    ai0 = i0[:0x1FC000].view("<u2").astype(np.int32)
    ai1 = i1[:0x1FC000].view("<u2").astype(np.int32)
    aa0 = a0[:0x1FC000].view("<u2").astype(np.int32)
    aa1 = a1[:0x1FC000].view("<u2").astype(np.int32)
    d_idle, d_a = ai1 - ai0, aa1 - aa0
    c16 = np.flatnonzero((d_a != d_idle) & (d_a == -1) &
                         (aa0 >= 3) & (aa0 <= 30) & (ai0 == aa0))
    log(f"A-diff round {round_k}: exact-1 candidates: "
        f"{[hex(int(w) * 2) for w in c16[:12]]}")
    for w in c16.tolist():
        addr = int(w) * 2
        # confirm: second grenade from the same base state
        p.load_state("dbase")
        p.core.run(10, set())
        v0 = p.mem.u16(addr)
        p.core.run(15, {"A"})
        p.core.run(90, set())
        p._advance()
        v1 = p.mem.u16(addr)
        if v1 == v0 - 1:
            BOMBS = addr
            break
    if BOMBS:
        break
    recover(p, log=log)
if BOMBS is None:
    sys.exit("!! bombs anchor not found")
delta = BOMBS - PUB["bombs"]
log(f"ANCHOR bombs @ {BOMBS:#x} -> cluster delta {delta:+#x}")
translated = {k: v + delta for k, v in PUB.items()}
log("translated:", {k: hex(v) for k, v in translated.items()})

# ---------------- scripted survival play + sampling ----------------
samples = []
recoveries = []
t0 = time.time()
i = 0
while i < FRAMES:
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
        v = {k: p.mem.u16(a) for k, a in translated.items()}
        v["pad"] = p.mem.u16(PAD_P1)
        v["score"] = p.mem.u32(SCORE)
        v["pow"] = p.mem.u16(POW)
        samples.append({"i": i, "btns": sum(BIT[b] for b in btns), "v": v})
    if i % 500 == 499:
        ch = idle_churn(p, 40)
        if ch < 800:
            recover(p, log=log)
            recoveries.append(i)
            ok, _ = responsive(p)
            if not ok:
                log("[warn] still unresponsive after recovery")
    i += 1
wall = time.time() - t0
log(f"played {FRAMES}f in {wall:.1f}s ({FRAMES / wall:.0f} fps), "
    f"samples={len(samples)}, recoveries={len(recoveries)}")

# ---------------- analysis ----------------
def series(k):
    return [s["v"][k] for s in samples]


def deltas(xs):
    return [b - a for a, b in zip(xs, xs[1:])]


verdict = {}
bv = series("bombs")
a_ks = [k for k, s in enumerate(samples) if s["btns"] & BIT["A"]]
adrops = 0
for k in a_ks:
    for j in range(k, min(k + 8, len(bv) - 1)):
        if bv[j + 1] == bv[j] - 1:
            adrops += 1
            break
verdict["bombs"] = {"addr": hex(BOMBS), "range": [min(bv), max(bv)],
                    "a_drops": adrops}
hv = series("hp")
verdict["hp"] = {"addr": hex(translated["hp"]), "range": [min(hv), max(hv)],
                 "frac_le_200": round(sum(1 for x in hv if 0 < x <= 200)
                                      / len(hv), 3),
                 "n_dec": sum(1 for d in deltas(hv) if d < 0),
                 "tail": hv[-10:]}
tv = series("timer")
verdict["timer"] = {"addr": hex(translated["timer"]),
                    "range": [min(tv), max(tv)], "net": tv[0] - tv[-1],
                    "expected": round(FRAMES / 60.0)}
lv = series("lives")
verdict["lives"] = {"addr": hex(translated["lives"]),
                    "range": [min(lv), max(lv)], "tail": lv[-10:]}
av = series("ammo")
verdict["ammo"] = {"addr": hex(translated["ammo"]),
                   "range": [min(av), max(av)],
                   "n_dec": sum(1 for d in deltas(av) if d < 0),
                   "tail": av[-10:]}
wv = series("weapon")
verdict["weapon"] = {"addr": hex(translated["weapon"]),
                     "values": sorted(set(wv))[:12]}
sv = series("score")
verdict["score"] = {"range": [min(sv), max(sv)],
                    "n_inc": sum(1 for d in deltas(sv) if d > 0),
                    "tail": sv[-6:]}
pv = series("pow")
verdict["pow"] = {"range": [min(pv), max(pv)], "tail": pv[-6:]}

# pad accuracy over samples
pad_ok = 0
for s in samples:
    if (s["v"]["pad"] & (BIT["RIGHT"] | BIT["Y"] | BIT["A"] | BIT["B"])) \
            == (s["btns"] & (BIT["RIGHT"] | BIT["Y"] | BIT["A"] | BIT["B"])):
        pad_ok += 1
verdict["pad"] = {"addr": hex(PAD_P1),
                  "match_frac": round(pad_ok / len(samples), 3),
                  "bitmap": {k: hex(v) for k, v in bitmap.items()}}

print("\n=== LIVE GAMESHARK VERIFICATION v3 (delta=%+#x) ===" % delta,
      flush=True)
for role, v in verdict.items():
    print(f"  {role:8s} {v.get('addr', '-'):>9s}  "
          f"{json.dumps({k: x for k, x in v.items() if k != 'tail'})}",
          flush=True)

checks = {
    "bombs": verdict["bombs"]["a_drops"] >= 1 and
    verdict["bombs"]["range"][1] <= 40,
    "hp": verdict["hp"]["frac_le_200"] > 0.9,
    "timer": verdict["timer"]["net"] >= verdict["timer"]["expected"] * 0.4
    and verdict["timer"]["range"][1] <= 400,
    "lives": 1 <= verdict["lives"]["range"][1] <= 9,
    "ammo": verdict["ammo"]["range"][1] <= 999,
    "weapon": bool(verdict["weapon"]["values"]) and
    max(verdict["weapon"]["values"]) <= 32,
    "score": verdict["score"]["range"][1] > 0,
    "pow": verdict["pow"]["range"][1] <= 999,
    "pad": verdict["pad"]["match_frac"] > 0.9,
}
print("\nverdicts:", json.dumps(checks), flush=True)

# ---------------- profile merge ----------------
gs = p.profile.setdefault("gsmap", {})
if checks["bombs"]:
    gs["bombs"] = {"addr": BOMBS, "dtype": "u16", "verified": True,
                   "source": "live A-diff anchor (grenade -1), "
                             f"published-cluster delta {delta:+#x}"}
    for role in ("hp", "timer", "lives", "ammo", "weapon"):
        if checks.get(role):
            gs[role] = {"addr": translated[role], "dtype": "u16",
                        "verified": True,
                        "source": "cluster translation "
                                  f"(delta {delta:+#x}) + live verdict"}
if checks["score"]:
    gs["score"] = {"addr": SCORE, "dtype": "u32", "verified": True,
                   "source": "static RE xrefs + live increment"}
if checks["pow"]:
    gs["pow"] = {"addr": POW, "dtype": "u16", "verified": True,
                 "source": "static RE xrefs"}
if checks["pad"]:
    gs["pad_p1"] = {"addr": PAD_P1, "dtype": "u16", "verified": True,
                    "source": "static RE pad array + live bit probes",
                    "bits": {k: v for k, v in bitmap.items()}}
p.profile.setdefault("history", []).append(
    {"op": "verify_gs_live3", "delta": delta, "checks": checks,
     "anchor": hex(BOMBS)})
p.save_profile()
log("profile updated")

res = {"frames": FRAMES, "wall_s": round(wall, 1), "delta": delta,
       "anchor": hex(BOMBS), "bitmap": {k: hex(v) for k, v in bitmap.items()},
       "verdict": verdict, "checks": checks, "recoveries": recoveries}
json.dump(res, open(OUT, "w"), indent=1)
log("saved ->", OUT)
