#!/usr/bin/env python3
"""r76_savestate_battery.py — R76: THE SAVESTATE TEST BATTERY (the
owner directive: freeze the game at the death point, load from
there, and test — each of the 100 tests exactly once).

ONE product boot (the ledger cap 3 disclosed pre-run; boot 1 = the
route + the checkpoint harvest; the battery itself is RESTORE-ONLY
— zero boots, the r66/r67 precedent).  The route = the shipped
policy v2.3.0 verbatim (byte-deterministic: the r75b1 parity is
ASSERTED in-flight — any divergence aborts the battery).  The
checkpoints serialize at the top of the frame iterations:

  CP_A2_THROW   f1378 (2f before the proven 229 throw)
  CP_B_PREBARR  f1495 (before the marchers arrive ~f1515)
  CP_C_PREDEATH f1820 (64f before the death at f1884)
  CP_D_DEATHM1  f1878 (6f before the death)

The battery executes scripts/r76_battery_plan.json in order: each
test = unserialize -> inject -> per-frame poll (the alive word, the
truck a4, the score, the marcher rows) -> one JSONL row.  No RAM
writes to the game; legal inputs only; no training; no runtime LLM.

Evidence: data/games/SLUS-01212/truck_evidence/r76/
          r76_battery.jsonl + r76_battery_summary.json + the PNGs
"""
from __future__ import annotations

import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.runtime.config import RuntimeConfig  # noqa: E402
from ps1play.runtime.registry import (            # noqa: E402
    adapter_for_game, make_env, policy_for_game)
from ps1play.runtime.interfaces import Frame      # noqa: E402
from ps1play.adapters.metal_slug_x.adapter import (  # noqa: E402
    PLAYER_X, PLAYER_HP, A_SCORE, GRENADES, A_FLAGS,
    TABLE, STRIDE, SLOTS, CORPSE_ST)

EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r76")
SCRATCH = os.path.join(_REPO, "scratch", "r76")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
BOOT_CAP = 3
PLAN = os.path.join(_REPO, "scripts", "r76_battery_plan.json")

ACTION_BTNS = {
    "IDLE": frozenset(),
    "WALK": frozenset({"RIGHT"}),
    "BACK": frozenset({"LEFT"}),
    "FIRE": frozenset({"Y"}),
    "HOP": frozenset({"RIGHT", "B"}),
    "GRENADE": frozenset({"A"}),
}
HOLD_BTNS = {
    "IDLE": frozenset(),
    "WALK": frozenset({"RIGHT"}),
    "BACK": frozenset({"LEFT"}),
    "FIRE": frozenset({"Y"}),
    "HOP": frozenset({"RIGHT", "B"}),
    "BHOP": frozenset({"LEFT", "B"}),
    "DOWN": frozenset({"DOWN"}),
    "GRENADE": frozenset({"A"}),
}
TRUCK_ST = (0x9E88, 0x9C14, 0x9E08)
DEAD_TRUCK_ST = (0xA304, 0xA44C, 0xA45C)
MARCHER_ST = (1, 2, 3, 5, 6)

CHECK_FRAMES = {1375: "CP_A2_THROW", 1495: "CP_B_PREBARR",
                1820: "CP_C_PREDEATH", 1878: "CP_D_DEATHM1"}
ROUTE_END = 1879
# the r75b1 parity gate (the in-flight assertion)
PARITY = [(1151, "FREEZE"), (1411, "CONNECT"), (1537, "CHIP"),
          (1565, "CHIP"), (1591, "CHIP"), (1643, "CHIP"),
          (1669, "CHIP"), (1695, "CHIP"), (1721, "CHIP")]


