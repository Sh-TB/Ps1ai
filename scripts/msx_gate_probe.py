#!/usr/bin/env python3
"""msx_gate_probe.py — Issue #5/#7 focused follow-up, Phase 2.

Camera-gate condition discovery for the Metal Slug X town
truck/chopper encounter. Order per task: gate trigger FIRST.

Flow reuses the PROVEN components verbatim:
  boot()               issue4_controller (adaptive nav + ownership gate)
  cb0 anchor + freeze  issue5_ab_invuln pattern (capture pair at anchor)
  death recovery       recover_v2 continue acceptance (v1, disclosed)
  traversal cadence    wagon_run pit_mode overlay (B hop + UP+Y anti-air)
  progress sensor      u16(0xCA2E2) — the route-ledger VERIFIED camera
                       word (0..224+ observed scale)

Stages (argv[1]):
  reach   boot -> cb0 anchor -> freeze -> advance loop (continue
          acceptance on death) until the camera-gate arena is isolated:
          ALIVE + progress frozen 8 chunks after progress > 150 ->
          savestate `arena` + arena_report.json
  probeB  from `arena`: controlled one-factor arms from the SAME
          savestate (idle / upy / advance), each 2400f with full
          instrumentation -> probeB_arms.json

Static evidence (msx_gate_static*.py, this task):
  ROOT = *(0x800C9A98); state-machine handler at ROOT+0x0; the 8
  in-overlay jal callers of FUN_800A87F8 install handlers into ROOT+0
  (scripted encounter transitions).
"""
from __future__ import annotations

import json
import os
import sys
import time

from PIL import Image                                     # noqa: E402

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.agent.cheatprof import CheatSession, CHEAT_ASSISTED  # noqa
from ps1play.agent.gameshark import GSCode                # noqa: E402
from mission import ensure_mission, idle_churn                # noqa: E402
from issue4_controller import boot                        # noqa: E402
from run_mission1_legit import recover_v2                 # noqa: E402
from ps1play.telemetry import TelemetryAdapter            # noqa: E402

EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_gate_probe")
os.makedirs(EVID, exist_ok=True)

RAM_MASK = 0x1FFFFF
A_ROOT_SLOT = 0x0C9A98            # *(this) = ROOT encounter object
TABLE = 0x0CA268
STRIDE = 0x14C
HP_OFF = 0x8E
SLOTS = 40
A_PROGRESS = 0x0CA2E2             # u16 route-ledger VERIFIED camera word
A_SCORE = 0x0EE318
A_PAIR0 = 0x0CA2F6
A_PAIR1 = 0x0CA2FE
A_FLAGS = 0x0EE518                # 0xFF == active play (A/B proven)
A_TIMER16 = 0x0D47D4              # u16 mission timer, 1/frame (300s)
ROOT_FIELDS = (0x2C, 0x80, 0x84, 0xE4, 0xF4)
PAIR = (0xCA2F6, 0xCA2FE)
PNG_CAP = 40


class _NullSensor:
    def poll(self, _fc):
        return []


def log(*a):
    print("[gate]", *a, file=sys.stderr, flush=True)


def png(p, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(EVID, name))


def snapshot_state(p):
    m = p.mem
    root = m.u32(A_ROOT_SLOT)
    st = {"root": root if 0x100000 < root < 0x200000 else None,
          "root_raw": root,
          "handler": None, "root_fields": {},
          "progress": m.u16(A_PROGRESS),
          "timer16": m.u16(A_TIMER16),
          "lives": m.u16(0x0CA69A),
          "score": m.u32(A_SCORE),
          "hp0": m.u16(PAIR[0]), "hp1": m.u16(PAIR[1]),
          "flags": m.u32(A_FLAGS) & 0xFF,
          "slots": {}}
    if st["root"] is not None:
        st["handler"] = m.u32(root & RAM_MASK)
        for f in ROOT_FIELDS:
            st["root_fields"][hex(f)] = m.u32((root & RAM_MASK) + f)
    for s in range(SLOTS):
        base = TABLE + s * STRIDE
        st["slots"][s] = {"hp": m.u16(base + HP_OFF),
                          "w78": m.u16(base + 0x78),
                          "w7a": m.u16(base + 0x7A)}
    return st


