#!/usr/bin/env python3
"""r20-t4 RUN 2: refined live-slot hunt + charged throw v2 -> second RETIRE.

Phase A: restore r19_f600, 16 ticks x 12f natural motion; live-slot =
continuous small-step u16 whose series correlates with the DETRENDED
moving-blob cx on the opponent half AND is non-monotone (kills timers).
Positive control: HARRY anchor 0x142EF8/0x142F00 live read.
Phase B: charged-throw loop (B hold 60f = grab/charge, release; mission
recipe r19 run4) up to +2400f; PNG every 120f; retire detector = heart-HUD
band collapse (viscal hud_heart_px row ~85) or RETIRE banner diff spike.
Honest verdict ladder: WON_2_RETIRE / PLAYING.
"""
import json, os, subprocess, sys, time
import numpy as np
from PIL import Image

sys.path.insert(0, "/home/z/my-project/ps1ai")
from ps1play.api import PS1Play

OUT = "/home/z/my-project/scratch/r20t4_poypoy/run2_throw"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
CORE = "/home/z/my-project/emu/cores/mednafen_psx_libretro.so"
OV = {b"beetle_psx_override_bios": b"openbios"}
HARRY = (1322744, 1322752)
os.makedirs(OUT, exist_ok=True)
R = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "run": 2}

p = PS1Play(CUE, core=CORE, workspace=WS, var_overrides=OV)
R["boot"] = {k: p.boot().get(k) for k in ("core", "serial", "ram_bytes")}
p.load_state("r19_f600")
p.core.run(20)
Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/start.png")

def gray():
    return np.asarray(Image.fromarray(p.core.frame_rgb()).convert("L")
                      .resize((512, 240)), np.float32)

# ---------------- Phase A: live-slot hunt ----------------
rams, grays = [], []
for i in range(16):
    p.core.run(12)
    rams.append(np.frombuffer(p.mem.snapshot(), np.uint8).copy())
    grays.append(gray())
K = len(rams)
series = np.stack([r.view("<i2").astype(np.int32) for r in rams])
d = np.abs(np.diff(series, axis=0))
cont = ((d >= 1) & (d <= 512)).all(axis=0)
cands = np.nonzero(cont)[0]
rngm = series[:, cands]
keep = (rngm.max(axis=0) - rngm.min(axis=0)) < 8192
cands, rngm = cands[keep], rngm[:, keep]
R["n_continuous_words"] = int(len(cands))

blob_cx = []
for a, b in zip(grays[:-1], grays[1:]):
    m = np.abs(b[:, 280:] - a[:, 280:]) > 18
    if m.sum() > 25:
        xs = np.nonzero(m)[1] + 280
        blob_cx.append(float(xs.mean()))
    else:
        blob_cx.append(np.nan)
blob_cx = np.array(blob_cx)
val = np.nan_to_num(blob_cx)
t = np.arange(len(val), dtype=np.float64)  # 15 diffs from K=16 ticks
A = np.stack([np.ones_like(t), t - t.mean()]).T
coef, *_ = np.linalg.lstsq(A, val, rcond=None)
resid = val - A @ coef                       # detrended blob motion
R["blob_cx"] = [round(float(v), 1) for v in blob_cx]

sig = {}
if resid.std() > 1e-6 and len(cands):
    xs_ = rngm[1:].astype(np.float64)
    xc = xs_ - xs_.mean(axis=0)  # mean-center
    tc = t - t.mean()           # detrend: remove monotone drift (timers)
    slope = (xc * tc[:, None]).mean(axis=0) / (tc * tc).sum()
    xres = xc - slope[None, :] * tc[:, None]
    corr = ((xres * resid[:, None]).mean(axis=0) /
            (xres.std(axis=0) * resid.std() + 1e-9))
    dd = np.diff(rngm[1:], axis=0)             # 14 rows
    sign_chg = np.zeros(len(cands), dtype=np.int64)
    sc = (np.diff(np.sign(dd), axis=0) != 0).sum(axis=0)
    sign_chg[:len(sc)] = sc
    ok = (np.abs(corr) > 0.45) & (sign_chg >= 3)
    idxs = np.nonzero(ok)[0]
    order = idxs[np.argsort(-np.abs(corr[idxs]))][:48]
    top = []
    for i in order:
        w = int(cands[i])
        top.append({"off": int(w * 2), "hex": hex(0x80000000 + w * 2),
                    "corr": round(float(corr[i]), 3),
                    "sign_changes": int(sign_chg[i]),
                    "series": [int(v) for v in rngm[:16, i]]})
    R["top_live_candidates"] = top
    seen, clusters = set(), []
    for c in top:
        k = c["off"] // 16
        if k in seen:
            continue
        seen.add(k)
        clusters.append(c)
    R["live_slot_clusters"] = clusters[:8]

# HARRY anchor live read
hx = [int(p.mem.u16(HARRY[0])), int(p.mem.u16(HARRY[1]))]
R["harry_anchor_live_after_phaseA"] = hx
R["phaseA_frames"] = p.core.frames_run

# ---------------- Phase B: charged throw loop ----------------
R["hearts"] = []          # [t, b0, b1, b2, b3]
R["retire_events"] = []
frames_png = 0
band_max = [1.0, 1.0, 1.0, 1.0]
throw_n = 0
B_burst = 0
retired = False
for step in range(2400 // 30):
    btn = "B" if B_burst > 0 else None
    if B_burst > 0:
        B_burst -= 30
        if B_burst == 0:
            throw_n += 1          # release = charged throw
    p.core.run(30, btn)
    fc = p.core.frames_run
    g = gray()
    band = []
    for i in range(4):
        seg = g[78:94, 20 + i * 120: 120 + i * 120]
        w = float((seg > 110).mean())
        band.append(w)
        band_max[i] = max(band_max[i], w)
    R["hearts"].append([fc] + [round(b, 3) for b in band])
    for i in range(4):
        if band_max[i] > 0.10 and band[i] < 0.25 * band_max[i] and not retired:
            R["retire_events"].append(
                {"frame": fc, "band": i, "band_w": band[i],
                 "band_max": band_max[i], "throw_n": throw_n})
            retired = True
    if fc % 120 < 30:
        Image.fromarray(p.core.frame_rgb()).save(
            f"{OUT}/f{fc:05d}.png"); frames_png += 1
    if not retired and step % 3 == 0:
        B_burst = 60              # schedule next grab/charge burst
    if retired:
        p.core.run(45)
        Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/retire_f{fc:05d}.png")
        frames_png += 1
        p.save_state("r20t4_retire")
        break

R["throws"] = throw_n
R["retired"] = retired
R["final_frame"] = p.core.frames_run
R["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
json.dump(R, open(f"{OUT}/run2.json", "w"), indent=1)
print(json.dumps({k: R.get(k) for k in
                  ("n_continuous_words", "live_slot_clusters",
                   "harry_anchor_live_after_phaseA", "throws", "retired",
                   "retire_events", "final_frame")}, indent=1)[:3000])
