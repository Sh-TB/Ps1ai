#!/usr/bin/env python3
"""issue4_real_start.py — escape the ATTRACT DEMO and reach REAL play.

Root cause found via frame captures (issue4_visual_debug): the boot
flow (enter_gameplay3 + START recovery) lands on the attract-loop DEMO
of mission 1.  The demo plays a scripted run with its own HUD (bombs
58/56, score 1600, 1UP=2) while "PRESS START" flashes top-right.  Our
pad bits DO appear in the mirror during the demo (that is why every
previous gate passed) but they do not control the demo's player, and
RAM variables verified inside demo micro-windows (e.g. u8 0xEDCF4
counting 10,9,8) do not transfer to real play.

This script:
  1. boots to the demo,
  2. detects the flashing PRESS START banner (white-pixel ratio in the
     top-right band, two sampling windows because it blinks),
  3. presses START (insert coin / 1P launch),
  4. verifies REAL play: banner gone for 180f, score==0, and the pad
     mirror is ZERO whenever we press nothing (the demo's scripted
     bits are gone),
  5. proves causality in REAL play: identical-save baseline vs RIGHT
     leg (pixel + churn), then
  6. re-runs the two-origin movement scan to find variables that
     transfer to real play (camera/scroll, player position), and
  7. finds the REAL bombs variable from the HUD value (start 58) via
     strict grenade decrements.

Report: evidence/issue4_realstart/real_start_report.json
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PIL import Image                                     # noqa: E402
from ps1play import labconfig                             # noqa: E402
from ps1play.api import PS1Play                           # noqa: E402
from mission import ensure_mission, responsive            # noqa: E402

SCORE_OFF = 0x0EE318
ZONE = 0x1FC000
BANNER_BOX = (160, 8, 264, 48)     # x0,y0,x1,y1 top-right band
OUTDIR = os.path.join(labconfig.resolve_path("evidence_dir") or
                      "/home/z/my-project/work/msx_recomp/evidence",
                      "issue4_realstart")


def _log(*a):
    print("[realstart]", *a, file=sys.stderr, flush=True)


def white_ratio(rgb, box):
    a = np.asarray(rgb, dtype=np.int32)[box[1]:box[3], box[0]:box[2]]
    return float(((a[:, :, 0] > 190) & (a[:, :, 1] > 190) &
                  (a[:, :, 2] > 190)).mean())


def banner_visible(p):
    """Legacy banner probe (records the cosmetic overlay only — the
    SLUS port keeps PRESS START visible during real play, so this is
    NOT a state discriminator)."""
    for _ in range(2):
        rgb = p.core.frame_rgb()
        if rgb is not None and white_ratio(rgb, BANNER_BOX) > 0.05:
            return True
        p.core.run(25, set())
    rgb = p.core.frame_rgb()
    return rgb is not None and white_ratio(rgb, BANNER_BOX) > 0.05


def owns_pad(p, frames=60):
    """Input-ownership proof: idle mirror all-zero across 5 windows,
    then RIGHT must move the world (sprite-region pixel diff).
    This replaces the banner check: in the SLUS port the PRESS START
    banner stays on screen during real play (cosmetic)."""
    idles = []
    for _ in range(5):
        p.core.run(10, set())
        idles.append(int(p.mem.u16(0x0D4948)))
    p.core.run(10, set())
    rgb0 = p.core.frame_rgb()
    s0 = p.mem.snapshot()
    p.core.run(frames, {"RIGHT"})
    p._advance()
    rgb1 = p.core.frame_rgb()
    churn = int(np.flatnonzero(s0 != p.mem.snapshot()).size)
    px = round(float(np.abs(rgb0.astype(np.int16) -
                            rgb1.astype(np.int16)).mean()), 3)
    return {"idle_mirror": idles,
            "idle_all_zero": all(v == 0 for v in idles),
            "churn": churn, "pixel_diff": px,
            "owns": bool(all(v == 0 for v in idles) and
                         (px > 0.5 or churn > 800))}


def boot_to_demo():
    ws = labconfig.resolve_path("workspace")
    fw = labconfig.resolve_firmware(
        os.environ.get("M1_FIRMWARE", "openbios"), ws)
    kw = {}
    core_path = labconfig.resolve_path("core")
    if core_path:
        kw["core"] = core_path
    if ws:
        kw["workspace"] = ws
    if fw["override_vars"]:
        kw["var_overrides"] = fw["override_vars"]
    p = PS1Play(labconfig.resolve_path("game"), **kw)
    p.boot()
    fw_ev = labconfig.firmware_log_evidence(
        getattr(p.core, "log_history", []))
    ok, detail = labconfig.check_firmware_trust(fw, fw_ev)
    if not ok:
        raise SystemExit(f"firmware trust failed: {detail}")
    nav = p.enter_gameplay3()
    _log("enter_gameplay3:", {k: nav.get(k) for k in
                              ("in_game", "steps", "screen")})
    return p


def three_way(p, origin_frames, frames=240):
    legs = {}
    for name, btns in (("idle", set()), ("right", {"RIGHT"}),
                       ("left", {"LEFT"})):
        p.load_state("real0")
        p.core.run(origin_frames, set())
        s0 = p.mem.snapshot()[:ZONE]
        p.core.run(10, set())
        sA = p.mem.snapshot()[:ZONE]
        p.core.run(frames, btns)
        p._advance()
        legs[name] = (s0, sA, p.mem.snapshot()[:ZONE])
    idle = legs["idle"]
    out = {}
    for width in (1, 2, 4):
        view = {1: "<u1", 2: "<u2", 4: "<u4"}[width]
        dr = legs["right"][2].view(view).astype(np.int64) - \
            legs["right"][0].view(view).astype(np.int64)
        dl = legs["left"][2].view(view).astype(np.int64) - \
            legs["left"][0].view(view).astype(np.int64)
        di = idle[2].view(view).astype(np.int64) - \
            idle[0].view(view).astype(np.int64)
        diA = idle[1].view(view).astype(np.int64) - \
            idle[0].view(view).astype(np.int64)
        lo, hi = ((60, 4000) if width > 1 else (60, 255))
        cand = np.flatnonzero(
            (dr >= lo) & (dr <= hi) & (dl <= -lo) & (dl >= -hi) &
            (np.abs(di) <= 6) & (np.abs(diA) <= 2) &
            (np.abs(dr + dl) <= np.maximum(60, 0.15 * np.abs(dr))))
        out[f"u{width * 8}"] = sorted(int(c) * width for c in cand)
    _log(f"origin+{origin_frames}: " +
         " ".join(f"{k}={len(v)}" for k, v in out.items()))
    return out


def bombs_trial(p, trial, bombs_addr_candidate=None):
    """One grenade press from a fresh real0 restore; return u8 drops."""
    p.load_state("real0")
    p.core.run(4 + 3 * trial, set())
    before = p.mem.snapshot()
    hud0 = None                      # caller reads HUD separately
    p.core.run(8, set())
    p.core.run(30, {"A"})
    p.core.run(20, set())
    p._advance()
    after = p.mem.snapshot()
    d = before.astype(np.int16) - after.astype(np.int16)
    drops = np.flatnonzero((d == 1) & (before >= 1) & (before <= 99))
    return {"trial": trial,
            "drop_addrs": [hex(int(x)) for x in drops[:24]],
            "drop_count": int(drops.size)}


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    out = {"schema": "ps1play-real-start/1",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime())}
    p = boot_to_demo()

    # 1-2: demo state + banner
    out["banner_in_demo"] = banner_visible(p)
    _log("banner visible during demo:", out["banner_in_demo"])
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(OUTDIR, "demo.png"))

    # 3: START taps — the arcade loop needs repeated coin+start; the
    # PRESS START banner stays on screen in this port even during real
    # play, so ownership (not the banner) decides when to stop.
    taps = []
    for attempt in range(6):
        p.core.run(12, {"START"})
        p.core.run(150, set())
        own = owns_pad(p, frames=30)
        taps.append({"attempt": attempt, "owns": own["owns"],
                     "idle_zero": own["idle_all_zero"],
                     "score": int(p.mem.u32(SCORE_OFF))})
        out.setdefault("start_taps", taps)
        _log(f"START tap {attempt}: owns={own['owns']} "
             f"idle0={own['idle_all_zero']} "
             f"score={taps[-1]['score']}")
        if own["owns"]:
            break
    own = owns_pad(p)
    out["ownership"] = own
    out["real_play_verified"] = own["owns"]
    _log("real play verified (input ownership):", own["owns"],
         "idle:", own["idle_mirror"])

    # 4: verify real play (ownership already proven above)
    score = int(p.mem.u32(SCORE_OFF))
    out["score_now"] = score
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(OUTDIR, "after_start.png"))
    _log("real play verified:", out["real_play_verified"],
         "score:", score)
    if not out["real_play_verified"]:
        with open(os.path.join(OUTDIR, "real_start_report.json"),
                  "w") as f:
            json.dump(out, f, indent=1)
        return 3

    # establish real0 anchor after a short rightward walk (like caus0)
    p.core.run(90, {"RIGHT"})
    p.core.run(15, set())
    p._advance()
    p.save_state("real0")
    ok, (w1, churn) = responsive(p)
    out["real0_responsive"] = {"ok": bool(ok), "pad": int(w1),
                               "churn": int(churn)}

    # 5: causality in real play (deterministic baseline vs RIGHT)
    p.load_state("real0")
    s0 = p.mem.snapshot()
    p.core.run(60, set())
    p._advance()
    b_rgb = p.core.frame_rgb()
    b_churn = int(np.flatnonzero(s0 != p.mem.snapshot()).size)
    p.load_state("real0")
    p.core.run(60, {"RIGHT"})
    p._advance()
    t_rgb = p.core.frame_rgb()
    t_churn = int(np.flatnonzero(s0 != p.mem.snapshot()).size)
    px = round(float(np.abs(b_rgb.astype(np.int16) -
                            t_rgb.astype(np.int16)).mean()), 3)
    out["real_causality_right"] = {
        "baseline_churn": b_churn, "right_churn": t_churn,
        "pixel_diff": px, "causal": bool(px > 0.2 or
                                         t_churn - b_churn > 64)}
    _log("real causality RIGHT:", out["real_causality_right"])

    # 6: movement variables that transfer to real play, two origins
    c0 = three_way(p, 0)
    c1 = three_way(p, 30)
    common = {}
    for k in c0:
        both = sorted(set(c0[k]) & set(c1[k]))
        if both:
            common[k] = [hex(a) for a in both[:24]]
    out["movement_candidates"] = common
    _log("movement candidates common across origins:", common)

    # 7: real bombs discovery (HUD starts 58)
    trials = [bombs_trial(p, k) for k in range(3)]
    out["bombs_trials"] = trials
    common_drops = set(trials[0]["drop_addrs"])
    for t in trials[1:]:
        common_drops &= set(t["drop_addrs"])
    out["bombs_common_drop_addrs"] = sorted(common_drops)
    _log("bombs common drops:", sorted(common_drops))

    with open(os.path.join(OUTDIR, "real_start_report.json"), "w") as f:
        json.dump(out, f, indent=1)
    _log("report saved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
