#!/usr/bin/env python3
"""r71_chip_probe.py — R71 product-track boot: THE CHIP-CONNECT KILL
SCHEDULE probe (policy v1.9.0 K1).

A READ-ONLY product-stack probe (the R64/R67/R68/R69/R70 diagnostic
precedent, disclosed in the round report).  It runs the REAL product
loop (the registered adapter v0.5.1 + the shipped policy v1.9.0) and
answers exactly the R71 questions:

  K1: does the aimed cooldown chip-fire REACH the parked truck at
      the record posture (the player's own chip rate — never yet
      isolated; the R70 chips were the escort strays + the C4
      wrong-phase lob)?
  THE KILL MATH: chips (-10 each) + TWO centered connects (-100
      each) reach a4 0 inside the scroll-capped window — the kill
      does NOT need three phase-connects (the R70 report)?
  THE CORRIDOR-FEED MAP data: every-frame entity tables from the
      drive-in through the fight — the walker spawn frames /
      positions / trajectories (the offline analysis mines the
      time- vs position-trigger question).

Method: the real adapter + the real policy, per-decision
diagnostics; the FULL entity table dumped every frame from f=650;
PNGs at every a4 transition, the kill and the death.  No RAM writes.
Legal inputs only.  No gameplay claim beyond the probe itself: a
perception diagnostic.

Boot ledger: scratch/r71/boots_used.json — the PRODUCT cap 3,
disclosed pre-run (boot 1 = this probe; boots 2-3 = the correction
cycle if the kill math needs a correction).

Evidence: data/games/SLUS-01212/truck_evidence/r71/
          r71_chip_probe.jsonl
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
    TABLE, STRIDE, SLOTS, CORPSE_ST)

EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r71")
SCRATCH = os.path.join(_REPO, "scratch", "r71")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
BOOT_CAP = 3

ACTION_BTNS = {
    "IDLE": frozenset(),
    "WALK": frozenset({"RIGHT"}),
    "BACK": frozenset({"LEFT"}),
    "FIRE": frozenset({"Y"}),
    "HOP": frozenset({"RIGHT", "B"}),
    "GRENADE": frozenset({"A"}),
}

TABLE_FROM = 650                  # the every-frame table window
MAX_F = 2400
SHOTS = (790, 795, 800, 811, 820, 825, 830, 900, 985, 990, 1140,
         1150, 1155, 1200, 1300)
DEAD_FAMILY = ("0xa304", "0xa44c", "0xa45c")
TRUCK_FAMILY = ("0x9e88", "0x9c14", "0x9e08")


def log(*a):
    print("[r71-probe]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason):
    os.makedirs(SCRATCH, exist_ok=True)
    if not os.path.exists(LEDGER):
        led = {"cap": BOOT_CAP, "count": 0, "log": [],
               "disclosed": "R71 product track: boot 1 = the v1.9.0 "
                            "chip-connect kill probe; boots 2-3 = "
                            "the correction cycle.  Read-only "
                            "product-loop probes: legal inputs only, "
                            "zero RAM writes, no training, no "
                            "runtime LLM."}
    else:
        with open(LEDGER) as f:
            led = json.load(f)
    if int(led.get("count", 0)) + 1 > int(led.get("cap", 0)):
        raise SystemExit("BOOT CAP EXCEEDED (r71 product ledger)")
    led["count"] = int(led.get("count", 0)) + 1
    led["log"].append({"n": led["count"],
                       "ts": time.strftime("%FT%TZ", time.gmtime()),
                       "script": "r71_chip_probe.py",
                       "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


def full_table(m):
    rows = []
    for s in range(1, SLOTS):
        base = TABLE + s * STRIDE
        st = int(m.u16(base))
        xw = int(m.u32(base + 0x78))
        if not xw:
            continue
        rows.append({"slot": s, "st": hex(st),
                     "x": round(xw / 65536.0, 1),
                     "h": int(m.u16(base + 0x7E)),
                     "a4": int(m.u16(base + 0xA4)),
                     "sx": int(m.u16(base + 0x8E)),
                     "corpse": st in CORPSE_ST})
    return rows


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


def main():
    # the boot-3 falsification arm (disclosed pre-run): R71_CHIP_FIRE=0
    # patches the policy module's TRUCK_CHIP_FIRE to False — the
    # exact v1.8.5 idle-hold semantics on the v0.5.2 adapter (the
    # ONE-VARIABLE test: the chip-fire stream vs the phase law)
    chip_arm = os.environ.get("R71_CHIP_FIRE", "1") != "0"
    if not chip_arm:
        import ps1play.adapters.metal_slug_x.policy as _pol
        _pol.TRUCK_CHIP_FIRE = False
        log("BOOT-3 ARM: TRUCK_CHIP_FIRE=False (the one-variable "
            "falsification test — the v1.8.5 hold semantics)")
    n = amend_ledger("BOOT the v1.9.0 chip-connect kill probe "
                     "(K1: the aimed cooldown chip-fire at the "
                     "record posture; the kill math: the chips + "
                     "TWO centered connects)"
                     if chip_arm else
                     "BOOT-3 the falsification arm: the v1.8.5 "
                     "idle-hold semantics on the v0.5.2 adapter "
                     "(the chip-fire stream vs the phase law)")
    os.makedirs(EVID, exist_ok=True)
    out_path = os.path.join(EVID, "r71_chip_probe.jsonl")
    jf = open(out_path, "w")

    def J(ev):
        ev["boot"] = n
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "BOOT_DISCLOSED", "n": n, "cap": BOOT_CAP,
       "policy": "msx_mission1_rules:1.9.0",
       "chip_fire_arm": chip_arm,
       "note": "read-only product-loop probe"})
    log("booting the product stack (the engine's verbatim wiring)...")
    cfg = RuntimeConfig(game="metal_slug_x", episodes=1,
                        max_frames_per_episode=10000,
                        output_dir="")
    env = make_env(cfg)                    # the fresh BaseEnv boot
    ad = adapter_for_game("metal_slug_x", env)
    pol = policy_for_game(cfg)
    ident = pol.identity()
    log("policy:", ident.get("name"), "| adapter:",
        ad.version if hasattr(ad, "version") else "?")
    J({"ev": "STACK", "policy": ident.get("name"),
       "policy_sha": ident.get("policy_sha256", "")[:16],
       "adapter": getattr(ad, "version", "?")})

    ad.wait_ready(deadline_s=90.0)
    ad.start_episode(6)

    log("loop start")
    t0 = time.time()
    truck_a4_prev = None
    seen_slots = {}               # the corridor-feed map data
    for f in range(1, MAX_F):
        frame = Frame(seq=f, emulator_frame_count=f, rgb=None,
                      timestamp=float(f), stale=False)
        obs = ad.observe(frame)
        dec = pol.predict(obs)
        x = obs.values
        row = {"f": f, "px": round(float(x[0]), 1),
               "score": int(x[1]), "php": int(x[2]), "gren": int(x[3]),
               "alive": float(x[4]) > 0.5,
               "ents": [[round(float(x[6 + 3 * i]), 1),
                         int(x[7 + 3 * i]), int(x[8 + 3 * i])]
                        for i in range(5)
                        if not (x[7 + 3 * i] == 0
                                and x[6 + 3 * i] == 0)],
               "rule": dec.diagnostics.get("rule"),
               "act": dec.action}
        rule = dec.diagnostics.get("rule") or ""
        if rule in ("truck_lead_throw", "truck_connect_grenade",
                    "truck_phase_hold", "truckin_hold",
                    "truckin_approach", "truck_lead_turn",
                    "truck_chip_fire", "truck_chip_wait",
                    "truck_chip_turn", "truck_width_probe"):
            row["diag"] = {k: v for k, v in dec.diagnostics.items()
                           if k != "rule"}
        if f >= TABLE_FROM:
            tab = full_table(env.p.mem)
            row["table"] = tab
            # the corridor-feed map data: new slots appearing
            for e in tab:
                s = e["slot"]
                if s not in seen_slots and e["x"] != 0.0 \
                        and not e["corpse"]:
                    seen_slots[s] = {"f": f, "x": e["x"],
                                     "st": e["st"]}
                    J({"ev": "SPAWN", "f": f, "slot": s,
                       "x": e["x"], "st": e["st"], "px": row["px"]})
            # the truck armor watch (keyed on the state family)
            for e in tab:
                if e["st"] in TRUCK_FAMILY:
                    if truck_a4_prev is not None \
                            and e["a4"] != truck_a4_prev:
                        d4 = e["a4"] - truck_a4_prev
                        ev = {"f": f, "ev": "A4_TRANSITION",
                               "from": truck_a4_prev, "to": e["a4"],
                               "delta": d4, "st": e["st"],
                               "x": e["x"], "prev_rule": rule,
                               "cls": ("CONNECT" if d4 == -100
                                       else "CHIP" if d4 == -10
                                       else "OTHER")}
                        J(ev)
                        log(f"A4 {truck_a4_prev}->{e['a4']} "
                            f"({ev['cls']}) rule={rule} f={f}")
                        p = os.path.join(
                            EVID, f"r71_a4_{truck_a4_prev}_"
                                  f"{e['a4']}_f{f}.png")
                        shot(env, p)
                        if e["a4"] <= 0:
                            J({"f": f, "ev": "A4_ZERO",
                               "st": e["st"], "score": row["score"]})
                            shot(env, os.path.join(
                                EVID, f"r71_a4_zero_f{f}.png"))
                    truck_a4_prev = e["a4"]
            # the kill signature: the dead family row
            for e in tab:
                if e["st"] in DEAD_FAMILY:
                    J({"f": f, "ev": "TRUCK_DEAD_ROW", "st": e["st"],
                       "x": e["x"], "score": row["score"]})
                    shot(env, os.path.join(
                        EVID, f"r71_truck_dead_f{f}.png"))
                    log(f"TRUCK DEAD ROW {e['st']} f={f} "
                        f"score={row['score']}")
        J(row)
        if f in SHOTS:
            p = os.path.join(EVID, f"r71_probe_f{f}.png")
            if shot(env, p):
                J({"f": f, "ev": "SHOT", "path": p})
        btns = ACTION_BTNS.get(dec.action, frozenset())
        env.run(1, set(btns))
        if not ad.alive():
            J({"f": f, "ev": "DEATH",
               "px": round(float(x[0]), 1), "score": int(x[1]),
               "table": full_table(env.p.mem)})
            shot(env, os.path.join(EVID, "r71_probe_death.png"))
            log(f"DEATH at f={f} px={x[0]:.0f} score={int(x[1])}")
            break
        if time.time() - t0 > 500:
            J({"f": f, "ev": "WALL_END"})
            break
    # the run summary (the R71 verdict data)
    J({"ev": "RUN_END", "frames": f, "score": int(x[1]),
       "px": round(float(x[0]), 1),
       "spawns": {str(k): v for k, v in seen_slots.items()},
       "wallclock_s": round(time.time() - t0, 1)})
    jf.close()
    log("probe ->", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