def freeze_now(p, tag="gate_probe_explore"):
    v0, v1 = int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1]))
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    codes = [GSCode(f"8{PAIR[0]:07X} {v0 & 0xFFFF:04X}"),
             GSCode(f"8{PAIR[1]:07X} {v1 & 0xFFFF:04X}")]
    session.enable(tag, codes)
    log(f"EXPLORATION freeze {tag}: pair=({v0},{v1}) "
        f"{[c.raw for c in codes]}")
    return session


def unfreeze(session, tag="gate_probe_explore"):
    if session is not None:
        try:
            session.disable(tag)
        except Exception:                    # noqa: BLE001
            pass


def advance_schedule(g):
    """Fast-traversal cadence (route ledger remedy: continuous RIGHT,
    fire when needed, hop pits) — same shape as the A/B schedule."""
    btns = {"RIGHT"}
    if (g % 45) < 12:
        btns.add("Y")
    if 40 <= (g % 90) < 48:
        btns.add("B")
    return btns


def pit_run(p, session, frames, buttons, phase):
    """wagon_run.gs_run pit overlay, local copy (sensor-free)."""
    PIT_B_PERIOD, PIT_B_LEN = 30, 8
    PIT_AA_PERIOD, PIT_AA_LEN = 45, 12
    base = set(buttons) if buttons else set()
    for i in range(frames):
        b = set(base | {"RIGHT"}) if base else {"RIGHT"}
        g = phase + i
        if (g % PIT_B_PERIOD) < PIT_B_LEN:
            b.add("B")
        if (g % PIT_AA_PERIOD) < PIT_AA_LEN:
            b |= {"UP", "Y"}
        p.core.set_buttons(b)
        p.core.run_frame()
        if session is not None:
            session.gs.tick()
    return phase + frames


