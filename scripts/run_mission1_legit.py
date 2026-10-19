#!/usr/bin/env python3
"""run_mission1_legit.py — CLEAR Metal Slug X Mission 1, LEGAL INPUTS ONLY.

Rules of engagement (user mandate):
  * ZERO memory writes, ZERO GameShark, ZERO rewinds during the real run.
  * Only legal pad inputs + read-only RAM perception (numpy, zero tokens).
  * Savestates used ONLY for calibration trials (read-only probes) and
    checkpoints/resume — never to rewind a live run.

Why a new policy: last session's entity slots were noise-dominated
(20-27 phantom "enemies" every frame -> policy never advanced,
advance=0 in 27000 frames). This run uses a noise-TOLERANT backbone
(humans clear MS1 the same way): ALWAYS advance, tap-fire rhythm,
hop cadence, escalate when stalled. Verified telemetry drives progress
and recovery; entity slots and kill-correlation are advisory evidence.

Perception (all read-only, zero tokens):
  * score u32 @0x0EE318 (static RE-verified), POW @0x087A78,
    mission byte @0x0D4213
  * bombs anchor via PerceptionGuard (live grenade-diff scan)
  * timer via cluster translation, validated 1 Hz decay (advisory)
  * camera/progress word found live: idle/right/left triple-diff +
    monotonic rightward-run test
  * WorldModel entity discovery (advisory only, from checkpoint)
  * KillCorrelator: passive RAM words correlated with score+100 events
    -> candidate VERIFIED enemy slots (semantic evidence)

Policy (RobustLegitPolicy):
  * NEVER idle: RIGHT always held; fire 9f on / 5f off (pistol tap rate)
  * hop cadence 75f (45f when bulldozing) — dodges grenades/shells/corpses
  * threat (persisted fast mover) -> immediate hop
  * stall >= 50 chunks -> bulldoze; >= 90 chunks -> grenade spam if armed
  * death: no action (auto respawn); game over: recover() -> continue
    (arcade continue = a legit game feature)
  * mission byte change -> MISSION 1 CLEAR -> stop, report, celebrate
"""
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np

sys.path.insert(0, "/home/z/my-project")
sys.path.insert(0, "/home/z/my-project/scripts")

from ps1play.api import PS1Play                              # noqa: E402
from ps1play.agent.perception import PerceptionGuard         # noqa: E402
from ps1play.agent.worldmodel import WorldModel              # noqa: E402
from mission import ensure_mission, recover, responsive      # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
EVID = "/home/z/my-project/download/ps1play_v4_mission1"
OUT = os.path.join(EVID, "mission1_report.json")
os.makedirs(EVID, exist_ok=True)

SCORE_ADDR = 0x0EE318
POW_ADDR = 0x087A78
MISSION_ADDR = 0x0D4213
ZONE = 0x1FC000

MAX_CHUNKS = int(os.environ.get("M1_CHUNKS", "1000"))
CHUNK = 60
RESUME = os.environ.get("M1_RESUME", "")

report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
          "mode": "legit-inputs-only", "cheats": "none"}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def png(p, name):
    try:
        from PIL import Image
        rgb = p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).resize((320, 240)).save(
                os.path.join(EVID, name))
    except Exception as e:                                  # noqa: BLE001
        log("png fail:", e)


# ====================================================================
# camera / progress word (read-only live calibration)
# ====================================================================
def find_progress_addr(p, log=log):
    """A word that grows while running right, shrinks running left,
    frozen while idle, and monotonic over a long rightward run.
    That is the camera (or player world-x) — the progress meter."""
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
        return None
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
    best = None
    for j in range(len(idx)):
        ser = S[:, j]
        dips = int(np.sum(np.diff(ser) < -4))
        gain = int(ser[-1] - ser[0])
        log(f"[cam] cand {int(idx[j]) * 2:#x}: gain={gain} dips={dips}")
        if gain >= 150 and dips <= 2:
            score = gain - dips * 400
            if best is None or score > best[0]:
                best = (score, int(idx[j]) * 2, gain, dips)
    if best:
        log(f"[cam] verified progress word @ {best[1]:#x} "
            f"(gain={best[2]}, dips={best[3]})")
        return {"addr": best[1], "gain": best[2], "verified": True}
    a = int(cand[0]) * 2
    log(f"[cam] fallback (unverified-monotonic) @ {a:#x}")
    return {"addr": a, "gain": int(dr[cand[0]]), "verified": False}


