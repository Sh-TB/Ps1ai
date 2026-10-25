#!/usr/bin/env python3
"""policy_chain_trial.py — Issue #5 session 4, Phase-5 paired trial.

The session-4 chain (chain_a_full.py v6) reached the MISSION 1 banner
3/3 with SCRIPTED taps.  This trial asks the sharper question: does
the SHIPPED PLUGIN POLICY (ps1play.agent.combat.CombatPolicy — the
thing the runner actually executes) do it alone?

Arms (each x3, fresh pin_ckpt):
  fix      the patched policy: scan_entities excludes CORPSE_ST rows
           (F9 mis-aim fix) + the 0xC mission-end HOLD (banner
           countdown protection).
  baseline emulates the pre-patch shipped behaviour: corpses are
           re-included in the scan (they carry a valid screen-x until
           their ~+138f despawn) and the mission-end latch is reset
           every chunk (no hold) — the exact two deltas of this
           session's patch, nothing else.

PASS = the (0xC, *) banner at px < 200 within the budget (PNG).
FAIL modes recorded: banner_expired (px jumped <200 without 0xC =
restart), death (php0 / px0), budget.

Usage: python3 scripts/policy_chain_trial.py [--arm fix] [--runs 3]
"""
import argparse
import json
import os
import sys
import time
import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _REPO)

from ps1play import labconfig
from issue4_controller import boot
import ps1play.agent.combat as combat

TABLE, STRIDE = combat.TABLE, combat.STRIDE
PLAYER_X = 0x0CA2E0
A_SCORE = 0x0EE318
GRENADES = 0x0EDCF4
PLAYER_HP = 0x0CA2F6
EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_policy_trial")


def log(*a):
    print("[pt]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def snap(m):
    return {"px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "gren": int(m.u8(GRENADES)),
            "php": int(m.u16(PLAYER_HP)),
            "sec": (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS))),
            "prog": int.from_bytes(
                m.ram[0xEB5D4:0xEB5D8].tobytes(), "little")}


def alive(m):
    return (int(m.u32(0x0EE518)) & 0xFF) == 0xFF and px_of(m) != 0.0


def png(p, name, tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(EVID,
                                               f"{tag}_{name}.png"))