# =====================================================================
def stage_reach(max_chunks=500, max_continues=40):
    p, fw = boot()
    p.save_state("cb0")
    session = freeze_now(p, "reach_freeze")
    phase = 0
    continues = 0
    max_prog = 0
    max_prog_ever = 0
    prog_streak = 0
    hist = []
    events = []
    t0 = time.time()
    arena = None
    png(p, "reach_start.png")
    for chunk in range(max_chunks):
        if time.time() - t0 > 50 * 60:
            events.append({"chunk": chunk, "stop": "WALL_BUDGET"})
            break
        phase = pit_run(p, session, 60, advance_schedule(phase), phase)
        prog = p.mem.u16(A_PROGRESS)
        flags = p.mem.u32(A_FLAGS) & 0xFF
        alive = flags == 0xFF
        # respawn regression (checkpoint death without continue screen):
        # progress falls well below the frontier
        regression = max_prog - prog > 25
        if regression:
            max_prog = prog
            prog_streak = 0
            events.append({"chunk": chunk, "event": "respawn_regression",
                           "prog": prog, "timer16": p.mem.u16(A_TIMER16)})
        max_prog = max(max_prog, prog)
        max_prog_ever = max(max_prog_ever, prog)
        hist.append({"chunk": chunk, "prog": prog, "alive": alive,
                     "score": p.mem.u32(A_SCORE),
                     "hp0": p.mem.u16(PAIR[0])})
        if not alive:
            continues += 1
            png(p, f"reach_DEATH_c{chunk:04d}.png")
            events.append({"chunk": chunk, "event": "death",
                           "prog": prog, "continues": continues})
            log(f"c{chunk} DEATH (flags={flags}) prog={prog} -> "
                f"continue {continues}")
            if continues > max_continues:
                events.append({"chunk": chunk, "stop": "CONTINUE_CAP"})
                break
            unfreeze(session, "reach_freeze")
            recover_v2(p, log=log)
            g = ensure_mission(p, tries=4, log=log, want_hp_cands=False)
            log("re-gate:", g.get("in_mission"),
                "prog now:", p.mem.u16(A_PROGRESS))
            # let the respawn animation fully finish BEFORE capturing
            # freeze values (mid-transition values are garbage)
            p.core.run(180, set())
            session = None
            for _try in range(4):
                session = freeze_now(p, "reach_freeze")
                if p.mem.u16(PAIR[0]) > 50:
                    break
                unfreeze(session, "reach_freeze")
                p.core.run(90, set())
            p.core.run(2, set())
            prog_streak = 0
            continue
        # ---- live arena monitor (every chunk, churn-gated) ----
        prog_streak = prog_streak + 1 if chunk > 0 and \
            prog == hist[-2]["prog"] else 0
        score_now = p.mem.u32(A_SCORE)
        hp0v = p.mem.u16(PAIR[0])
        if chunk > 12 and prog_streak >= 4 and hp0v > 50 and \
                (score_now >= 2000 or continues >= 1 or
                 max_prog_ever >= 150):
            ch = idle_churn(p, 40)
            if ch > 800:
                # idle_churn runs unticked frames (freeze silently
                # stops) — re-assert the freeze, then capture
                for _ in range(2):
                    p.core.run_frame()
                    session.gs.tick()
                png(p, "reach_ARENA_live.png")
                p.save_state("arena")
                live = snapshot_state(p)
                live["churn"] = ch
                events.append({"chunk": chunk, "event": "ARENA_LIVE",
                               "st": live})
                log(f"ARENA live capture (mid-fight) c{chunk}: "
                    f"score={live['score']} hp0={live['hp0']} "
                    f"churn={ch} prog={prog}")
                arena = {"chunk": chunk, "prog": prog,
                         "maxE": max_prog_ever, "continues": continues,
                         "live": live}
                break
        if chunk % 25 == 0:
            png(p, f"reach_c{chunk:04d}.png")
            st = snapshot_state(p)
            events.append({"chunk": chunk, "sample": st})
            log(f"c{chunk} prog={prog} maxE={max_prog_ever} alive={alive} "
                f"timer={st['timer16']} score={st['score']} "
                f"hp0={st['hp0']} root_raw={st['root_raw']:#x} "
                f"handler={hex(st['handler']) if st['handler'] else None}")
    out = {"fw": fw, "arena": arena, "max_prog": max_prog,
           "max_prog_ever": max_prog_ever,
           "continues": continues,
           "disclosure": "EXPLORATION: hp_pair freeze + continue "
                         "acceptance (v1 recover_v2), disclosed",
           "hist": hist, "events": events,
           "wall_s": round(time.time() - t0, 1)}
    json.dump(out, open(os.path.join(EVID, "arena_report.json"), "w"),
              indent=1)
    log("reach done:", bool(arena), "wall:", out["wall_s"], "s")
    return bool(arena)