def validate_timer(guard, log=log):
    """timer = bombs anchor + published-cluster offset; must tick -1/s."""
    if "bombs" not in guard.addrs:
        return None
    a = guard.addrs["bombs"] + (0x0295F8 - 0x0398B4)
    v0 = guard.p.mem.u16(a)
    guard.p.core.run(120, set())
    guard.p._advance()
    v1 = guard.p.mem.u16(a)
    if 0 < v0 <= 300 and 0 <= v1 < v0 <= v0 - 1:
        log(f"[timer] validated @ {a:#x}: {v0}->{v1} (1Hz)")
        guard.addrs["timer"] = a
        return a
    log(f"[timer] translation @ {a:#x} invalid ({v0}->{v1}) — ignored")
    return None


def validate_lives(guard, log=log):
    """Try the published-cluster offset for lives; advisory only."""
    if "bombs" not in guard.addrs:
        return None
    a = guard.addrs["bombs"] + (0x0475A8 - 0x0398B4)
    v = guard.p.mem.u16(a)
    if 1 <= v <= 9:
        log(f"[lives] translated @ {a:#x} = {v} (plausible, advisory)")
        guard.addrs["lives"] = a
        return a
    log(f"[lives] translation @ {a:#x} = {v} implausible — ignored")
    return None


# ====================================================================
# KillCorrelator — passive semantic evidence: which RAM words die with
# score+100 events? (read-only, runs alongside the real game)
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
        self.verified = []

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
        if self.events >= 4 and not self.verified:
            good = sorted((v, k) for k, v in self.votes.items() if v >= 4)
            self.verified = [int(self.cands[k]) * 2 for _, k in good[:16]]
            log(f"[kc] verified kill-correlated words: "
                f"{[hex(a) for a in self.verified[:8]]}...")

    def to_dict(self):
        return {"events": self.events, "verified_n": len(self.verified),
                "verified": [hex(a) for a in self.verified]}


# ====================================================================
# RobustLegitPolicy v2 — noise-tolerant survival backbone.
# LESSON from run v1: reacting to noisy 'bullet' slots caused PERPETUAL
# hopping -> bot landed on soldiers -> death loop. v2: NEVER react to
# unverified scene noise. Human opening strategy: walk + tap-fire,
# occasional hop, grenades only when provably stuck.
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

    def decide(self, chunk, stall, bombs, timer, zone, churn):
        """v17 — ZONE MODE DELETED. Evidence: the lab winners were plain
        input patterns (F: right-fire 9s, C: left+grenades 1-2s, B:
        alternation 9s) and the diag bot (walk+fire+rare jumps) crossed
        canyon+market+village in 15s. Churn-based zone detection misfires
        on normal fights (fights churn 1000-2400 too). Final policy:
        ALWAYS walk right + tap-fire + rare jumps + periodic side-
        alternating grenade; on a long stall do one left-shred burst."""
        plan = []
        self.fc += chunk
        # long-stall escape: one C-burst (left + grenades), then resume
        shred = stall > 60 and (self.fc % 900) < 240
        for _ in range(chunk):
            if shred:
                btns = {"LEFT", "Y"}
                if (self.fc % 900) % 75 == 0:
                    btns.add("A")
                    self.stats["grenade"] += 1
            else:
                btns = {"RIGHT"}
                self.burst = (self.burst + 1) % (FIRE_ON + FIRE_OFF)
                if self.burst < FIRE_ON:
                    btns.add("Y")
                # side-alternating grenade every ~5s (A no-ops when empty)
                if (self.fc % 300) == 30:
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
            return
    log("[gate] recovery v2: still dead after taps")