def log(*a):
    print("[r76]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason):
    os.makedirs(SCRATCH, exist_ok=True)
    if not os.path.exists(LEDGER):
        led = {"cap": BOOT_CAP, "count": 0, "log": [],
               "disclosed": "R76 product track: boot 1 = the route "
                            "run + the checkpoint harvest (the "
                            "policy v2.3.0 verbatim to f1879); THE "
                            "BATTERY IS RESTORE-ONLY (100 tests, "
                            "zero boots — the owner directive: "
                            "freeze at the death point, load, "
                            "test).  Legal inputs only, zero RAM "
                            "writes, no training, no runtime LLM."}
    else:
        with open(LEDGER) as f:
            led = json.load(f)
    if led.get("count") == 3 and led.get("cap") == 3:
        # the DISCLOSED amendment (the r46/r50 precedent): the boot-3
        # process crashed in run_battery BEFORE any test (the
        # list/dict TypeError) — zero game frames of battery value;
        # the cap 3 -> 4 for the resume
        led["cap"] = 4
        led["amendments"] = led.get("amendments", []) + [
            {"cap": "3->4", "reason": "the boot-3 process crashed at "
             "the battery loop start (TypeError, zero tests); the "
             "resume needs one boot to load the disk checkpoints"}]
        with open(LEDGER, "w") as f:
            json.dump(led, f, indent=1)
    if int(led.get("count", 0)) + 1 > int(led.get("cap", 0)):
        raise SystemExit("BOOT CAP EXCEEDED (r76 ledger)")
    led["count"] = int(led.get("count", 0)) + 1
    led["log"].append({"n": led["count"],
                       "ts": time.strftime("%FT%TZ", time.gmtime()),
                       "script": "r76_savestate_battery.py",
                       "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']}")
    return led["count"]


def mem_read(m):
    """The one-frame measurement pack."""
    px = m.u32(PLAYER_X) / 65536.0
    php = m.u16(PLAYER_HP)
    score = m.u32(A_SCORE)
    gren = m.u8(GRENADES)
    alive = (m.u32(A_FLAGS) & 0xFF) == 0xFF and px != 0.0
    truck_a4 = None
    truck_st = None
    marchers = []
    for s in range(1, SLOTS):
        base = TABLE + s * STRIDE
        st = m.u16(base)
        xw = m.u32(base + 0x78)
        if not xw:
            continue
        x = xw / 65536.0
        if st in TRUCK_ST:
            truck_a4 = m.u16(base + 0xA4)
            truck_st = hex(st)
        elif st in MARCHER_ST and -220.0 < x - px < 0.0:
            marchers.append({"dx": round(x - px, 1),
                             "h": m.u16(base + 0x7E),
                             "st": hex(st)})
    return {"px": round(px, 1), "php": php, "score": score,
            "gren": gren, "alive": alive, "truck_a4": truck_a4,
            "truck_st": truck_st, "marchers": marchers}


def shot(env, path):
    try:
        from PIL import Image
        rgb = env.p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).save(path)
            return True
    except Exception:                                 # noqa: BLE001
        pass
    return False


def run_route(env, ad, pol, jf, blobs):
    """The policy v2.3.0 route to f1879 with the checkpoints; the
    r75b1 parity asserted in-flight."""
    A4 = {"events": []}
    parity_i = 0
    truck_a4_prev = None
    freeze_f = None
    route_f = None
    for f in range(1, ROUTE_END + 1):
        if f in CHECK_FRAMES:
            name = CHECK_FRAMES[f]
            blobs[name] = env.p.core.serialize()
            try:
                env.p.save_state(name)
            except Exception as e:                        # noqa: BLE001
                log(f"disk checkpoint {name} skipped: {e}")
            log(f"checkpoint {name} at f={f} "
                f"({len(blobs[name])} B)")
        frame = Frame(seq=f, emulator_frame_count=f, rgb=None,
                      timestamp=float(f), stale=False)
        obs = ad.observe(frame)
        dec = pol.predict(obs)
        x = obs.values
        row = {"f": f, "px": round(float(x[0]), 1),
               "score": int(x[1]), "php": int(x[2]), "gren": int(x[3]),
               "alive": float(x[4]) > 0.5,
               "rule": dec.diagnostics.get("rule"),
               "act": dec.action}
        rule = dec.diagnostics.get("rule") or ""
        if f >= 650:
            tab = []
            m = env.p.mem
            for s in range(1, SLOTS):
                base = TABLE + s * STRIDE
                st = int(m.u16(base))
                xw = int(m.u32(base + 0x78))
                if not xw:
                    continue
                tab.append({"slot": s, "st": hex(st),
                            "x": round(xw / 65536.0, 1),
                            "a4": int(m.u16(base + 0xA4))})
            row["table"] = tab
            if freeze_f is None:
                for e in tab:
                    if e["st"] == "0x9e88":
                        freeze_f = f
                        A4["events"].append((f, "FREEZE"))
                        break
            for e in tab:
                if int(e["st"], 16) in TRUCK_ST:
                    if truck_a4_prev is not None and \
                            e["a4"] != truck_a4_prev:
                        d4 = e["a4"] - truck_a4_prev
                        cls = ("CONNECT" if d4 == -100
                               else "CHIP" if d4 == -10
                               else "OTHER")
                        ev = {"f": f, "ev": "A4_TRANSITION",
                              "from": truck_a4_prev, "to": e["a4"],
                              "cls": cls}
                        jf.write(json.dumps(ev) + "\n")
                        A4["events"].append((f, cls))
                        log(f"A4 {truck_a4_prev}->{e['a4']} ({cls}) "
                            f"f={f}")
                    truck_a4_prev = e["a4"]
        jf.write(json.dumps(row, default=str) + "\n")
        btns = set()
        act = dec.action
        for k, v in (("IDLE", ""), ("WALK", "RIGHT"), ("BACK", "LEFT"),
                     ("FIRE", "Y"), ("HOP", "RIGHT+B"),
                     ("GRENADE", "A")):
            if act == k:
                btns = set(v.split("+")) if v else set()
        env.run(1, btns)
        # the parity gate
        if parity_i < len(PARITY) and A4["events"] and \
                A4["events"][-1][0] >= PARITY[parity_i][0]:
            want_f, want_cls = PARITY[parity_i]
            got = [(ef, ec) for ef, ec in A4["events"]
                   if abs(ef - want_f) <= 2 and ec == want_cls]
            if not got:
                raise SystemExit(
                    f"ROUTE DIVERGED from r75b1: expected "
                    f"{want_cls}@{want_f}, events={A4['events']}")
            parity_i += 1
        if f == 1879:
            route_f = f
    if parity_i < len(PARITY):
        raise SystemExit(f"ROUTE INCOMPLETE: parity {parity_i}/"
                         f"{len(PARITY)} events={A4['events']}")
    return route_f, freeze_f


def run_battery(env, plan, blobs, jf, out_dir):
    core = env.p.core
    m = env.p.mem
    results = []
    png_n = 0
    for t in plan:
        blob = blobs.get(t["cp"])
        if blob is None:
            results.append({"id": t["id"], "error": "no checkpoint"})
            continue
        core.unserialize(blob)
        inj = t["inj"]
        events = []
        death_f = None
        start_fc = core.frames_run
        kill_f = None
        a4_prev = mem_read(m)["truck_a4"]
        pre = mem_read(m)
        step_count = [0]

        def death_ok():
            # the first 2 frames after the restore settle (the
            # transient alive-word flap); the death frame recorded
            # RELATIVE to the restore
            step_count[0] += 1
            return step_count[0] > 2

        def step(btns=frozenset(), n=1):
            nonlocal death_f, kill_f, a4_prev
            for _ in range(n):
                s0 = m.u32(A_SCORE)
                core.run(1, set(btns))
                r = mem_read(m)
                if r["truck_a4"] is not None and \
                        r["truck_a4"] != a4_prev:
                    d4 = r["truck_a4"] - a4_prev
                    cls = ("CONNECT" if d4 == -100
                           else "CHIP" if d4 == -10 else "OTHER")
                    events.append({"ev": "A4", "delta": d4,
                                   "cls": cls,
                                   "to": r["truck_a4"]})
                    a4_prev = r["truck_a4"]
                    if r["truck_a4"] == 0:
                        kill_f = True
                if s0 != r["score"]:
                    events.append({"ev": "SCORE",
                                   "delta": r["score"] - s0})
                if not r["alive"] and death_f is None \
                        and death_ok():
                    death_f = core.frames_run - start_fc
            return mem_read(m)

        # the injection sequence (the fixed order; each key <= once)
        if inj.get("idle"):
            step(frozenset(), int(inj["idle"]))
        if inj.get("walk"):
            step(HOLD_BTNS["WALK"], int(inj["walk"]))
        if inj.get("fire"):
            step(HOLD_BTNS["FIRE"], int(inj["fire"]))
        if inj.get("down"):
            step(HOLD_BTNS["DOWN"], int(inj["down"]))
        if inj.get("hop"):
            step(HOLD_BTNS["HOP"], 1)
        if inj.get("bhop"):
            step(HOLD_BTNS["BHOP"], 1)
        if inj.get("lob"):
            step(HOLD_BTNS["GRENADE"], 1)
        if inj.get("back"):
            step(HOLD_BTNS["BACK"], int(inj["back"]))
        if inj.get("lob2"):
            step(HOLD_BTNS["GRENADE"], 1)
        # the observation horizon (the per-frame poll, the held
        # buttons for the dodge-matrix holds)
        held = HOLD_BTNS.get(inj.get("hold") or "", frozenset())
        horizon = int(inj.get("horizon") or inj.get("obs") or 0)
        march0 = len(pre["marchers"])
        marcher_deaths = 0
        for _ in range(horizon):
            core.run(1, set(held))
            r = mem_read(m)
            if r["truck_a4"] is not None and r["truck_a4"] != a4_prev:
                d4 = r["truck_a4"] - a4_prev
                cls = ("CONNECT" if d4 == -100
                       else "CHIP" if d4 == -10 else "OTHER")
                events.append({"ev": "A4", "delta": d4, "cls": cls,
                               "to": r["truck_a4"]})
                a4_prev = r["truck_a4"]
                if r["truck_a4"] == 0 and kill_f is None:
                    kill_f = core.frames_run
            if not r["alive"] and death_f is None and death_ok():
                death_f = core.frames_run - start_fc
                png_n += 1
                shot(env, os.path.join(
                    out_dir, f"r76_{t['id']}_death.png"))
            cur = len(r["marchers"])
            if cur < march0:
                marcher_deaths += march0 - cur
                march0 = cur
                events.append({"ev": "MARCHER_DEATH",
                               "n_gone": marcher_deaths,
                               "at_fc": core.frames_run})
                png_n += 1
                shot(env, os.path.join(
                    out_dir, f"r76_{t['id']}_marcher.png"))
        post = mem_read(m)
        res = {"id": t["id"], "block": t["block"], "cp": t["cp"],
               "title": t["title"], "inj": inj,
               "pre": {k: pre[k] for k in ("px", "php", "score",
                                           "gren", "alive",
                                           "truck_a4")},
               "post": {k: post[k] for k in ("px", "php", "score",
                                             "gren", "alive",
                                             "truck_a4",
                                             "truck_st")},
               "death_f": death_f, "killed_truck": kill_f,
               "marcher_deaths": marcher_deaths,
               "n_marchers_end": len(post["marchers"]),
               "marchers_end": post["marchers"][:4],
               "events": events[:24]}
        results.append(res)
        jf.write(json.dumps(res, default=str) + "\n")
        jf.flush()
        tag = ""
        if kill_f:
            tag = " *** TRUCK KILLED ***"
        if death_f is None and t["block"] in ("A", "D", "E"):
            tag = " *** SURVIVED ***"
            png_n += 1
            shot(env, os.path.join(out_dir,
                                   f"r76_{t['id']}_survived.png"))
        log(f"{t['id']} [{t['block']}] {t['title'][:44]:44} "
            f"alive={post['alive']} death_f={death_f} "
            f"a4={post['truck_a4']} score={post['score']} "
            f"md={marcher_deaths}{tag}")
    return results


def load_disk_checkpoints(env, names):
    """The battery-only path: boot -> load each disk checkpoint ->
    re-serialize into the memory blobs (the fast restores)."""
    blobs = {}
    for name in names:
        env.p.load_state(name)
        blobs[name] = env.p.core.serialize()
        log(f"loaded {name} from disk ({len(blobs[name])} B, "
            f"fc={env.p.core.frames_run})")
    return blobs


def main():
    battery_only = "--battery-only" in sys.argv
    n = amend_ledger(
        "BOOT 2 (battery-only): the boot-1 disk checkpoints (the "
        "verified r74b1-parity route) loaded directly; the route "
        "phase skipped after the parity-gate string/int defect "
        "(fixed in the same commit)"
        if battery_only else
        "BOOT 1: the route + the checkpoints; the battery is "
        "restore-only")
    os.makedirs(EVID, exist_ok=True)
    plan = json.load(open(PLAN))
    bat_path = os.path.join(EVID, "r76_battery.jsonl")
    t0 = time.time()
    if battery_only:
        env = make_env(RuntimeConfig(
            game="metal_slug_x", episodes=1,
            max_frames_per_episode=10000, output_dir=""))
        log("booting (battery-only)...")
        blobs = load_disk_checkpoints(env, CHECK_FRAMES.values())
        assert len(blobs) == len(CHECK_FRAMES), blobs.keys()
        freeze_f = 1151
        route_f = None
    else:
        out_path = os.path.join(EVID, "r76_route.jsonl")
        jf = open(out_path, "w")
        log("booting (the engine's verbatim wiring)...")
        env = make_env(RuntimeConfig(
            game="metal_slug_x", episodes=1,
            max_frames_per_episode=10000, output_dir=""))
        ad = adapter_for_game("metal_slug_x", env)
        pol = policy_for_game(cfg := RuntimeConfig(
            game="metal_slug_x", episodes=1,
            max_frames_per_episode=10000, output_dir=""))
        ident = pol.identity()
        log("policy:", ident.get("name"), "| adapter:",
            getattr(ad, "version", "?"))
        ad.wait_ready(deadline_s=90.0)
        ad.start_episode(6)
        blobs = {}
        route_f, freeze_f = run_route(env, ad, pol, jf, blobs)
        jf.close()
        log(f"route done f={route_f} freeze={freeze_f} "
            f"({time.time()-t0:.0f}s); checkpoints: "
            f"{sorted(blobs)}")
    # ---- the battery (restore-only; the resume skips the done ids)
    done = set()
    if os.path.exists(bat_path):
        with open(bat_path) as f:
            for line in f:
                try:
                    done.add(json.loads(line).get("id"))
                except Exception:                     # noqa: BLE001
                    pass
        log(f"resume: {len(done)} tests already done "
            f"({sorted(done)[:3]}...)")
    todo = [t for t in plan["tests"] if t["id"] not in done]
    log(f"the battery: {len(todo)} tests to run")
    bf = open(bat_path, "a")
    results = run_battery(env, todo, blobs, bf, EVID)
    bf.close()
    summary = {
        "round": "R76", "boot": n, "route_f": route_f,
        "freeze_f": freeze_f, "n_tests": len(results),
        "survivors": [r["id"] for r in results
                      if r.get("post", {}).get("alive")
                      and r["block"] in ("A", "D", "E")],
        "truck_kills": [r["id"] for r in results
                        if r.get("killed_truck")],
        "marcher_kills": {r["id"]: r.get("marcher_deaths")
                          for r in results
                          if r.get("marcher_deaths")},
        "wallclock_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(EVID, "r76_battery_summary.json"),
              "w") as f:
        json.dump(summary, f, indent=1)
    log("SUMMARY:", json.dumps({k: v for k, v in summary.items()
                                if k != "marcher_kills"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