# =====================================================================
def run_arm(p, name, frames=2400, sample_every=10, session=None,
            dismount=True):
    rows = []
    pngs = []
    phase = 0
    t0 = time.time()
    arm_stats = {"continues": 0}
    # ---- common dismount prelude (60f LEFT): the captured state has
    # the player ON the armored truck — arms dismount first so the arm
    # input is the only differing factor. The truckgun arm keeps the
    # mount (higher vulcan reach vs the overhead chopper).
    if dismount:
        for _ in range(60):
            phase = _arm_frame(p, session, {"LEFT"}, phase)
    elif name in ("mosque_grenade", "gateclear"):
        for _ in range(20):                    # short approach only
            phase = _arm_frame(p, session, {"LEFT"}, phase)
    for f in range(frames):
        if name == "idle":
            btns = set()
        elif name == "upy":
            btns = {"UP", "Y"}
        elif name == "upy_left":
            btns = {"LEFT", "UP", "Y"}
        elif name == "jumpgun":
            # jump -> vulcan-up at apex (ground fire cannot reach the
            # chopper altitude — proven zero damage in 2400f)
            btns = {"B"} if (f % 48) < 14 else \
                ({"UP", "Y"} if (f % 48) < 34 else {"Y"})
        elif name == "grenade":
            # grenade arc toward the chopper (hovers above-left of the
            # dismount point): face left, lob on a fixed period
            btns = {"A"} if (f % 80) < 8 else \
                ({"LEFT"} if (f % 80) < 40 else set())
        elif name == "mosque_grenade":
            # the arena is the Mosque Artillery mini-boss fight: the
            # mortars rain from the mosque cannon. Close the distance
            # slightly (20f — NOT the 60f that reaches the left water
            # channel) and lob grenades into the dome on a fixed period.
            btns = {"A"} if (f % 80) < 8 else \
                ({"LEFT"} if (f % 80) < 24 else set())
        elif name == "gateclear":
            # ADAPTIVE two-phase: grenade the mosque until the mortar
            # rain stops (the rain = transient entity slots churning;
            # rain-quiet 300f = the cannon is dead) — then walk right.
            if not arm_stats.get("rain_quiet"):
                btns = {"A"} if (f % 80) < 8 else \
                    ({"LEFT"} if (f % 80) < 24 else set())
            else:
                btns = advance_schedule(f)
        elif name == "truckgun":
            # stay mounted; sustained straight-up vulcan (the chopper
            # hovers directly overhead from the truck bed)
            btns = {"UP", "Y"}
        elif name == "truckwalk":
            # stay on the RIGHT side (the arena's left edge is a lethal
            # water channel); after the scripted truck destruction keep
            # walking right with the pit cadence — the human strategy
            btns = advance_schedule(f)
        elif name == "advance":
            btns = advance_schedule(f)
        else:
            raise ValueError(name)
        phase = _arm_frame(p, session, btns, phase)
        # ---- rain-quiet detector: the mortar rain spawns transient
        # entity slots (lifetime counters 204-254 -> 0); when no
        # transient activity for 5 consecutive samples (300f) the
        # cannon is dead and the walk phase begins ----
        if name == "gateclear" and f % sample_every == 0:
            cur = {s: p.mem.u16(TABLE + s * STRIDE + HP_OFF)
                   for s in range(10, 40)}
            prev = arm_stats.get("prev_slots")
            active = prev is not None and any(
                cur[s] != prev[s] for s in cur)
            q = arm_stats.get("quiet", 0)
            q = q + 1 if not active else 0
            arm_stats["quiet"] = q
            arm_stats["prev_slots"] = cur
            if q >= 5 and not arm_stats.get("rain_quiet"):
                arm_stats["rain_quiet"] = True
                arm_stats["rain_quiet_frame"] = f
                log(f"[arm {name}] mortar rain STOPPED at f={f} "
                    f"-> walk phase")
        # ---- sustain: the in-game CONTINUE screen is near-static
        # (low pixel churn) while gameplay churns; on a static screen
        # tap START ONCE (v1 continue acceptance, disclosed) and wait
        # through the respawn. Gameplay-phase churn keeps taps out.
        if f % 90 == 45:
            ch = idle_churn(p, 30)
            if ch < 250:
                p.core.run(10, {"START"})
                p.core.run(70, set())
                if session is not None:
                    for _ in range(70):
                        p.core.run_frame()
                        session.gs.tick()
                arm_stats["continues"] += 1
        if f % sample_every == 0:
            st = snapshot_state(p)
            st["frame"] = f
            st["arm"] = name
            rows.append(st)
        if f % 250 == 0:
            nm = f"{name}_f{f:05d}.png"
            png(p, nm)
            pngs.append(nm)
    first, last = rows[0], rows[-1]
    slot_deltas = {}
    for s in range(SLOTS):
        h0, h1 = first["slots"][s]["hp"], last["slots"][s]["hp"]
        if h0 != h1:
            slot_deltas[s] = (h0, h1)
    deaths = 0
    prev_alive = True
    for r in rows:
        alive_now = r["slots"][0]["hp"] > 0
        if prev_alive and not alive_now:
            deaths += 1
        prev_alive = alive_now
    handlers = []
    progs = []
    flags_off_frames = 0
    for r in rows:
        h = r["handler"]
        if not handlers or handlers[-1][1] != h:
            handlers.append([r["frame"], h])
        if not progs or progs[-1][1] != r["progress"]:
            progs.append([r["frame"], r["progress"]])
        if r["flags"] != 0xFF:
            flags_off_frames += 1
    summary = {
        "arm": name, "frames": frames,
        "wall_s": round(time.time() - t0, 1),
        "continues_accepted": arm_stats["continues"],
        "progress_first": first["progress"],
        "progress_last": last["progress"],
        "progress_max": max(r["progress"] for r in rows),
        "score_first": first["score"], "score_last": last["score"],
        "score_gain": last["score"] - first["score"],
        "hp0_first": first["hp0"], "hp0_last": last["hp0"],
        "flags_last": last["flags"],
        "deaths": deaths,
        "flags_off_frames": flags_off_frames,
        "slot_deltas": {str(k): v for k, v in slot_deltas.items()},
        "handler_transitions": [[fr, hex(h) if h else None]
                                for fr, h in handlers],
        "progress_steps": progs[:40],
        "pngs": pngs,
    }
    json.dump(rows, open(os.path.join(EVID, f"gate_dump_{name}.jsonl"),
                         "w"))
    log(f"arm {name}: prog {summary['progress_first']}->"
        f"{summary['progress_last']} (max {summary['progress_max']}), "
        f"score +{summary['score_gain']}, slot_deltas={slot_deltas}, "
        f"handlers={len(handlers)}")
    return summary


