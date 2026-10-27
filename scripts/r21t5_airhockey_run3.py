#!/usr/bin/env python3
"""r21-t5 run 3 — corrective boot: resume from run-2 checkpoints and finish.

Run 2 mapped the full menu path but burned its last step on a VLM keyword
bug (a "no hockey gameplay" loading screen matched the gameplay detector),
so the paddle/goal phases never saw the real match. This boot (3rd, past
the planned 2 — disclosed) resumes from the persisted workspace states:

  p3s5 = match loading (right after CIRCLE-confirm on PLAYER SELECT)

flow: boot -> load p3s5 -> wait out the load (VLM-gated) -> save "game"
-> phase4 paddle hunt (LEFT/RIGHT -> paddle word) -> phase4b goal attempt.
All helpers/phases are imported from r21t5_airhockey_causality so the
evidence, GIF frames and R log stay in one place.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, "/home/z/my-project/ps1ai/scripts")
import r21t5_airhockey_causality as m                      # noqa: E402
from ps1play.api import PS1Play                            # noqa: E402

R3 = {"task": "r21t5-run3", "started": time.strftime("%Y-%m-%dT%H:%M:%SZ")}


def log(*a):
    print("[r21t5-r3]", *a, file=sys.stderr, flush=True)


def classify(p, tag):
    m.png(p, f"r3_{tag}")
    vtxt = m.vlm([os.path.join(m.OUT, f"r3_{tag}.png")],
                 "PS1 game screen. Reply EXACTLY as: TYPE=<LIVE_MATCH|MENU|"
                 "LOADING_BLACK>; DETAIL=<what is visible incl. any score/"
                 "text, <=15 words>", tag)
    t = vtxt.upper()
    typ = "UNKNOWN"
    if "LIVE_MATCH" in t:
        typ = "LIVE_MATCH"
    elif "LOADING_BLACK" in t or "BLACK" in t:
        typ = "LOADING_BLACK"
    elif "MENU" in t:
        typ = "MENU"
    log(f"  {tag}: {typ} :: {vtxt[:110]}")
    return typ, vtxt


def advance_to_gameplay(p, state, tag):
    """Wait out loading; if a menu shows up, battery-walk it. -> bool."""
    for attempt in range(8):
        p.load_state(state)
        m.rel(p, 30)
        for w in range(6):
            m.rel(p, 300)
            m.gifcap(p, 1)
            typ, vtxt = classify(p, f"{tag}_w{attempt}_{w}")
            R3.setdefault("wait", []).append(
                {"state": state, "w": w, "type": typ, "vlm": vtxt[:160]})
            if typ == "LIVE_MATCH" or m.looks_like_gameplay(vtxt):
                m.rel(p, 60)
                m.png(p, "p4_game_entry")
                p.save_state("game")
                return True
            if typ == "LOADING_BLACK":
                continue
            # a real menu screen: battery-walk one step, then re-classify
            bat = m.screen_battery(p, state, f"r3_{tag}_d{attempt}_probe")
            best = max(bat, key=lambda b: bat[b]["mad_vs_base"])
            if bat[best]["mad_vs_base"] < 5.0:
                continue          # input-dead screen: keep waiting
            R3.setdefault("walk", []).append(
                {"state": state, "battery": bat, "applied": best})
            p.load_state(state)
            m.rel(p, 10)
            p.core.run(3, {best})
            m.rel(p, 180)
            p.save_state(state)   # new screen becomes the working baseline
            break
    return False


def main():
    t0 = time.time()
    p = PS1Play(m.CUE, core=m.CORE, workspace=m.WS, var_overrides=m.OV)
    info = p.boot()
    log("boot", {k: info.get(k) for k in ("serial", "ram_bytes")})
    m.rel(p, 60)
    ok = advance_to_gameplay(p, "p3s5", "load")
    R3["gameplay"] = ok
    if ok:
        verify, pick = m.phase4(p)
        R3["paddle"] = verify
        if verify.get("ok"):
            m.phase4b(p)
            R3["goal"] = {k: v for k, v in m.R["phases"]["p4b"].items()
                          if k != "desc"}
    R3["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    R3["wall_s"] = round(time.time() - t0, 1)
    json.dump(R3, open(os.path.join(m.OUT, "run3_log.json"), "w"),
              indent=1, default=str)
    json.dump(m.R, open(os.path.join(m.OUT, "run_log.json"), "w"),
              indent=1, default=str)
    log("DONE", R3)


if __name__ == "__main__":
    main()
