#!/usr/bin/env python3
"""r35a_attack2.py — R35-A continuation: NO-STOP kill policies at the
1164 wall (boot #5 of 5; cap amendment 4->5 DISCLOSED PRE-RUN).

Evidence grounding (boot #4 traces + heli_ladder patterns):
  - atk1/atk2 died ONE-SHOT at the wall (hp 289/291 -> 0) while the
    policies LOBBED grenades (A) and HOPPED on stall (B): in Metal Slug
    both animations ROOT-LOCK the player for ~20f — the heli ladder
    proved stops at the clamp eat truck rams (patterns 5/6/8 all died
    exactly there; pattern 2, pure RIGHT, survived 1500f).
  - Engagement worked: entity hp->0 kills recorded (slot15 331->0,
    slot12 65016->0), and the §B gap closed: flyers visible per-frame
    (h 112-157 at +0x7E).
  => attempt 3/4: NEVER stop (no A, no B), walk RIGHT + fire, aim UP
     at flyer candidates while walking.

Honest metric fix: true progress = max_px > 1164.5 (the r35a_attack
past_clamp threshold 1163.0 produced a FALSE POSITIVE at exactly
1164.0 == the old wall value; corrected here and reinterpreted).
"""
import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import r35a_attack as base          # noqa: E402  (constants + helpers)
from issue4_controller import boot  # noqa: E402

BUDGET = 2400
TRUE_WALL = 1164.5                  # old wall value is 1164.0


def policy_walkkill(i, px, st, cand, gren, stuck):
    """Never stop: RIGHT+Y always; UP-aim at flyer candidates."""
    btns = {"RIGHT", "Y"}
    if cand is not None and cand["hp"] > 0:
        btns.add("UP")
    return btns


def policy_walkkill2(i, px, st, cand, gren, stuck):
    """Variant: burst fire cadence + UP-aim window on candidates."""
    btns = {"RIGHT"}
    if (i % 45) < 18:
        btns.add("Y")
    if cand is not None and cand["hp"] > 0:
        btns |= {"UP", "Y"}
    return btns


def amend_ledger2(reason, amendment):
    with open(base.LEDGER) as f:
        led = json.load(f)
    if led["count"] >= 5:
        raise SystemExit("BOOT CAP 5 EXCEEDED (amended cap reached)")
    led["amendments"].append(amendment)
    led["count"] = int(led["count"]) + 1
    led["log"].append({"n": led["count"],
                       "ts": time.strftime("%FT%TZ", time.gmtime()),
                       "script": "r35a_attack2.py", "reason": reason})
    json.dump(led, open(base.LEDGER, "w"), indent=1)
    base.log("boot ledger: count =", led["count"])
    return led["count"]


def hp_of(m):
    return int(m.u16(base.A_PAIR0))


