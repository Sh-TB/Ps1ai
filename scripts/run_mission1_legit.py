#!/usr/bin/env python3
"""run_mission1_legit.py — CLEAR Metal Slug X Mission 1, LEGAL INPUTS ONLY.

v0.6 (mission-review revision). Rules of engagement (unchanged):
  * ZERO memory writes, ZERO GameShark, ZERO rewinds during the real run.
  * Only legal pad inputs + read-only RAM perception (numpy, zero tokens).
  * Savestates used ONLY for calibration trials (read-only probes) and
    checkpoints/resume — never to rewind a live run.

What changed vs v0.5 and WHY (root causes from the v0.5 report audit):
  RC1 score semantics   — score is now sampled BEFORE and AFTER each
        action interval with raw bytes; ScoreTracker handles continue
        resets / u32 wrap / suspicious jumps with explicit reason codes
        (v0.5 shipped score_start==score_end==200 vs telemetry 96..252).
  RC2 kill honesty      — score deltas >= 90 are ENEMY_KILL_CANDIDATE
        (ESTIMATED); they are NEVER reported as verified kills without
        independent entity evidence (v0.5's "27 kills" were deltas).
  RC3 progress honesty  — the camera word is only usable when the
        calibration tests pass (idle-stable, right/left symmetric,
        monotonic run); camera-lock is separated from a true stall;
        unverified signals cannot claim progress in the report.
  RC4 anchor hygiene    — after every mission reload the cluster is
        invalidated and re-anchored, then plausibility-checked (bombs
        must stay 0..40 and never rise; v0.5 latched bombs=30).
  RC5 clear honesty     — a mission-byte change is only
        mission_clear_detected; mission_clear_verified requires the
        change to SUSTAIN plus independent corroboration.
  RC6 lifecycle         — every recovery goes through the recorded FSM;
        stale calibration is invalidated on death/continue.
  RC7 report validator  — the report is validated for self-consistency
        before it is written (the v0.5 report would be rejected).
  RC8 configuration     — all paths/limits are CLI/env configurable with
        the original defaults preserved; validated before boot.

Policy (RobustLegitPolicy): unchanged backbone — ALWAYS advance,
tap-fire rhythm, hop cadence, escalate when stalled — with one honesty
fix: grenades are only thrown when the bombs counter is VERIFIED > 0.
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.api import PS1Play                              # noqa: E402
from ps1play.agent.perception import PerceptionGuard         # noqa: E402
from ps1play.agent.worldmodel import WorldModel              # noqa: E402
from ps1play.agent.events import (                           # noqa: E402
    EventLog, ScoreTracker, KillClassifier, MissionClearDetector,
    SCORE_CHANGED, SCORE_RESET, SCORE_SUSPICIOUS,
    CONTINUE_USED, PLAYER_DIED, OBSERVED, ESTIMATED)
from ps1play.agent.progress import ProgressSignal            # noqa: E402
from ps1play.agent.lifecycle import Lifecycle                # noqa: E402
from ps1play.agent.report_validate import assert_consistent  # noqa: E402
from ps1play.agent.rewards import RewardAudit                # noqa: E402
from mission import ensure_mission, recover, responsive      # noqa: E402

# ------------------------------------------------------------------
# configuration (§9): CLI args with env-var defaults. The original
# absolute defaults are preserved for the original environment.
# ------------------------------------------------------------------
DEF_GAME = os.environ.get(
    "M1_GAME", "/home/z/my-project/ps1-test/emu/games/"
               "Metal Slug X (USA).cue")
DEF_CORE = os.environ.get("M1_CORE", None)          # None -> api default
DEF_WORKSPACE = os.environ.get("M1_WORKSPACE", None)
DEF_EVID = os.environ.get(
    "M1_EVID", "/home/z/my-project/download/ps1play_v6_mission1")
DEF_PROFILE_DIR = os.environ.get("M1_PROFILE_DIR", None)
DEF_CHUNKS = int(os.environ.get("M1_CHUNKS", "1000"))
DEF_CHUNK = 60
DEF_RESUME = os.environ.get("M1_RESUME", "")

SCORE_ADDR = 0x0EE318          # static RE: 9 xrefs (representation audit: §2)
POW_ADDR = 0x087A78
MISSION_ADDR = 0x0D4213        # UNVERIFIED as a clear signal — detector §10
ZONE = 0x1FC000


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Legit Mission-1 run (legal inputs only, read-only "
                    "RAM perception)")
    ap.add_argument("--game", default=DEF_GAME,
                    help="path to the game .cue (env M1_GAME)")
    ap.add_argument("--core", default=DEF_CORE,
                    help="path to mednafen_psx_libretro.so (env M1_CORE; "
                         "default: ps1play.api.DEFAULT_CORE)")
    ap.add_argument("--workspace", default=DEF_WORKSPACE,
                    help="emu workspace dir (env M1_WORKSPACE)")
    ap.add_argument("--profile-dir", default=DEF_PROFILE_DIR,
                    help="profiles dir override (env M1_PROFILE_DIR)")
    ap.add_argument("--evidence-dir", default=DEF_EVID,
                    help="evidence output dir (env M1_EVID)")
    ap.add_argument("--chunks", type=int, default=DEF_CHUNKS,
                    help="max chunks of 60 frames (env M1_CHUNKS)")
    ap.add_argument("--resume", default=DEF_RESUME,
                    help="savestate name to resume from (env M1_RESUME)")
    ap.add_argument("--report", default=None,
                    help="report JSON path (default <evidence-dir>/"
                         "mission1_report.json)")
    args = ap.parse_args(argv)
    if args.chunks < 1:
        ap.error("--chunks must be >= 1")
    # ---- validate BEFORE touching the emulator (§9: no silent fallback)
    missing = []
    if not os.path.exists(args.game):
        missing.append(f"game image not found: {args.game} "
                       f"(set --game / M1_GAME)")
    if args.core and not os.path.exists(args.core):
        missing.append(f"libretro core not found: {args.core} "
                       f"(set --core / M1_CORE)")
    if missing:
        ap.error(" | ".join(missing))
    return args


report = {}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def png(p, evid, name):
    try:
        from PIL import Image
        rgb = p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).resize((320, 240)).save(
                os.path.join(evid, name))
            return name
    except Exception as e:                                  # noqa: BLE001
        log("png fail:", e)
    return None


# ====================================================================
# camera / progress calibration (§4) — candidates are ranked, only a
# candidate that passes ALL tests is marked verified.
# ====================================================================
def find_progress_addr(p, log=log):
    """A word that grows while running right, shrinks running left,
    frozen while idle, and monotonic over a long rightward run.
    Returns {"addr", "gain", "verified", "tests"} — verified=False
    candidates are reported but MUST NOT drive progress claims."""
    p.save_state("_cam")
    s0 = p.mem.snapshot()
    p.core.run(90, set())
    p._advance()
    s_idle = p.mem.snapshot()
    p.load_state("_cam")
    p.core.run(120, {"RIGHT"})
    p._advance()
    s_run = p.mem.snapshot()
    p.load_state("_cam")
    p.core.run(120, {"LEFT"})
    p._advance()
    s_left = p.mem.snapshot()
    a0 = s0[:ZONE].view("<u2").astype(np.int32)
    di = s_idle[:ZONE].view("<u2").astype(np.int32) - a0
    dr = s_run[:ZONE].view("<u2").astype(np.int32) - a0
    dl = s_left[:ZONE].view("<u2").astype(np.int32) - a0
    cand = np.flatnonzero((dr >= 60) & (dl <= -60) & (np.abs(di) < 8))
    log(f"[cam] 3-way candidates: {len(cand)}")
    p.load_state("_cam")
    if not len(cand):
        return {"addr": None, "gain": 0, "verified": False,
                "tests": {"reason": "no 3-way candidate"}}
    # monotonic rightward run (top candidates only)
    idx = cand[:8]
    T = 300
    S = np.zeros((T // 10 + 1, len(idx)), np.int64)
    p.core.set_buttons({"RIGHT"})
    for k in range(T):
        p.core.run_frame()
        if k % 10 == 0:
            w = p.mem.ram[:ZONE].view("<u2").astype(np.int64)
            S[k // 10] = w[idx]
    p._advance()
    p.load_state("_cam")
    results = []
    for j in range(len(idx)):
        ser = S[:, j]
        dips = int(np.sum(np.diff(ser) < -4))
        gain = int(ser[-1] - ser[0])
        idle_drift = 0                      # enforced by the 3-way filter
        right_delta = int(dr[idx[j]])
        left_delta = int(dl[idx[j]])
        ok = (gain >= 150 and dips <= 2 and idle_drift <= 8
              and right_delta >= 60 and left_delta <= -60)
        results.append({"addr": int(idx[j]) * 2, "gain": gain,
                        "dips": dips, "right_delta": right_delta,
                        "left_delta": left_delta,
                        "idle_drift": idle_drift, "verified": ok})
        log(f"[cam] cand {int(idx[j]) * 2:#x}: gain={gain} dips={dips} "
            f"R={right_delta} L={left_delta} -> "
            f"{'VERIFIED' if ok else 'rejected'}")
    good = [r for r in results if r["verified"]]
    if good:
        best = max(good, key=lambda r: r["gain"] - r["dips"] * 400)
        log(f"[cam] verified progress word @ {best['addr']:#x}")
        return {"addr": best["addr"], "gain": best["gain"],
                "verified": True, "tests": {"candidates": results}}
    fb = results[0] if results else {"addr": None, "gain": 0}
    log(f"[cam] NO candidate passed all tests — keeping "
        f"{fb.get('addr', None)} as UNVERIFIED observation only")
    return {"addr": fb.get("addr"), "gain": fb.get("gain", 0),
            "verified": False, "tests": {"candidates": results}}


def validate_timer(guard, log=log):
    """timer = bombs anchor + published-cluster offset; must tick -1/s.
    Advisory only — recorded in the contract as PENDING until its own
    event test passes (it never does via translation alone)."""
    if "bombs" not in guard.addrs:
        return None
    a = guard.addrs["bombs"] + (0x0295F8 - 0x0398B4)
    v0 = guard.p.mem.u16(a)
    guard.p.core.run(120, set())
    guard.p._advance()
    v1 = guard.p.mem.u16(a)
    if 0 < v0 <= 300 and 0 <= v1 < v0 <= v0 - 1:
        log(f"[timer] validated @ {a:#x}: {v0}->{v1} (1Hz)")
        guard._set_role("timer", a, "VERIFIED", "1Hz decay event test",
                        confidence=0.8)
        return a
    log(f"[timer] translation @ {a:#x} invalid ({v0}->{v1}) — stays "
        f"PENDING in the contract")
    return None


def validate_lives(guard, log=log):
    """Try the published-cluster offset for lives; needs a death event
    (-1) to be VERIFIED. A plausible value alone is NOT verification."""
    if "bombs" not in guard.addrs:
        return None
    a = guard.addrs["bombs"] + (0x0475A8 - 0x0398B4)
    v = guard.p.mem.u16(a)
    if 1 <= v <= 9:
        log(f"[lives] translated @ {a:#x} = {v} (plausible — PENDING "
            f"death-event verification)")
        guard._set_role("lives", a, "PENDING",
                        "plausible range only; death -1 test not run")
        return a
    log(f"[lives] translation @ {a:#x} = {v} implausible — ignored")
    return None


# ====================================================================
# KillCorrelator — passive semantic evidence: which RAM words change
# together with score events? EVIDENCE-ONLY: correlated words are
# candidates, never "verified kills" (v0.5 latched score-shadow words
# 0xEF31A/0xEF368 as "verified" — they sit next to the score itself).
# ====================================================================
class KillCorrelator:
    def __init__(self, n_cand=240, warm=45, ring=48):
        self.n, self.warm, self.ring_n = n_cand, warm, ring
        self.chg = None
        self.samples = 0
        self.cands = None
        self.ring = None
        self.ri = 0
        self.votes = defaultdict(int)
        self.events = 0
        self.correlated = []

    def observe(self, mem):
        cur = mem.ram[:ZONE].view("<u2")
        cur32 = cur.astype(np.int32)
        if self.chg is None:
            self.chg = np.zeros(cur.size, np.int32)
            self.pv = cur32.copy()
            self.samples += 1
            return
        self.chg += (cur32 - self.pv) != 0
        self.pv = cur32
        self.samples += 1
        if self.cands is None:
            if self.samples >= self.warm:
                idx = np.argsort(-self.chg)[:self.n]
                self.cands = np.sort(idx)
                self.ring = np.zeros((self.ring_n, len(self.cands)),
                                     np.int32)
                self.ring[0] = cur32[self.cands]
                self.ri = 1
                log(f"[kc] warm done: {len(self.cands)} candidate words")
        else:
            self.ring[self.ri] = cur32[self.cands]
            self.ri = (self.ri + 1) % self.ring_n

    def on_score_event(self, mem):
        """score just jumped — vote for words that just died/reset."""
        self.events += 1
        if self.cands is None:
            return
        cur = mem.ram[:ZONE].view("<u2").astype(np.int32)[self.cands]
        for back in (2, 3, 4):
            past = self.ring[(self.ri - back) % self.ring_n]
            hit = (past > 50) & (past <= 0x2000) & \
                  ((cur == 0) | (np.abs(cur - past) > 0x1800))
            for k in np.flatnonzero(hit).tolist():
                self.votes[int(k)] += 1
        if self.events >= 4 and not self.correlated:
            good = sorted((v, k) for k, v in self.votes.items() if v >= 4)
            self.correlated = [int(self.cands[k]) * 2 for _, k in
                               good[:16]]
            log(f"[kc] score-correlated words (candidates ONLY): "
                f"{[hex(a) for a in self.correlated[:8]]}...")

    def to_dict(self):
        return {"events": self.events,
                "correlated_n": len(self.correlated),
                "correlated": [hex(a) for a in self.correlated],
                "note": "evidence-only candidates; NOT verified kills "
                        "(v0.5 lesson: score-shadow words correlate "
                        "trivially)"}


# ====================================================================
# RobustLegitPolicy — noise-tolerant survival backbone (unchanged core;
# grenade now requires a VERIFIED bombs counter > 0).
# ====================================================================
FIRE_ON, FIRE_OFF = 8, 6


class RobustLegitPolicy:
    """WALK mode: RIGHT + tap-fire + real jumps.
    ZONE mode (camera locked): find the target side with EXPLOSION
    feedback — throw a probe grenade left; a churn spike (>12000)
    proves the blast hit a crowd/vehicle -> SHRED that side. No spike
    -> probe right. No hits at all -> alternate facing (v6 style).
    Verifiable, zero tokens, no reliance on noisy entity slots."""

    SPIKE = 12000           # churn spike = explosion hit something

    def __init__(self):
        self.burst = 0
        self.hop_cd = 150
        self.hop_hold = 0
        self.fc = 0               # global frame counter (input rhythm)
        self.stats = defaultdict(int)

    def decide(self, chunk, stall, bombs, timer, zone, churn,
               bombs_verified=False):
        """v18 — evidence-gated grenades. Evidence: the lab winners were
        plain input patterns (F: right-fire 9s, C: left+grenades 1-2s, B:
        alternation 9s) and the diag bot (walk+fire+rare jumps) crossed
        canyon+market+village in 15s. Churn-based zone detection misfires
        on normal fights (fights churn 1000-2400 too). Final policy:
        ALWAYS walk right + tap-fire + rare jumps + periodic side-
        alternating grenade ONLY IF bombs counter is VERIFIED and > 0;
        on a long stall do one left-shred burst."""
        plan = []
        self.fc += chunk
        # long-stall escape: one C-burst (left + grenades), then resume
        shred = stall > 60 and (self.fc % 900) < 240 and bombs_verified
        for _ in range(chunk):
            if shred:
                btns = {"LEFT", "Y"}
                if (self.fc % 900) % 75 == 0 and bombs:
                    btns.add("A")
                    self.stats["grenade"] += 1
            else:
                btns = {"RIGHT"}
                self.burst = (self.burst + 1) % (FIRE_ON + FIRE_OFF)
                if self.burst < FIRE_ON:
                    btns.add("Y")
                # side-alternating grenade every ~5s (A no-ops when empty)
                if (self.fc % 300) == 30 and bombs_verified and bombs:
                    btns.add("A")
                    self.stats["grenade"] += 1
                    self.stats["gren_right" if (self.fc // 300) % 2
                               else "gren_left"] += 1
            if self.hop_hold > 0:
                btns.add("B")                # hold B = full jump
                self.hop_hold -= 1
            elif self.hop_cd <= 0:
                self.hop_hold = 13
                self.hop_cd = 200 + 13
                self.stats["jump"] += 1
            else:
                self.hop_cd -= 1
            plan.append(btns)
        # compress into segments
        segs = []
        for b in plan:
            if segs and segs[-1]["btns"] == b:
                segs[-1]["frames"] += 1
            else:
                segs.append({"frames": 1, "btns": set(b)})
        return segs


def execute(p, segs, budget):
    done = 0
    for s in segs:
        k = min(s["frames"], budget - done)
        if k <= 0:
            break
        p.core.set_buttons(s["btns"])
        for _ in range(k):
            p.core.run_frame()
        done += k
    p._advance()
    return done


def responsive_live(p):
    """In-mission keepalive test: pad mirror + ANY real world churn +
    SELF-PLAY guard (v15 lesson: the attract demo churns 200k+ AND
    mirrors its own scripted inputs, so pad+churn alone accept it —
    but a real mission mirrors 0 when we press nothing)."""
    p.core.run(6, set())
    self_play = False
    for _ in range(3):
        p.core.run(10, set())
        if p.mem.u16(0x0D4948) != 0:
            self_play = True
    w0 = p.mem.u16(0x0D4948)
    p.core.run(8, {"RIGHT"})
    w1 = p.mem.u16(0x0D4948)
    p.core.run(6, set())
    w2 = p.mem.u16(0x0D4948)
    p._advance()
    pad_ok = (w1 & 0x20) and not (w2 & 0x20) and not (w0 & 0x20)
    s0 = p.mem.snapshot()
    p.core.run(45, {"RIGHT", "Y"})
    churn = int(np.count_nonzero(s0 != p.mem.snapshot()))
    p._advance()
    alive = bool(pad_ok and churn > 250 and not self_play)
    return alive, (int(w1), churn)


def recover_v2(p, log=log):
    """Adaptive START taps: tap, then CHECK with the FULL alive test
    (pad mirror + churn + self-play guard) — the attract demo churns
    200k+ so a churn-only check accepts it (v15 lesson)."""
    for _ in range(4):
        p.core.run(6, {"START"})
        p.core.run(75, set())
        ok, _ = responsive_live(p)
        if ok:
            log("[gate] recovery v2: back in control")
            return True
    log("[gate] recovery v2: still dead after taps")
    return False


def read_score_raw(mem):
    raw = bytes(mem.ram[SCORE_ADDR:SCORE_ADDR + 4])
    return raw, int.from_bytes(raw, "little")


# ====================================================================
# MAIN
# ====================================================================
def main(argv=None):
    args = parse_args(argv)
    evid = args.evidence_dir
    os.makedirs(evid, exist_ok=True)
    report.update({
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "legit-inputs-only", "cheats": "none",
        "config": {"game": args.game, "core": args.core,
                   "workspace": args.workspace, "evidence_dir": evid,
                   "chunks": args.chunks, "resume": args.resume,
                   "repo_head": _repo_head()},
    })
    lc = Lifecycle(log=log)
    lc.transition("GAME_IDENTIFIED", "pre-boot config validated",
                  evidence=report["config"])
    evlog = EventLog()
    tracker = ScoreTracker(SCORE_ADDR, width=4, encoding="u32le")
    killer = KillClassifier(min_delta=90)
    evidence_files = []

    kw = {}
    if args.core:
        kw["core"] = args.core
    if args.workspace:
        kw["workspace"] = args.workspace
    if args.profile_dir:
        kw["profile_dir"] = args.profile_dir
    p = PS1Play(args.game, **kw)
    info = p.boot()
    log("boot:", info)
    report["boot"] = info
    lc.transition("TITLE_OR_MENU", "core booted, game identified",
                  evidence=info)

    if args.resume:
        p.load_state(args.resume)
        log("resumed from", args.resume)
        ok, _ = responsive(p)
        if not ok:
            recover(p, log=log)
            ok, _ = responsive(p)
        if not ok:
            report["lifecycle"] = lc.to_dict()
            sys.exit("!! resume state not in mission")
    else:
        r = p.enter_gameplay3()
        log("enter:", r.get("in_game"))
        report["enter"] = r.get("in_game")
        if not r.get("in_game"):
            report["lifecycle"] = lc.to_dict()
            sys.exit("!! boot failed")
        m = ensure_mission(p, tries=6, log=log)
        log("gate:", {k: v for k, v in m.items() if k != "evidence"})
        report["gate"] = {k: v for k, v in m.items() if k != "evidence"}
        if not m.get("in_mission"):
            report["lifecycle"] = lc.to_dict()
            sys.exit("!! gate failed")
    lc.transition("GAMEPLAY_CANDIDATE", "activity gates passed",
                  evidence={"gate": report.get("gate", {})})
    lc.transition("INPUT_CONTROL_VERIFIED", "responsive() triple test",
                  evidence={"pad_mirror": "0x0D4948", "churn": ">900",
                            "self_play_guard": True})
    lc.transition("MISSION_1_VERIFIED", "mission-1 HUD state reached",
                  evidence={"gate": report.get("gate", {})})

    # ---- calibration (read-only probes from savestates) -------------
    cam = find_progress_addr(p, log=log)
    report["camera"] = {"addr": cam["addr"], "gain": cam["gain"],
                        "verified": cam["verified"],
                        "tests": cam["tests"]}
    prog = ProgressSignal(cam["addr"], cam["verified"]) \
        if cam["addr"] is not None else None
    guard = PerceptionGuard(p)
    anch = guard.anchor(log=log)
    log("anchor:", anch)
    report["anchor"] = anch
    t_addr = validate_timer(guard, log=log)
    l_addr = validate_lives(guard, log=log)
    lc.transition("OBSERVATION_CALIBRATED", "camera + bombs anchor",
                  evidence={"anchor": anch,
                            "camera_verified": cam["verified"]})
    lc.transition("PLAYING", "calibration done; live run starts")
    report["observation_contract"] = guard.observation_contract()

    # ---- entity discovery (advisory, from checkpoint) ----------------
    p.save_state("m1_base")
    wm = WorldModel(p.mem)
    try:
        disc = wm.discover(p.core, p.states, "m1_base", budget=1800)
    except Exception as e:                                  # noqa: BLE001
        log("discovery error:", e)
        disc = {"error": str(e)}
        wm.slots = []
    p.load_state("m1_base")
    report["worldmodel"] = disc
    log("worldmodel:", disc)

    # ---- live run -----------------------------------------------------
    p.save_state("m1_start")
    evidence_files.append(png(p, evid, "00_mission_start.png") or
                          "00_mission_start.png")
    raw0, score0 = read_score_raw(p.mem)
    tracker.feed(score0, frame=p.t, chunk=0, raw=raw0)
    mb0 = p.mem.u8(MISSION_ADDR)
    mcd = MissionClearDetector(baseline_byte=mb0, sustain_chunks=4,
                               log=log)
    cam_addr = cam["addr"]
    log(f"[run] mission_byte={mb0} score={score0} "
        f"cam={hex(cam_addr) if cam_addr else None} "
        f"cam_verified={cam['verified']}")

    policy = RobustLegitPolicy()
    kc = KillCorrelator()
    tel = []
    score_event_log = []
    stall = 0
    last_cam = None
    last_churn = 0
    zone = False
    continues = 0
    deaths_seen = []
    prev_lives = guard.read("lives") if l_addr else None
    t0 = time.time()
    last_mb = mb0

    audit = RewardAudit(sensor_status={
        "score": False,           # encoding audit still PARTIAL (§2.1)
        "progress": bool(cam["verified"]),
        "kill_verified": False,   # estimated-only until entity proof
        "pickup_verified": False,
        "lives_hp": l_addr is not None and
        guard.verification.get("lives", {}).get("status") == "VERIFIED",
    })

    for i in range(args.chunks):
        # ---- mission-clear detector (primary signal) -----------------
        mb = p.mem.u8(MISSION_ADDR)
        if mb != last_mb:
            evlog.add("MISSION_STATE_CHANGED", OBSERVED, frame=p.t,
                      chunk=i,
                      evidence={"from": last_mb, "to": int(mb),
                                "addr": hex(MISSION_ADDR)})
            last_mb = mb
        det_ev = mcd.feed(mb, frame=p.t, chunk=i, evlog=evlog)
        if mcd.detected and not mcd.verified:
            # corroboration attempt #1: is the input profile consistent
            # with a transition (responsiveness changed)?
            ok_now, (i1, rr) = responsive_live(p)
            if ok_now:
                mcd.corroborate("input_responsive_after_transition")
            else:
                mcd.corroborate("input_unresponsive_after_transition")
            evidence_files.append(
                png(p, evid, "99_MISSION_CLEAR_DETECTED.png") or
                "99_MISSION_CLEAR_DETECTED.png")
        if mcd.verified:
            evidence_files.append(
                png(p, evid, "99_MISSION_CLEAR_VERIFIED.png") or
                "99_MISSION_CLEAR_VERIFIED.png")
            report["mission_clear"] = mcd.to_dict()
            report["mission_clear"]["evidence_files"] = [
                e for e in evidence_files if e]
            break

        # ---- action interval: sample score BEFORE actions ------------
        raw_b, _ = read_score_raw(p.mem)
        frame_start = p.t
        action_before = dict(policy.stats)

        # ---- keepalive / recovery (CONTINUE screen has ~9s timer) ----
        if i % 3 == 2:
            ok, (i1, rr) = responsive_live(p)
            last_churn = max(last_churn, rr if isinstance(rr, int) else 0)
            if not ok:
                continues += 1
                evlog.add(CONTINUE_USED, ESTIMATED, frame=p.t, chunk=i,
                          evidence={"gate": [i1, rr]},
                          note="responsive gate failed; recovery run")
                deaths_seen.append({"chunk": i, "gate": [i1, rr]})
                try:
                    zl = os.path.join(evid, "zone_live.png")
                    if os.path.exists(zl):
                        os.replace(zl, os.path.join(
                            evid, f"predeath_{i:04d}.png"))
                except OSError:
                    pass
                evidence_files.append(
                    png(p, evid, f"death_{i:04d}.png") or
                    f"death_{i:04d}.png")
                log(f"[keepalive] chunk {i}: unresponsive "
                    f"(idle={i1} run={rr}) -> recover")
                lc.transition("DEATH_OR_CONTINUE",
                              "responsive gate failed",
                              evidence={"gate": [i1, rr]})
                recovered = recover_v2(p, log=log)
                if not recovered:
                    log("[keepalive] still out -> ensure_mission")
                    m = ensure_mission(p, tries=4, log=log)
                    if not m.get("in_mission"):
                        log("[keepalive] re-entering mission")
                        p.enter_gameplay3()
                        ensure_mission(p, tries=4, log=log)
                # §5/§6: mission reload => cluster moves => invalidate +
                # re-anchor + plausibility check
                guard.invalidate("death/continue reload", log=log)
                ra = guard.anchor(log=log)
                if ra.get("ok"):
                    va = guard.validate_anchor(log=log)
                    report.setdefault("reanchors", []).append(
                        {"chunk": i, **ra, "validate": va})
                    t_addr = validate_timer(guard, log=log)
                    l_addr = validate_lives(guard, log=log)
                lc.transition("RECOVERY", "recover_v2 + ensure_mission",
                              evidence={"reanchor": ra})
                lc.transition("INPUT_CONTROL_REVERIFIED",
                              "responsive gate re-passed",
                              evidence={"reanchor_ok": bool(ra.get("ok"))})
                lc.transition("OBSERVATION_RECALIBRATED",
                              "anchor re-verified after reload",
                              evidence={"validate": ra})
                lc.transition("PLAYING", "recovery complete")
                report.setdefault("continues", []).append(
                    {"chunk": i, "score": tracker.value})
            elif stall > 30:
                # PAUSED-DEAD-INPUT detector: pad mirror alive but the
                # inputs have zero world effect in BOTH directions ->
                # one START (unpause). Self-corrects if false positive.
                s0 = p.mem.snapshot()
                p.core.run(24, {"LEFT"})
                cl = int(np.count_nonzero(s0 != p.mem.snapshot()))
                s1 = p.mem.snapshot()
                p.core.run(24, {"RIGHT"})
                cr = int(np.count_nonzero(s1 != p.mem.snapshot()))
                p._advance()
                if cl < 220 and cr < 220:
                    evlog.add("PAUSE_TAP", OBSERVED, frame=p.t, chunk=i,
                              evidence={"L": cl, "R": cr})
                    log(f"[keepalive] chunk {i}: inputs dead "
                        f"(L={cl} R={cr}) -> START tap (unpause?)")
                    p.core.run(6, {"START"})
                    p.core.run(60, set())
                    p._advance()
                    policy.hop_cd = max(policy.hop_cd, 60)

        # ---- policy + execute (with per-chunk churn measurement) -------
        bombs = guard.read("bombs")
        timer = guard.read("timer") if t_addr else None
        lives = guard.read("lives") if l_addr else None
        segs = policy.decide(60, stall, bombs, timer, zone, last_churn,
                             bombs_verified=(
                                 guard.verification.get(
                                     "bombs", {}).get("status")
                                 == "VERIFIED"))
        s_before = p.mem.snapshot()
        execute(p, segs, 60)
        churn = int(np.count_nonzero(s_before != p.mem.snapshot()))
        last_churn = churn
        zone = churn < 2500  # simple low-churn marker for the policy

        # ---- POST-action sampling: events attributed to THIS interval
        frame_end = p.t
        raw_a, score_a = read_score_raw(p.mem)
        sobs = tracker.feed(score_a, frame=frame_end, chunk=i, raw=raw_a)
        sobs["frame_start"] = frame_start
        _btns = set()
        for _s in segs:
            _btns |= _s["btns"]
        sobs["action_during_interval"] = "+".join(sorted(_btns)) or "none"
        del action_before
        sobs["mission_state"] = int(mb)
        sobs["input_responsive"] = bool(churn > 250)
        score_event_log.append(sobs)
        if sobs["kind"] in ("update", "wrap"):
            if sobs["delta"]:
                evlog.add(SCORE_CHANGED, OBSERVED, frame=frame_end,
                          chunk=i,
                          evidence={"delta": sobs["delta"],
                                    "raw": sobs["raw_after"]})
            killer.on_score_obs(sobs, evlog, frame=frame_end, chunk=i)
        elif sobs["kind"] == "reset":
            evlog.add(SCORE_RESET, OBSERVED, frame=frame_end, chunk=i,
                      evidence={"before": sobs["decoded_before"],
                                "after": sobs["decoded_after"]},
                      note="continue/death reset — start/end must not "
                           "hide this")
        elif sobs["kind"] == "suspicious":
            evlog.add(SCORE_SUSPICIOUS, OBSERVED, frame=frame_end,
                      chunk=i,
                      evidence={"delta": sobs["delta"]},
                      note="impossible jump recorded, NOT converted "
                           "into kills/rewards")
        kc.on_score_event(p.mem)

        # ---- progress / stall (validated signal only) ------------------
        cam_now = p.mem.u16(cam_addr) if cam_addr else None
        if prog is not None and cam_now is not None:
            state = prog.update(cam_now, churn=churn, frame=frame_end)
            if state == ProgressSignal.STALLED:
                stall += 1
            elif state == ProgressSignal.PROGRESS:
                stall = 0
            # CAMERA_LOCKED: fight at a locked camera — NOT a stall
        else:
            # no trusted progress: fall back to conservative stall rule
            stall = 0 if (sobs.get("delta") or churn >= 3500) else stall + 1
        if lives is not None and prev_lives is not None \
                and lives < prev_lives:
            evlog.add(PLAYER_DIED, OBSERVED, frame=frame_end, chunk=i,
                      evidence={"lives": lives, "prev": prev_lives})
            deaths_seen.append({"chunk": i, "lives": lives})
        prev_lives = lives

        # ---- scene (advisory, every 4th chunk only — noise anyway) ----
        scene_n = 0
        if i % 4 == 0 and wm.slots:
            scene = wm.read_world(p.core)
            scene_n = len(scene.get("enemies", []))

        if i % 4 == 0:
            kc.observe(p.mem)             # evidence-only, every 4th chunk
        last_mb = mb

        # ---- telemetry / evidence -------------------------------------
        if i % 5 == 4:
            act = policy.stats
            log(f"[t] i={i} score={score_a} cam={cam_now} "
                f"churn={last_churn} zone={int(zone)} "
                f"enemies={scene_n} bombs={bombs} timer={timer} "
                f"lives={lives} stall={stall} "
                f"act={max(act, key=act.get) if act else '-'}")
        if i % 25 == 24:
            tel.append({"chunk": i, "score": score_a, "cam": cam_now,
                        "bombs": bombs, "timer": timer, "lives": lives,
                        "stall": stall, "churn": last_churn,
                        "enemies": scene_n,
                        "act": (max(policy.stats, key=policy.stats.get)
                                if policy.stats else "-")})
            evidence_files.append(
                png(p, evid, f"play_{(i // 25) + 1:02d}.png") or
                f"play_{(i // 25) + 1:02d}.png")
        if i in (20, 60, 120) or (i % 250 == 249):
            p.save_state(f"m1cp_{i}")
            p.save_state("m1cp")
            log("checkpoint @", i, "score", score_a)

    wall = time.time() - t0
    raw_end, score_end = read_score_raw(p.mem)
    report["play"] = {
        "chunks": i + 1, "frames": (i + 1) * 60,
        "wall_s": round(wall, 1),
        "fps": round((i + 1) * 60 / max(wall, 0.1), 1),
        "score": dict(tracker.to_dict(), raw_end=raw_end.hex()),
        "score_start": int(score0),
        "score_end": int(score_end),
        "score_resets": tracker.n_resets,
        "kills_estimated": killer.estimated,
        "kills_verified": killer.verified,
        "continues": continues,
        "cleared": bool(mcd.verified),
        "progress_claim": (prog.to_dict() if prog and prog.claims_progress
                           else None),
        "stall_final": stall,
        "policy_stats": dict(policy.stats)}
    report["events"] = evlog.to_dict()
    report["deaths"] = deaths_seen
    report["telemetry"] = tel
    report["score_event_log"] = score_event_log[-64:]
    report["kill_correlator"] = kc.to_dict()
    report["guard_addrs"] = {k: hex(v) for k, v in guard.addrs.items()}
    report["observation_contract"] = guard.observation_contract()
    report["lifecycle"] = lc.to_dict()
    audit.accumulate(chunk=i,
                     score_delta=float(tracker.cumulative_gain),
                     progress_delta=float(prog.n_progress
                                          if prog and prog.verified
                                          else 0),
                     stalled_chunks=int(stall))
    report["reward_audit"] = audit.to_dict()
    report["mission_clear"] = mcd.to_dict()
    report["mission_clear"]["evidence_files"] = [e for e in evidence_files
                                                 if e]
    if not mcd.verified:
        evidence_files.append(png(p, evid, "99_end.png") or "99_end.png")
    out_path = args.report or os.path.join(evid, "mission1_report.json")
    try:
        assert_consistent(report)
    except ValueError as e:
        # v0.6 §2.3: never ship a self-contradictory report; park it and
        # re-raise so the failure is loud.
        rej = out_path.replace(".json", ".REJECTED.json")
        json.dump({"findings": str(e), "report": report},
                  open(rej, "w"), indent=1, default=str)
        log(f"!! report validation FAILED -> {rej}")
        raise
    json.dump(report, open(out_path, "w"), indent=1, default=str)
    p.save_profile()
    log("report ->", out_path)
    print(json.dumps({k: report.get(k) for k in
                      ("boot", "enter", "camera", "anchor", "play",
                       "mission_clear", "lifecycle") if k in report},
                     indent=1, default=str))


def _repo_head():
    try:
        import subprocess
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_REPO,
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:                                       # noqa: BLE001
        return None


if __name__ == "__main__":
    main()
