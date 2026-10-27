#!/usr/bin/env python3
"""r20-t4 RUN 1: re-enter live match from r19_f600 checkpoint + live-position hunt.

Method (per mission): freeze comparison — tick N vs N+20 vs N+40 while an
opponent visibly moves; a LIVE slot tracks the sprite. We sample RAM+screen
every 15f across idle (opponents roam) / LEFT / RIGHT segments. Candidates =
u16 words that change continuously with small position-like steps; ranked by
corr(word series, moving-blob cx on the opponent half of the screen).
Positive control: HARRY anchor 0x142EF8/0x142F00 (1322744/1322752 decimal)
must track HARRY during LEFT/RIGHT segments.
"""
import json, os, sys, time
import numpy as np
from PIL import Image

sys.path.insert(0, "/home/z/my-project/ps1ai")
from ps1play.api import PS1Play

OUT = "/home/z/my-project/scratch/r20t4_poypoy/run1_slots"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
CORE = "/home/z/my-project/emu/cores/mednafen_psx_libretro.so"
OV = {b"beetle_psx_override_bios": b"openbios"}
HARRY_X, HARRY_Y = 1322744, 1322752  # known screen-pos anchor pattern
os.makedirs(OUT, exist_ok=True)
R = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "cue": CUE, "ws": WS}

p = PS1Play(CUE, core=CORE, workspace=WS, var_overrides=OV)
info = p.boot()
R["boot"] = {k: info.get(k) for k in ("core", "serial", "plugin", "ram_bytes")}

# ---- 1) re-enter live match from checkpoint ----
p.load_state("r19_f600")
p.core.run(30)
Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/re_entry_f600.png")
g0 = np.asarray(Image.fromarray(p.core.frame_rgb()).convert("L"), np.float32)
p.core.run(60)
g1 = np.asarray(Image.fromarray(p.core.frame_rgb()).convert("L"), np.float32)
R["reentry_alive_motion"] = float(np.abs(g1 - g0).mean())
R["reentry_ok"] = R["reentry_alive_motion"] > 1.0
if not R["reentry_ok"]:
    R["verdict_run1"] = "REENTRY_DEAD"
    json.dump(R, open(f"{OUT}/slots.json", "w"), indent=1)
    print(json.dumps(R, indent=1)); sys.exit(1)

def gray():
    return np.asarray(Image.fromarray(p.core.frame_rgb()).convert("L")
                      .resize((512, 240)), np.float32)

# ---- 2) freeze-comparison sampling: 18 ticks x 15f ----
segs = ([("idle", None)] * 6 + [("LEFT", "LEFT")] * 4 + [("idle", None)] * 4 +
        [("RIGHT", "RIGHT")] * 4)
rams, grays, segs_used = [], [], []
for i, (tag, btn) in enumerate(segs):
    p.core.run(15, btn)
    rams.append(np.frombuffer(p.mem.snapshot(), np.uint8).copy())
    grays.append(gray())
    segs_used.append(tag)
    if i % 2 == 0:
        Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/tick{i:02d}_{tag}.png")
K = len(rams)
R["ticks"] = K
R["segments"] = segs_used

# ---- 3) candidate filter: continuous small-step changers ----
series = np.stack([r.view("<i2").astype(np.int32) for r in rams])   # K x 1M
d = np.abs(np.diff(series, axis=0))
cont = ((d >= 1) & (d <= 512)).all(axis=0)          # moves every tick, small steps
cands = np.nonzero(cont)[0]
R["n_continuous_words"] = int(len(cands))
rng = series[:, cands]
R["cand_range_p99"] = int(np.percentile(rng.max(axis=0) - rng.min(axis=0), 99))
keep = (rng.max(axis=0) - rng.min(axis=0)) < 8192    # screen-coordinate-like
cands, rng = cands[keep], rng[:, keep]

# ---- 4) sprite-motion series on the opponent half (x>=280) ----
blob_cx, energy = [], []
for a, b in zip(grays[:-1], grays[1:]):
    m = np.abs(b[:, 280:] - a[:, 280:]) > 18
    energy.append(float(m.mean()))
    if m.sum() > 25:
        xs = np.nonzero(m)[1] + 280
        blob_cx.append(float(xs.mean()))
    else:
        blob_cx.append(np.nan)
blob_cx, energy = np.array(blob_cx), np.array(energy)
val = np.nan_to_num(blob_cx)
R["blob_cx"] = [round(float(v), 1) for v in blob_cx]
R["energy"] = [round(float(v), 5) for v in energy]

# ---- 5) rank candidates by corr(word, blob cx) ----
if val.std() > 0 and len(cands):
    yc = val - val.mean()
    xs_ = rng[1:].astype(np.float64)
    xc = xs_ - xs_.mean(axis=0)
    num = (xc * yc[:, None]).mean(axis=0)
    den = xs_.std(axis=0) * val.std()
    corr = np.divide(num, den, out=np.zeros_like(num), where=den > 1e-9)
    order = np.argsort(-np.abs(corr))[:60]
    top = []
    for i in order:
        w = int(cands[i])
        top.append({"off": int(w * 2), "hex": hex(0x80000000 + w * 2),
                    "corr": round(float(corr[i]), 3),
                    "first": int(series[0, w]), "last": int(series[-1, w])})
    R["top_live_candidates"] = top

# ---- 6) positive control: HARRY anchor vs LEFT/RIGHT movement ----
for name, off in (("harry_x", HARRY_X), ("harry_y", HARRY_Y)):
    w = off // 2
    s = series[:, w].astype(np.float64)
    R[name] = [int(v) for v in s]
    if s.std() > 0:
        seg_flag = np.array([1.0 if t in ("LEFT", "RIGHT") else 0.0
                             for t in segs_used[1:]])
        c = np.corrcoef(s[1:] - s[1:].mean(), seg_flag - seg_flag.mean())[0, 1]
        R[name + "_corr_moving_segs"] = round(float(c), 3)

# clustering: group top words within 16 bytes
clusters = []
for c in R.get("top_live_candidates", []):
    for cl in clusters:
        if abs(c["off"] - cl["members"][-1]["off"]) <= 16:
            cl["members"].append(c); break
    else:
        clusters.append({"members": [c]})
R["live_slot_clusters"] = [{"hex": m["members"][0]["hex"],
                            "off": m["members"][0]["off"],
                            "best_corr": max((x["corr"] for x in m["members"]),
                                             default=0),
                            "n": len(m["members"])}
                           for m in clusters[:8]]
R["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
json.dump(R, open(f"{OUT}/slots.json", "w"), indent=1)
print(json.dumps({k: R[k] for k in
                  ("boot", "reentry_alive_motion", "n_continuous_words",
                   "harry_x", "harry_x_corr_moving_segs",
                   "live_slot_clusters")}, indent=1))