def run2(p, m, name, policy):
    p.load_state(base.CKPT_PRISTINE)
    for _ in range(2):
        p.core.run_frame()
    tr = base.SlotTracker()
    jf = open(os.path.join(base.EVID, "trace", f"r35a_{name}.jsonl"), "w")
    px0, hp0 = base.px_of(m), hp_of(m)
    gren0 = int(m.u8(base.GRENADES))
    max_px, stuck, last_px = px0, 0, px0
    death_f, quiet_f, rain_seen, quiet_streak = None, None, 0, 0
    kills, hp_traj, events, cand_hist = [], [], [], []
    t0, i = time.time(), -1
    base.log(f"[{name}] start px={px0:.1f} hp0={hp0} gren={gren0}")
    try:
        for i in range(BUDGET):
            px = base.px_of(m)
            hp = hp_of(m)
            tv = base.table_words(m)
            active, cand, fall_total, fall_near, hits = tr.poll(tv, px)
            for h in hits:
                if h["hp_from"] > 0 and h["hp_to"] == 0:
                    kills.append({"f": i, **h})
            if fall_total:
                rain_seen += 1
                quiet_streak = 0
            elif rain_seen:
                quiet_streak += 1
                if quiet_streak == 300 and quiet_f is None:
                    quiet_f = i
                    events.append({"f": i, "event": "RAIN_QUIET_300f",
                                   "px": round(px, 1)})
            if i % 30 == 0:
                hp_traj.append({"f": i, "px": round(px, 1), "hp": hp})
            if cand is not None:
                cand_hist.append({"f": i, **{k: cand[k]
                                             for k in ("slot", "x", "h",
                                                       "hp")}})
            stuck = stuck + 1 if px == last_px else 0
            last_px = px
            btns = policy(i, px, {}, cand, gren0, stuck)
            p.core.set_buttons(btns)
            p.core.run_frame()
            max_px = max(max_px, px)
            if hp <= 0:
                death_f = i
                jf.write(json.dumps({"f": i, "event": "DEATH",
                                     "px": round(px, 1)}) + "\n")
                for _ in range(60):
                    p.core.run_frame()
                break
            jf.write(json.dumps({"f": i, "px": round(px, 1), "hp": hp,
                                 "fall": fall_total,
                                 "cand": cand and dict(cand),
                                 "btns": sorted(btns)}) + "\n")
            if px > TRUE_WALL and not any(
                    e["event"] == "TRUE_PAST_WALL" for e in events):
                events.append({"f": i, "event": "TRUE_PAST_WALL",
                               "px": round(px, 1)})
                base.log(f"[{name}] *** TRUE PAST WALL *** px={px:.1f}")
                base.png(p, f"r35a_{name}_pastwall_f{i}.png")
    finally:
        jf.close()
    rep = {"attempt": name, "policy": policy.__name__,
           "budget": BUDGET, "frames_run": i + 1,
           "start_px": round(px0, 1), "max_px": round(max_px, 1),
           "true_past_wall": max_px > TRUE_WALL,
           "hp_start": hp0, "died": death_f is not None,
           "death_f": death_f, "kills": len(kills),
           "kill_events": kills[:40],
           "rain_frames": rain_seen, "rain_quiet_frame": quiet_f,
           "cand_frames": len(cand_hist),
           "cand_last": cand_hist[-1] if cand_hist else None,
           "hp_traj": hp_traj[::4], "events": events,
           "wall_s": round(time.time() - t0, 1)}
    base.png(p, f"r35a_{name}_end_f{i}.png")
    with open(os.path.join(base.EVID, f"r35a_report_{name}.json"),
              "w") as f:
        json.dump(rep, f, indent=1)
    base.log(f"[{name}] END max_px={rep['max_px']} "
             f"true_past_wall={rep['true_past_wall']} "
             f"died={rep['died']}@{death_f} kills={len(kills)} "
             f"rain_f={rain_seen} quiet@{quiet_f} "
             f"wall={rep['wall_s']}s")
    return rep


def main():
    n = amend_ledger2(
        "NO-STOP kill policies at the 1164 wall (walkkill/walkkill2)",
        amendment={
            "before_boot": 5,
            "disclosure": "cap 4->5 (single +1 amendment): boot #4 "
                          "closed the §B flyer-encoding gap (flyers "
                          "visible per-frame, h 112-157) and its death "
                          "traces show one-shot wall deaths while lob "
                          "(A) and hop (B) root-locked the player — "
                          "the heli-ladder patterns 5/6/8 died exactly "
                          "there and pattern 2 (pure RIGHT) survived "
                          "1500f. One more session runs two no-stop "
                          "kill policies from the on-disk pristine "
                          "savestate (no re-reach); in-process "
                          "restores only.",
            "ts": time.strftime("%FT%TZ", time.gmtime())})
    p, fwmode = boot()
    m = p.mem
    p.load_state(base.CKPT_PRISTINE)
    for _ in range(2):
        p.core.run_frame()
    px = base.px_of(m)
    assert (int(m.u32(base.A_FLAGS)) & 0xFF) == 0xFF, "flags not active"
    assert 805 <= px <= 875, f"checkpoint px {px} out of window"
    base.log(f"anchor ok px={px:.1f} fw={fwmode} (n={n})")
    reps = [run2(p, m, "atk3_walkkill", policy_walkkill),
            run2(p, m, "atk4_walkkill2", policy_walkkill2)]
    out = {"firmware_mode": fwmode, "attempts": reps,
           "metric_note": "true_past_wall = max_px > 1164.5 "
                          "(r35a_attack's 1163.0 threshold false-"
                          "positived at exactly 1164.0 == old wall)",
           "disclosure": "UNFROZEN; on-disk pristine savestate restore "
                         "per attempt; boots_used count=5 (amended cap)"}
    with open(os.path.join(base.EVID, "attack2_report.json"), "w") as f:
        json.dump(out, f, indent=1)
    base.log("attack2 complete:", json.dumps(
        [{k: r[k] for k in ("attempt", "max_px", "true_past_wall",
                            "died", "kills")} for r in reps]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