# ====================================================================
# MAIN
# ====================================================================
def main():
    p = PS1Play(GAME)
    info = p.boot()
    log("boot:", info)
    report["boot"] = info

    if RESUME:
        p.load_state(RESUME)
        log("resumed from", RESUME)
        ok, _ = responsive(p)
        if not ok:
            recover(p, log=log)
            ok, _ = responsive(p)
        if not ok:
            sys.exit("!! resume state not in mission")
    else:
        r = p.enter_gameplay3()
        log("enter:", r.get("in_game"))
        report["enter"] = r.get("in_game")
        if not r.get("in_game"):
            sys.exit("!! boot failed")
        m = ensure_mission(p, tries=6, log=log)
        log("gate:", {k: v for k, v in m.items() if k != "evidence"})
        report["gate"] = {k: v for k, v in m.items() if k != "evidence"}
        if not m.get("in_mission"):
            sys.exit("!! gate failed")

    # ---- calibration (read-only probes from savestates) -------------
    cam = find_progress_addr(p)
    report["camera"] = cam
    guard = PerceptionGuard(p)
    anch = guard.anchor(log=log)
    log("anchor:", anch)
    report["anchor"] = anch
    t_addr = validate_timer(guard)
    l_addr = validate_lives(guard)

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
    png(p, "00_mission_start.png")
    mb0 = p.mem.u8(MISSION_ADDR)
    cam_addr = cam["addr"] if cam else None
    score0 = guard.score()
    log(f"[run] mission_byte={mb0} score={score0} "
        f"cam={hex(cam_addr) if cam_addr else None}")

    policy = RobustLegitPolicy()
    kc = KillCorrelator()
    evc = defaultdict(int)
    tel = []
    stall = 0
    last_score, last_cam = score0, None
    last_churn = 0
    low_streak = 0
    zone = False
    continues = 0
    kills = 0
    deaths_seen = []
    prev_lives = guard.read("lives") if l_addr else None
    t0 = time.time()
    cleared = False

    for i in range(MAX_CHUNKS):
        score = guard.score()
        cam_now = p.mem.u16(cam_addr) if cam_addr else None
        mb = p.mem.u8(MISSION_ADDR)
        bombs = guard.read("bombs")
        timer = guard.read("timer") if t_addr else None
        lives = guard.read("lives") if l_addr else None
        prev_score = last_score

        # ---- semantic events -----------------------------------------
        if score > prev_score:
            d = score - prev_score
            evc["score_up"] += 1
            evc[f"score+{d}"] += 1
            if d >= 90:
                kills += 1
            kc.on_score_event(p.mem)
        if lives is not None and prev_lives is not None \
                and lives < prev_lives:
            evc["death"] += 1
            deaths_seen.append({"chunk": i, "lives": lives})
        prev_lives = lives
        if mb != mb0:
            evc["mission_byte_changed"] += 1

        # ---- progress / stall ----------------------------------------
        # progress = score gain (kills) OR the world is scrolling
        # (RAM churn). Both use VERIFIED signals only.
        prog = score > prev_score or last_churn >= 3500
        if cam_now is not None and last_cam is not None \
                and cam_now < last_cam - 100:
            evc["cam_reset"] += 1        # death/respawn moved camera back
            stall = min(stall, 5)
        last_cam = cam_now
        stall = 0 if prog else stall + 1

        # ---- mission clear? ------------------------------------------
        if mb != mb0:
            png(p, "99_MISSION_CLEAR.png")
            log(f"*** MISSION CLEAR: mission byte {mb0}->{mb} "
                f"at chunk {i} (score={score}) ***")
            cleared = True
            report["mission_clear"] = {
                "chunk": i, "game_min": round(i * CHUNK / 3600, 1),
                "score": score, "from": mb0, "to": int(mb)}
            break

        # ---- scene (advisory, every 4th chunk only — noise anyway) ----
        scene_n = 0
        if i % 4 == 0 and wm.slots:
            scene = wm.read_world(p.core)
            scene_n = len(scene.get("enemies", []))

        # ---- policy + execute (with per-chunk churn measurement) -------
        s_before = p.mem.snapshot()
        segs = policy.decide(CHUNK, stall, bombs, timer, zone,
                             last_churn)
        execute(p, segs, CHUNK)
        churn = int(np.count_nonzero(s_before != p.mem.snapshot()))
        last_churn = churn
        low_streak = low_streak + 1 if churn < 2500 else 0
        zone = low_streak >= 2
        if zone and i % 4 == 0:
            png(p, "zone_live.png")       # rolling pre-death context
        last_score = score
        if i % 4 == 0:
            kc.observe(p.mem)             # evidence-only, every 4th chunk

        # ---- keepalive / recovery (CONTINUE screen has ~9s timer) ------
        if i % 3 == 2:
            ok, (i1, rr) = responsive_live(p)
            last_churn = max(last_churn, rr if isinstance(rr, int) else 0)
            if not ok:
                continues += 1
                evc["unresponsive"] += 1
                try:
                    zl = os.path.join(EVID, "zone_live.png")
                    if os.path.exists(zl):
                        os.replace(zl, os.path.join(
                            EVID, f"predeath_{i:04d}.png"))
                except OSError:
                    pass
                png(p, f"death_{i:04d}.png")          # kill-site evidence
                log(f"[keepalive] chunk {i}: unresponsive "
                    f"(idle={i1} run={rr}) -> recover")
                recover_v2(p, log=log)
                ok, (i1, rr) = responsive_live(p)
                last_churn = max(last_churn, rr if isinstance(rr, int) else 0)
                if not ok:
                    log("[keepalive] still out -> ensure_mission")
                    m = ensure_mission(p, tries=4, log=log)
                    if not m.get("in_mission"):
                        log("[keepalive] re-entering mission")
                        p.enter_gameplay3()
                        ensure_mission(p, tries=4, log=log)
                    ra = guard.anchor(log=log)
                    if ra.get("ok"):
                        report.setdefault("reanchors", []).append(
                            {"chunk": i, **ra})
                        t_addr = validate_timer(guard, log=log)
                    report.setdefault("reanchors", []).append(
                        {"chunk": i, "note": "re-entered"})
                policy.hop_cd = max(policy.hop_cd, 60)
                report.setdefault("continues", []).append(
                    {"chunk": i, "score": score})
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
                    evc["pause_tap"] += 1
                    log(f"[keepalive] chunk {i}: inputs dead "
                        f"(L={cl} R={cr}) -> START tap (unpause?)")
                    p.core.run(6, {"START"})
                    p.core.run(60, set())
                    p._advance()
                    policy.hop_cd = max(policy.hop_cd, 60)

        # ---- telemetry / evidence -------------------------------------
        if i % 5 == 4:
            act = policy.stats
            log(f"[t] i={i} score={score} cam={cam_now} "
                f"churn={last_churn} zone={int(zone)} "
                f"enemies={scene_n} bombs={bombs} timer={timer} "
                f"lives={lives} stall={stall} "
                f"act={max(act, key=act.get) if act else '-'}")
        if i % 25 == 24:
            tel.append({"chunk": i, "score": score, "cam": cam_now,
                        "bombs": bombs, "timer": timer, "lives": lives,
                        "stall": stall, "churn": last_churn,
                        "enemies": scene_n,
                        "act": (max(policy.stats, key=policy.stats.get)
                                if policy.stats else "-")})
            png(p, f"play_{(i // 25) + 1:02d}.png")
        if i in (20, 60, 120) or (i % 250 == 249):
            p.save_state(f"m1cp_{i}")
            p.save_state("m1cp")
            log("checkpoint @", i, "score", score)

    wall = time.time() - t0
    report["play"] = {
        "chunks": i + 1, "frames": (i + 1) * CHUNK,
        "wall_s": round(wall, 1),
        "fps": round((i + 1) * CHUNK / max(wall, 0.1), 1),
        "score_start": int(score0), "score_end": int(guard.score()),
        "kills_est": kills, "continues": continues,
        "cleared": cleared, "stall_final": stall,
        "policy_stats": dict(policy.stats)}
    report["events"] = dict(evc)
    report["deaths"] = deaths_seen
    report["telemetry"] = tel
    report["kill_correlator"] = kc.to_dict()
    report["guard_addrs"] = {k: hex(v) for k, v in guard.addrs.items()}
    if not cleared:
        png(p, "99_end.png")
    json.dump(report, open(OUT, "w"), indent=1, default=str)
    p.save_profile()
    log("report ->", OUT)
    print(json.dumps({k: report.get(k) for k in
                      ("boot", "enter", "camera", "anchor", "play",
                       "events", "kill_correlator", "mission_clear")},
                     indent=1, default=str))


if __name__ == "__main__":
    main()