def _arm_frame(p, session, btns, phase):
    p.core.set_buttons(set(btns) if btns else set())
    p.core.run_frame()
    if session is not None:
        session.gs.tick()
    return phase + 1


def stage_probeB(arms=(("gateclear", "short"),), arm_frames=4200):
    p, fw = boot()
    g = ensure_mission(p, tries=4, log=log, want_hp_cands=False)
    log("mission gate:", g.get("in_mission"))
    try:
        p.load_state("arena")
        log("loaded savestate `arena`")
    except Exception as e:                     # noqa: BLE001
        log("no `arena` savestate:", e)
        return None
    p.save_state("arena_pristine")             # re-anchor
    reports = {}
    for arm, dm in arms:
        p.load_state("arena_pristine")
        # freeze the JUST-LOADED values immediately: any unticked frame
        # lets the overhead bombing rewrite the pair (144 -> 35)
        session = freeze_now(p, f"probeB_{arm}")
        for _ in range(2):                     # pre-engage WITH tick
            p.core.run_frame()
            session.gs.tick()
        reports[arm] = run_arm(
            p, arm, frames=arm_frames, session=session,
            dismount=(dm == "left"))
        unfreeze(session, f"probeB_{arm}")
    json.dump({"arms": reports,
               "disclosure": "EXPLORATION: hp_pair freeze active in ALL "
                             "arms; one-factor-at-a-time from savestate "
                             "`arena_pristine`",
               "note": "gate open = sustained progress-word gain > 0"},
              open(os.path.join(EVID, "probeB_arms.json"), "w"), indent=1)
    log("probeB complete")
    return reports


# =====================================================================
if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "reach"
    if stage == "reach":
        ok = stage_reach()
        sys.exit(0 if ok else 1)
    elif stage == "probeB":
        stage_probeB()
    else:
        raise SystemExit(f"unknown stage {stage}")
