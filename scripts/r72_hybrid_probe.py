#!/usr/bin/env python3
"""r72_hybrid_probe.py — R72 product-track boot: THE VOLLEY+PHASE
HYBRID (policy v2.0.0).

A READ-ONLY product-stack probe (the R64/R67/R68/R69/R70/R71
diagnostic precedent, disclosed in the round report).  It runs the
REAL product loop (the registered adapter v0.5.2 + the shipped
policy v2.0.0 — NO module patching: the hybrid IS the shipped
default) and answers exactly the R72 questions:

  THE HYBRID: the gre40 cadence gated by the FULL +-2f phase
  tolerance — do the on-grid landings connect from the idle-hold
  stream (the boot-3 evidence said 1/3)?  Does the widened
  pre-side window (the land 176/177 throws) produce the connect
  the v1.9.0 gate could never reach?
  THE KILL MATH: the connect rate per window vs the 3-connect
  kill; the chips as the supplement are OFF (the re-selection).

Method: the real adapter + the real policy, per-decision
diagnostics; the FULL entity table dumped every frame from f=650;
PNGs at the freeze, every grid throw, every a4 transition, the
kill and the death.  No RAM writes.  Legal inputs only.  No
gameplay claim beyond the probe itself: a perception diagnostic.

Boot ledger: scratch/r72/boots_used.json — the PRODUCT cap 3,
disclosed pre-run (boot 1 = this probe; boots 2-3 = the correction
cycle if the hybrid needs one).

Evidence: data/games/SLUS-01212/truck_evidence/r72/
          r72_hybrid_probe.jsonl (per boot)
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
                    "truck_evidence", "r72")
SCRATCH = os.path.join(_REPO, "scratch", "r72")
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
DEAD_FAMILY = ("0xa304", "0xa44c", "0xa45c")
TRUCK_FAMILY = ("0x9e88", "0x9c14", "0x9e08")
FIGHT_RULES = ("truck_lead_throw", "truck_connect_grenade",
               "truck_phase_hold", "truck_connect_hold",
               "truckin_hold", "truckin_approach", "truck_lead_turn",
               "truck_turn", "truck_width_probe",
               "truck_connect_retreat")


def log(*a):
    print("[r72-probe]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason):
    os.makedirs(SCRATCH, exist_ok=True)
    if not os.path.exists(LEDGER):
        led = {"cap": BOOT_CAP, "count": 0, "log": [],
               "disclosed": "R72 product track: boot 1 = the v2.0.0 "
                            "volley+phase hybrid probe (the shipped "
                            "default: TRUCK_CHIP_FIRE=False, the "
                            "full +-2f gate); boots 2-3 = the "
                            "correction cycle.  Read-only "
                            "product-loop probes: legal inputs only, "
                            "zero RAM writes, no training, no "
                            "runtime LLM."}
    else:
        with open(LEDGER) as f:
            led = json.load(f)
    if int(led.get("count", 0)) + 1 > int(led.get("cap", 0)):
        raise SystemExit("BOOT CAP EXCEEDED (r72 product ledger)")
    led["count"] = int(led.get("count", 0)) + 1
    led["log"].append({"n": led["count"],
                       "ts": time.strftime("%FT%TZ", time.gmtime()),
                       "script": "r72_hybrid_probe.py",
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
    n = amend_ledger("BOOT the v2.0.0 volley+phase hybrid probe "
                     "(the shipped default: the idle-hold stream + "
                     "the full +-2f gate; the K1 chip supplement "
                     "OFF)")
    os.makedirs(EVID, exist_ok=True)
    out_path = os.path.join(EVID,
                            f"r72_hybrid_probe_boot{n}.jsonl")
    jf = open(out_path, "w")

    def J(ev):
        ev["boot"] = n
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "BOOT_DISCLOSED", "n": n, "cap": BOOT_CAP,
       "policy": "msx_mission1_rules:2.0.0",
       "chip_fire_default": False,
       "note": "read-only product-loop probe; the shipped hybrid"})
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
       "truck_rules": ident.get("truck_rules"),
       "adapter": getattr(ad, "version", "?")})

    ad.wait_ready(deadline_s=90.0)
    ad.start_episode(6)

    log("loop start")
    t0 = time.time()
    truck_a4_prev = None
    throws = []
    connects = []
    chips = 0
    freeze_f = None
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
        if rule in FIGHT_RULES:
            row["diag"] = {k: v for k, v in dec.diagnostics.items()
                           if k != "rule"}
        if rule == "truck_connect_grenade":
            d = dict(dec.diagnostics)
            throws.append({"f": f, "fight_f": d.get("fight_f"),
                           "phase_k": d.get("phase_k"),
                           "phase_off": d.get("phase_off"),
                           "grenades_used": d.get("grenades_used")})
            J({"ev": "GRID_THROW", "f": f,
               "fight_f": d.get("fight_f"),
               "phase_k": d.get("phase_k"),
               "phase_off": d.get("phase_off"),
               "grenades_used": d.get("grenades_used")})
            shot(env, os.path.join(
                EVID, f"r72_boot{n}_throw_k{d.get('phase_k')}_"
                      f"f{f}.png"))
        if f >= TABLE_FROM:
            tab = full_table(env.p.mem)
            row["table"] = tab
            # the freeze witness (the first SC_TRUCK sighting)
            if freeze_f is None:
                for e in tab:
                    if e["st"] == "0x9e88":
                        freeze_f = f
                        J({"ev": "FREEZE", "f": f,
                           "px": row["px"],
                           "truck": e})
                        shot(env, os.path.join(
                            EVID, f"r72_boot{n}_freeze_f{f}.png"))
                        break
            # the truck armor watch (keyed on the state family)
            for e in tab:
                if e["st"] in TRUCK_FAMILY:
                    if truck_a4_prev is not None \
                            and e["a4"] != truck_a4_prev:
                        d4 = e["a4"] - truck_a4_prev
                        cls = ("CONNECT" if d4 == -100
                               else "CHIP" if d4 == -10
                               else "OTHER")
                        ev = {"f": f, "ev": "A4_TRANSITION",
                              "from": truck_a4_prev, "to": e["a4"],
                              "delta": d4, "st": e["st"],
                              "x": e["x"], "prev_rule": rule,
                              "cls": cls}
                        J(ev)
                        log(f"A4 {truck_a4_prev}->{e['a4']} "
                            f"({cls}) rule={rule} f={f}")
                        if cls == "CONNECT":
                            connects.append({"f": f,
                                             "fight_f":
                                                 f - (freeze_f or f),
                                             "throw": throws[-1]
                                             if throws else None})
                        elif cls == "CHIP":
                            chips += 1
                        p = os.path.join(
                            EVID, f"r72_boot{n}_a4_{truck_a4_prev}_"
                                  f"{e['a4']}_f{f}.png")
                        shot(env, p)
                        if e["a4"] <= 0:
                            J({"f": f, "ev": "A4_ZERO",
                               "st": e["st"], "score": row["score"]})
                            shot(env, os.path.join(
                                EVID, f"r72_boot{n}_kill_f{f}.png"))
                    truck_a4_prev = e["a4"]
            # the kill signature: the dead family row
            for e in tab:
                if e["st"] in DEAD_FAMILY:
                    J({"f": f, "ev": "TRUCK_DEAD_ROW", "st": e["st"],
                       "x": e["x"], "score": row["score"]})
                    shot(env, os.path.join(
                        EVID, f"r72_boot{n}_truck_dead_f{f}.png"))
                    log(f"TRUCK DEAD ROW {e['st']} f={f} "
                        f"score={row['score']}")
        J(row)
        if f in (790, 811, 985, 990):
            p = os.path.join(EVID, f"r72_boot{n}_f{f}.png")
            if shot(env, p):
                J({"f": f, "ev": "SHOT", "path": p})
        btns = ACTION_BTNS.get(dec.action, frozenset())
        env.run(1, set(btns))
        if not ad.alive():
            J({"f": f, "ev": "DEATH",
               "px": round(float(x[0]), 1), "score": int(x[1]),
               "throws": throws, "connects": connects,
               "chips": chips})
            shot(env, os.path.join(
                EVID, f"r72_boot{n}_probe_death.png"))
            log(f"DEATH at f={f} px={x[0]:.0f} score={int(x[1])} "
                f"throws={len(throws)} connects={len(connects)} "
                f"chips={chips}")
            break
        if time.time() - t0 > 500:
            J({"f": f, "ev": "WALL_END"})
            break
    # the run summary (the R72 verdict data)
    J({"ev": "RUN_END", "frames": f, "score": int(x[1]),
       "px": round(float(x[0]), 1),
       "freeze_f": freeze_f,
       "throws": throws, "connects": connects, "chips": chips,
       "connect_rate": (f"{len(connects)}/{len(throws)}"
                        if throws else "0/0"),
       "wallclock_s": round(time.time() - t0, 1)})
    jf.close()
    log("probe ->", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