def scan_with_corpses(mem, px=None):
    """Baseline scan: the pre-session-4 behaviour — corpses INCLUDED.

    Identical to combat.scan_entities minus the CORPSE_ST filter
    (the patch's delta #1), so the paired trial isolates exactly the
    session-4 change."""
    if px is None:
        px = int(mem.u32(combat.PLAYER_X)) / 65536.0
    out = []
    for s in range(1, combat.SLOTS):
        base = combat.TABLE + s * combat.STRIDE
        xw = int(mem.u32(base + 0x78))
        hp = int(mem.u16(base + 0x8E))
        if not xw or not hp:
            continue
        if hp >= combat.ENEMY_HP_SIGNED or hp > combat.ENEMY_HP_MAX:
            continue
        x_px = xw / 65536.0
        if not 0.0 < x_px < 4096.0:
            continue
        dx = x_px - px
        if abs(dx) > combat.ENGAGE_WINDOW:
            continue
        h = int(mem.u16(base + 0x7E))
        st = int(mem.u16(base))
        hp_a4 = int(mem.u16(base + combat.ENTITY_HP_A4))
        out.append({"slot": s, "x_px": round(x_px, 1),
                    "dx_px": round(dx, 1), "hp": hp, "sx": hp,
                    "h": h, "st": st, "hp_a4": hp_a4,
                    "kind": ("projectile_air" if h > combat.GROUND_HEIGHT
                             else "enemy")})
    out.sort(key=lambda e: abs(e["dx_px"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="fix", choices=["fix", "baseline"])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--chunks", type=int, default=340)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    t0 = time.time()
    results = []
    p, fw = boot()
    m = p.mem
    for r in range(args.runs):
        tag = f"{args.arm}{r + 1}_{time.strftime('%H%M%S')}"
        jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

        def J(ev):
            jf.write(json.dumps(ev, default=str) + "\n")
            jf.flush()

        p.load_state("pin_ckpt")
        pol = combat.CombatPolicy()
        J({"ev": "start", "arm": args.arm, "run": r + 1, **snap(m)})
        log(f"=== {args.arm} run {r + 1}/{args.runs} ===")

        # wait for the pin-cycle warp to the wave zone (k<=18, proven)
        warped = False
        for k in range(60):
            s = snap(m)
            if not alive(m):
                for w in range(60):
                    p.core.run(30, set())
                    if alive(m):
                        break
                continue
            if s["px"] < 1100.0:
                warped = True
                J({"ev": "WARP", "k": k, **s})
                break
            p.core.run(30, set())

        outcome, end_k, deaths = None, None, 0
        last_px, last_segs = None, None
        if warped:
            for c in range(args.chunks):
                s = snap(m)
                if not alive(m):
                    deaths += 1
                    J({"ev": "death", "chunk": c, **s})
                    got = False
                    for w in range(60):
                        p.core.run(30, set())
                        if alive(m):
                            got = True
                            break
                    if not got:
                        outcome = "death_no_respawn"
                        break
                    last_px, last_segs = None, None
                    continue
                if px_of(m) > 5000.0:
                    # mission-transition garbage (px u32 reads
                    # 0xFFFF_xxxx while the world rebuilds — trial
                    # c=14): skip the chunk entirely
                    p.core.run(60, set())
                    continue
                px_early = px_of(m)
                sec = combat.scan_section(m)
                pol.observe_section(sec, px_now=px_early)
                if args.arm == "baseline" and pol.mission_end:
                    # delta #2: the pre-patch policy has NO hold —
                    # reset the latch so decide() never holds
                    pol.mission_end = False
                    pol.me_streak = 0
                px = px_of(m)
                advanced = 0.0 if last_px is None else px - last_px
                intent = any("RIGHT" in (x.get("btns") or set())
                             for x in (last_segs or []))
                pol.observe(px, advanced, intent)
                scan = (scan_with_corpses(m, px=px)
                        if args.arm == "baseline"
                        else combat.scan_entities(m, px=px))
                # 15f micro-chunks (the policy is chunk-size
                # independent since v0.7): the (0,8) pre-banner reset
                # must be caught FAST — a 60f segment of inputs can
                # skip the banner mid-chunk (trial c=13, 3/3)
                segs = pol.decide(15, px, scan,
                                  grenades=int(m.u8(GRENADES)),
                                  hp=int(m.u16(PLAYER_HP)))
                last_px, last_segs = px, segs
                _pre = combat.scan_section(m)
                for x in segs:
                    p.core.run(x["frames"], x["btns"] or set())
                _post = combat.scan_section(m)
                if (_pre["state"], _pre["flags"]) != \
                        (_post["state"], _post["flags"]):
                    png(p, f"sec_{_post['state']:02x}"
                           f"_{_post['flags']:02x}", tag)
                s2 = snap(m)
                J({"ev": "chunk", "c": c, "mode": pol.mode, **s2,
                   "n": len(scan)})
                if s2["sec"][0] == 0xC and s2["px"] < 200.0:
                    outcome = "MISSION_BANNER"
                    end_k = c
                    png(p, "mission_banner", tag)
                    J({"ev": "MISSION_BANNER", "chunk": c, **s2})
                    log(f"MISSION BANNER c={c} px={s2['px']} "
                        f"score={s2['score']}")
                    break
                if s2["px"] < 200.0 and c > 4 and \
                        s2["sec"][0] in (0xB, 0x0):
                    outcome = "banner_expired_restart"
                    end_k = c
                    J({"ev": "RESTART_SEEN", "chunk": c, **s2})
                    log(f"RESTART c={c} px={s2['px']} sec={s2['sec']}")
                    break
            else:
                outcome = "budget"
        else:
            outcome = "no_warp"
        png(p, "final", tag)
        res = {"run": r + 1, "arm": args.arm, "outcome": outcome,
               "end_chunk": end_k, "deaths": deaths,
               "pol_stats": {k: v for k, v in pol.stats.items()
                             if v},
               "final": snap(m)}
        results.append(res)
        J({"ev": "RUN_DONE", **res})
        jf.close()
        log(f"RUN {r + 1}: {outcome} c={end_k} deaths={deaths}")

    rep = {"schema": "issue5/policy-chain-trial/1",
           "arm": args.arm, "runs": results,
           "wall_s": round(time.time() - t0, 1), "firmware": fw,
           "game_sha256":
               "45cde149878fe945d0219fd0f61ca09856aee66bdcc9119de21c0583f1d0667d"}
    with open(os.path.join(EVID, f"report_{args.arm}_{int(t0)}.json"),
              "w") as f:
        json.dump(rep, f, indent=1, default=str)
    log("ALL DONE", json.dumps([{k: r[k] for k in
                                 ("run", "outcome")} for r in
                                results]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
